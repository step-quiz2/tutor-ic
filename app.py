"""
Tutor IC — UI Streamlit.

Per executar:
    export GEMINI_API_KEY=...
    streamlit run app.py

Senyals especials que l'alumne pot teclejar:
    ?        → demana pista socràtica
    !text    → registra discrepància («tinc raó perquè...») i avança
    !!       → tanca la sessió

Estat top-level de st.session_state (NO es reseteja amb "Reiniciar sessió"):
    disclaimer_acknowledged : bool. L'usuari ha acceptat l'avís d'ús.
    api_calls_used          : int. Comptador de crides a la IA durant
                              tota la sessió de navegador. Persistent
                              entre reinicis per evitar que un alumne
                              reinicii per recuperar quota.

Estat per problema (st.session_state.tutor): es reseteja amb "Reiniciar".
"""

import json
import time
import streamlit as st

import problem as PB
import llm as L

st.set_page_config(page_title="Tutor IC", page_icon="📊", layout="centered")


# ============================================================
# Constants
# ============================================================
MIN_ANSWER_CHARS = 10

# Sostre de crides a la IA per sessió de navegador. Una sessió típica
# raonable consumeix entre 4 i 12 crides (3 passos × 1-2 crides + alguna
# pista). 20 dona prou marge per a retrocés a prereq + un parell de
# pistes, però talla l'abús d'un input spamejat.
MAX_API_CALLS_PER_SESSION = 20

DISCLAIMER_TEXT = """
**Atenció, aquest programa està en mode DEBUG / desenvolupament.**

Recorda: **no pots escriure cap dada personal, familiar o financera.**
No escriguis el teu nom, el teu PIN, adreces, telèfons, números de
compte, ni cap altra dada identificativa de tu mateix o de tercers.

Respon **exclusivament** amb raonaments de matemàtiques o d'estadística.
"""


# ============================================================
# Estat tutorial (per problema)
# ============================================================
def _new_state():
    return {
        "started_at": time.time(),
        "current_step_idx": 0,
        "history": [],
        "messages": [],
        "active_prereq": None,
        "concept_failure_streak": 0,
        "discrepancies": [],
        "hints_requested": 0,
        "finished": None,
        "awaiting_next": False,
    }


def _push(kind: str, text: str, persistent: bool = False):
    st.session_state.tutor["messages"].append({
        "kind": kind, "text": text, "persistent": persistent,
    })


# ============================================================
# Gestió de quota d'API
# ============================================================
def _api_quota_exhausted() -> bool:
    return st.session_state.get("api_calls_used", 0) >= MAX_API_CALLS_PER_SESSION


def _consume_api_quota():
    """Incrementa el comptador. Cridar JUST ABANS de cada crida a llm."""
    st.session_state.api_calls_used = (
        st.session_state.get("api_calls_used", 0) + 1
    )


def _push_quota_exhausted_warning():
    _push("warning",
          f"⚠️ Has arribat al límit de {MAX_API_CALLS_PER_SESSION} "
          "crides d'aquesta sessió. Per continuar, tanca i torna a "
          "obrir l'aplicació al navegador.")


# ============================================================
# Lògica nuclear del torn
# ============================================================
def _process_prereq_turn(answer: str):
    """Validació deterministica per keyword matching. Cap crida a IA."""
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


def _try_generate_hint(step) -> bool:
    """Genera una pista respectant la quota i mostra els missatges UI.
    Retorna True si s'ha generat alguna pista, False si la quota era
    plena o hi ha hagut error tècnic."""
    if _api_quota_exhausted():
        _push_quota_exhausted_warning()
        return False
    _consume_api_quota()
    try:
        with st.spinner("Generant pista..."):
            hint = L.generate_hint(step, "param_vs_stat")
        _push("hint", f"💡 {hint}")
        return True
    except Exception:
        _push("warning",
              "⚠️ No s'ha pogut generar la pista (servei IA no disponible). "
              "Pots tornar-ho a provar.")
        return False


def process_turn(raw: str):
    state = st.session_state.tutor
    state["messages"] = [m for m in state["messages"] if m["persistent"]]

    s = (raw or "").strip()
    if not s:
        return

    # --- Senyals d'escapament: cap crida API ---
    if s in ("!!", ":q", "exit"):
        state["finished"] = "abandoned"
        _push("system", "Sessió tancada. Rastre desat.")
        return

    if s == "?":
        # Dins de prereq la pista és deterministica (sense API). Fora,
        # cal generar amb la IA i això consumeix quota.
        if state["active_prereq"] is not None:
            pre = PB.PREREQUISITES[state["active_prereq"]]
            _push("hint", pre["explanation"])
            state["hints_requested"] += 1
        else:
            step = PB.PROBLEM["passos"][state["current_step_idx"]]
            if _try_generate_hint(step):
                state["hints_requested"] += 1
        return

    if s.startswith("!") and len(s) > 1:
        # Discrepància: cap crida API.
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

    # --- Sessió de prerequisit activa: validació deterministica ---
    if state["active_prereq"] is not None:
        _process_prereq_turn(s)
        return

    # --- Guard contra entrades no substantives (sense crida IA) ---
    if len(s) < MIN_ANSWER_CHARS:
        _push("warning",
              "✏️ La teva resposta és massa curta per avaluar-la bé. "
              "Desenvolupa la idea (almenys una frase completa) i "
              "torna-la a enviar.")
        return

    # --- Pas normal: avaluació via IA (consumeix quota) ---
    if _api_quota_exhausted():
        _push_quota_exhausted_warning()
        return

    step = PB.PROBLEM["passos"][state["current_step_idx"]]
    _consume_api_quota()
    try:
        with st.spinner("Avaluant resposta..."):
            verdict_obj = L.judge_step(step, s)
    except Exception:
        _push("warning",
              "⚠️ El servei d'avaluació no respon ara mateix. "
              "Torna a enviar la mateixa resposta d'aquí uns segons.")
        return

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
        state["awaiting_next"] = True
        return

    state["concept_failure_streak"] += 1
    streak = state["concept_failure_streak"]
    cat_msg = PB.ERROR_CATALOG.get(label or "", "") if label else ""
    feedback = cat_msg or reason or "La resposta no és correcta."
    _push("feedback", f"✗ {feedback}")

    if v == "conceptual_gap":
        if streak >= 2:
            _try_generate_hint(step)
        else:
            _activate_prereq()
    elif v == "typical_error":
        if streak >= 2:
            _try_generate_hint(step)


# ============================================================
# Rastre JSON per al professor
# ============================================================
def build_trace() -> dict:
    state = st.session_state.tutor
    return {
        "problema": PB.PROBLEM["id"],
        "tema": PB.PROBLEM["tema"],
        "started_at": state["started_at"],
        "durada_s": round(time.time() - state["started_at"], 1),
        "passos_totals": len(PB.PROBLEM["passos"]),
        "pas_assolit": state["current_step_idx"],
        "torns": state["history"],
        "discrepancies": state["discrepancies"],
        "pistes_demanades": state["hints_requested"],
        "crides_api_usades_sessio": st.session_state.get("api_calls_used", 0),
        "crides_api_limit_sessio": MAX_API_CALLS_PER_SESSION,
        "veredicte": state["finished"] or "en_curs",
    }


# ============================================================
# UI: pantalla d'avís inicial
# ============================================================
def render_disclaimer():
    st.title("⚠️ Avís d'ús")
    st.warning(DISCLAIMER_TEXT)
    st.markdown("---")
    acknowledged = st.checkbox(
        "**Comprenc el que he llegit** i em comprometo a no introduir "
        "cap dada personal."
    )
    if st.button("Començar", type="primary", disabled=not acknowledged):
        st.session_state.disclaimer_acknowledged = True
        st.rerun()


# ============================================================
# UI: aplicació principal
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
        # Indicador de quota usada per a tota la sessió de navegador.
        used = st.session_state.get("api_calls_used", 0)
        remaining = MAX_API_CALLS_PER_SESSION - used
        msg = f"Crides API: {used} / {MAX_API_CALLS_PER_SESSION}"
        if remaining > 5:
            st.caption(msg)
        elif remaining > 0:
            st.warning(f"{msg}  (queden {remaining})")
        else:
            st.error(f"{msg}  (límit assolit)")


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
    # Estat top-level (no es reseteja amb "Reiniciar sessió").
    if "disclaimer_acknowledged" not in st.session_state:
        st.session_state.disclaimer_acknowledged = False
    if "api_calls_used" not in st.session_state:
        st.session_state.api_calls_used = 0

    # Gate: si encara no s'ha acceptat l'avís, només mostrem la pantalla
    # d'avís. Cap altra cosa es renderitza fins que l'usuari cliqui
    # "Començar".
    if not st.session_state.disclaimer_acknowledged:
        render_disclaimer()
        return

    # Estat tutorial per a aquest problema.
    if "tutor" not in st.session_state:
        st.session_state.tutor = _new_state()

    render_sidebar()
    render_problem_header()
    render_messages()

    state = st.session_state.tutor

    if state["finished"] is None:
        if state["awaiting_next"]:
            if st.button("Següent →", type="primary"):
                state["messages"] = []
                state["awaiting_next"] = False
                state["current_step_idx"] += 1
                _maybe_finish()
                st.rerun()
        else:
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
