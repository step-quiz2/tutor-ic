"""
Tutor IC — UI Streamlit.

Per executar:
    export GEMINI_API_KEY=...
    streamlit run app.py

Senyals especials que l'alumne pot teclejar:
    ?        → demana pista socràtica
    !text    → registra discrepància («tinc raó perquè...») i avança
    !!       → tanca la sessió

Tot l'estat de la sessió viu a `st.session_state.tutor`. Es perd quan
es tanca la finestra: no hi ha persistència a disc. Per a 20 minuts de
demo és suficient.
"""

import json
import time
import streamlit as st

import problem as PB
import llm as L

st.set_page_config(page_title="Tutor IC", page_icon="📊", layout="centered")


# ============================================================
# Estat de la sessió
# ============================================================
def _new_state():
    return {
        "started_at": time.time(),
        "current_step_idx": 0,
        "history": [],            # tots els torns enviats
        "messages": [],           # missatges visibles a la UI (per al torn actual)
        "active_prereq": None,    # id del prereq actiu, o None
        "concept_failure_streak": 0,
        "discrepancies": [],
        "hints_requested": 0,
        "finished": None,         # None | "solved" | "abandoned" | "referred"
    }


def _push(kind: str, text: str, persistent: bool = False):
    """kind ∈ {system, feedback, hint, prereq, prereq_done, discrepancy, warning}"""
    st.session_state.tutor["messages"].append({
        "kind": kind, "text": text, "persistent": persistent,
    })


# ============================================================
# Lògica nuclear del torn
# ============================================================
def _process_prereq_turn(answer: str):
    """L'alumne respon dins del mini-exercici PRE-PARAM. Validació
    deterministica per keyword matching."""
    state = st.session_state.tutor
    pre = PB.PREREQUISITES[state["active_prereq"]]
    low = answer.lower()
    has_req = any(kw.lower() in low for kw in pre["keywords_required"])
    has_forb = any(kw.lower() in low for kw in pre["forbidden_keywords"])
    correct = has_req and not has_forb

    if correct:
        _push("prereq_done",
              f"✓ Molt bé. {pre['explanation']}\n\nTornem ara al "
              "problema principal, prova de respondre el pas anterior "
              "tenint això al cap.",
              persistent=True)
    else:
        _push("prereq_done",
              f"No exactament. {pre['explanation']}\n\nTornem ara al "
              "problema principal amb aquesta idea clara.",
              persistent=True)

    state["history"].append({
        "type": "prereq",
        "prereq_id": state["active_prereq"],
        "student": answer,
        "correct": correct,
        "ts": time.time(),
    })
    state["active_prereq"] = None


def _activate_prereq():
    """Activa el mini-exercici de reforç."""
    state = st.session_state.tutor
    pre_id = PB.DEPENDENCIES["param_vs_stat"]["prerequisite"]
    pre = PB.PREREQUISITES[pre_id]
    state["active_prereq"] = pre_id
    _push("prereq",
          f"### 🔁 Sembla que cal aclarir un concepte previ\n\n"
          f"**Exercici de reforç:** {pre['question']}")


def _maybe_finish():
    state = st.session_state.tutor
    if state["current_step_idx"] >= len(PB.PROBLEM["passos"]):
        state["finished"] = "solved"
        _push("system",
              "🎉 **Has completat el problema!** "
              "Has interpretat correctament l'interval de confiança "
              "evitant l'error clàssic. Bona feina.")


def process_turn(raw: str):
    """Punt d'entrada únic. Modifica `st.session_state.tutor` directament."""
    state = st.session_state.tutor

    # Neteja missatges no persistents (els persistents són feedbacks de
    # prereq que volem que l'alumne segueixi veient).
    state["messages"] = [m for m in state["messages"] if m["persistent"]]

    s = (raw or "").strip()
    if not s:
        return

    # --- Senyals d'escapament ---
    if s in ("!!", ":q", "exit"):
        state["finished"] = "abandoned"
        _push("system", "Sessió tancada. Rastre desat.")
        return

    if s == "?":
        # Demana pista. Si estem dins de prereq, mostrem l'explicació.
        if state["active_prereq"] is not None:
            pre = PB.PREREQUISITES[state["active_prereq"]]
            _push("hint", pre["explanation"])
        else:
            step = PB.PROBLEM["passos"][state["current_step_idx"]]
            with st.spinner("Generant pista..."):
                hint = L.generate_hint(step, "param_vs_stat")
            _push("hint", f"💡 {hint}")
        state["hints_requested"] += 1
        return

    if s.startswith("!") and len(s) > 1:
        payload = s[1:].strip()
        state["discrepancies"].append({
            "step": state["current_step_idx"] + 1,
            "text": payload,
            "ts": time.time(),
        })
        state["history"].append({
            "type": "discrepancy",
            "step_id": state["current_step_idx"] + 1,
            "text": payload,
            "ts": time.time(),
        })
        _push("discrepancy",
              "D'acord, queda anotat per revisió del professor. Continuem.")
        state["current_step_idx"] += 1
        _maybe_finish()
        return

    # --- Sessió de prerequisit activa ---
    if state["active_prereq"] is not None:
        _process_prereq_turn(s)
        return

    # --- Pas normal: avaluació via IA ---
    step = PB.PROBLEM["passos"][state["current_step_idx"]]
    with st.spinner("Avaluant resposta..."):
        verdict_obj = L.judge_step(step, s)

    v = verdict_obj["verdict"]
    reason = verdict_obj.get("reason", "")
    label = verdict_obj.get("error_label")

    state["history"].append({
        "type": "step",
        "step_id": step["id"],
        "student": s,
        "verdict": v,
        "error_label": label,
        "reason": reason,
        "ts": time.time(),
    })

    if v == "correct":
        state["concept_failure_streak"] = 0
        _push("feedback", f"✓ **Correcte.** {reason}".strip())
        state["current_step_idx"] += 1
        _maybe_finish()
        return

    # Error: incrementem streak per decidir si retrocedim o donem pista.
    state["concept_failure_streak"] += 1
    streak = state["concept_failure_streak"]

    # Mostrem missatge del catàleg si tenim etiqueta coneguda.
    cat_msg = PB.ERROR_CATALOG.get(label or "", "") if label else ""
    feedback = cat_msg or reason or "La resposta no és correcta."
    _push("feedback", f"✗ {feedback}")

    if v == "conceptual_gap":
        # Primera fallada conceptual → retrocés a prereq.
        # Segona fallada del mateix concepte → pista socràtica directa.
        if streak >= 2:
            with st.spinner("Generant pista..."):
                hint = L.generate_hint(step, "param_vs_stat")
            _push("hint", f"💡 {hint}")
        else:
            _activate_prereq()
    elif v == "typical_error":
        # Error clàssic. Donem una empenta socràtica directament si ja
        # ha fallat dos cops el mateix concepte.
        if streak >= 2:
            with st.spinner("Generant pista..."):
                hint = L.generate_hint(step, "param_vs_stat")
            _push("hint", f"💡 {hint}")


# ============================================================
# Rastre JSON per al professor
# ============================================================
def build_trace() -> dict:
    state = st.session_state.tutor
    return {
        "problema":     PB.PROBLEM["id"],
        "tema":         PB.PROBLEM["tema"],
        "started_at":   state["started_at"],
        "durada_s":     round(time.time() - state["started_at"], 1),
        "passos_totals": len(PB.PROBLEM["passos"]),
        "pas_assolit":  state["current_step_idx"],
        "torns":        state["history"],
        "discrepancies": state["discrepancies"],
        "pistes_demanades": state["hints_requested"],
        "veredicte":    state["finished"] or "en_curs",
    }


# ============================================================
# UI
# ============================================================
def render_sidebar():
    with st.sidebar:
        st.markdown("### 📊 Tutor IC")
        st.markdown(f"**Problema:** {PB.PROBLEM['id']} — {PB.PROBLEM['tema']}")
        st.markdown("---")
        st.markdown("**Senyals especials:**")
        st.markdown(
            "- `?` → pista socràtica\n"
            "- `!text` → discrepància («tinc raó perquè...»)\n"
            "- `!!` → tancar sessió"
        )
        st.markdown("---")
        if st.button("🔄 Reiniciar sessió"):
            st.session_state.tutor = _new_state()
            st.rerun()
        st.markdown("---")
        st.caption(f"Model: `{L.MODEL}`")
        if "tutor" in st.session_state:
            t = st.session_state.tutor
            n_calls = sum(1 for h in t["history"] if h.get("type") == "step")
            st.caption(f"Crides IA: {n_calls}")


def render_problem_header():
    st.title("📊 Tutor d'interval de confiança")
    st.markdown(PB.PROBLEM["enunciat"])
    state = st.session_state.tutor
    total = len(PB.PROBLEM["passos"])
    idx = state["current_step_idx"]
    if state["finished"] is None and idx < total:
        st.markdown(f"### Pas {idx + 1} de {total}")
        step = PB.PROBLEM["passos"][idx]
        st.info(step["text"])


def render_messages():
    state = st.session_state.tutor
    for msg in state["messages"]:
        kind = msg["kind"]
        text = msg["text"]
        if kind == "feedback":
            if text.startswith("✓"):
                st.success(text)
            else:
                st.error(text)
        elif kind == "hint":
            st.info(text)
        elif kind == "prereq":
            st.warning(text)
        elif kind == "prereq_done":
            st.success(text)
        elif kind == "discrepancy":
            st.info(text)
        elif kind == "system":
            st.success(text)
        elif kind == "warning":
            st.warning(text)


def render_history():
    state = st.session_state.tutor
    if not state["history"]:
        return
    with st.expander(f"📋 Historial ({len(state['history'])} torns)"):
        for h in state["history"]:
            t = h.get("type", "?")
            if t == "step":
                v = h.get("verdict", "")
                icon = "✓" if v == "correct" else "✗"
                st.markdown(
                    f"**Pas {h.get('step_id')}** — {icon} *{v}*  \n"
                    f"_Alumne:_ {h.get('student', '')}  \n"
                    f"_IA:_ {h.get('reason', '')}"
                )
            elif t == "prereq":
                ok = "✓" if h.get("correct") else "✗"
                st.markdown(
                    f"**Prereq {h.get('prereq_id')}** — {ok}  \n"
                    f"_Alumne:_ {h.get('student', '')}"
                )
            elif t == "discrepancy":
                st.markdown(
                    f"**Discrepància** (pas {h.get('step_id')}): "
                    f"{h.get('text', '')}"
                )
            st.markdown("---")


def render_trace():
    state = st.session_state.tutor
    if state["finished"] is None:
        return
    with st.expander("🔍 Rastre JSON (per al professor)"):
        st.json(build_trace())


# ============================================================
# Main
# ============================================================
def main():
    if "tutor" not in st.session_state:
        st.session_state.tutor = _new_state()

    render_sidebar()
    render_problem_header()
    render_messages()

    state = st.session_state.tutor

    if state["finished"] is None:
        # Input. Form clear-on-submit; el botó "Enviar" envia el text.
        with st.form("answer_form", clear_on_submit=True):
            answer = st.text_area(
                "La teva resposta:",
                key="answer_input",
                height=100,
                placeholder="Escriu aquí... (o `?` per a pista, `!text` per discrepància)",
            )
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                submitted = st.form_submit_button("Enviar ↵")
            with col2:
                hint_btn = st.form_submit_button("? Pista")
            with col3:
                exit_btn = st.form_submit_button("✕ Sortir")

        if submitted and answer.strip():
            process_turn(answer)
            st.rerun()
        elif hint_btn:
            process_turn("?")
            st.rerun()
        elif exit_btn:
            process_turn("!!")
            st.rerun()
    else:
        if state["finished"] == "solved":
            st.balloons()
        elif state["finished"] == "abandoned":
            st.info("Sessió tancada. Pots reiniciar al panell de l'esquerra.")

    render_history()
    render_trace()


if __name__ == "__main__":
    main()
