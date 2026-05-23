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
        "prereq_attempts": 0,
        # Tracking de pistes per al generador dirigit (Proposta 3).
        # `hints_by_step` és un dict {step_id (int) -> list[str]} que
        # acumula les pistes donades a cada pas, perquè el generador
        # eviti repetir-les. `prereq_hints` és la llista anàloga però
        # del reforç actiu (es buida quan el reforç es tanca).
        "hints_by_step": {},
        "prereq_hints": [],
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
    """Validació del prereq via LLM judge (proposta 2 del registre de
    canvis). Substitueix el matching determinista per keyword, que tenia
    exactament el patró de fallada KEY_only documentat al Phase 2 del
    PROJECT_LOG.

    Política de reintents:
      - "correct"     → tanquem el reforç i tornem al problema.
      - "keyword_only" en el PRIMER intent → micropista i nou intent
                       sobre la mateixa pregunta (no avancem).
      - "keyword_only" en el SEGON intent → explicació canònica i
                       tornem al problema.
      - "incorrect"   → explicació canònica i tornem al problema.
                       (Sense reintent: si la resposta està molt
                       desviada, un segon intent rarament ajuda;
                       l'alumne pot seguir endavant amb la
                       infraestructura `!text` si pensa que té raó.)
    """
    state = st.session_state.tutor
    pre = PB.PREREQUISITES[state["active_prereq"]]

    # Fast-reject deterministic: si la resposta conté una afirmació
    # explícitament prohibida ("μ és aleatòria"), no cal cridar la
    # IA — és incorrect per construcció.
    low = answer.lower()
    has_forb = any(kw.lower() in low for kw in pre["forbidden_keywords"])

    if has_forb:
        result = {
            "verdict": "incorrect",
            "reason": ("Has afirmat el contrari del que volem clarificar: "
                       "que μ és aleatòria. Repassa-ho amb cura."),
            "n_api_calls": 0,
        }
        api_consumed = False
    else:
        # Crida real al judge LLM.
        if _api_quota_exhausted():
            _push_quota_exhausted_warning()
            return
        # Self-consistency selectiva (Proposta 5): permetem resample
        # només si tenim quota per a 2 crides.
        remaining = MAX_API_CALLS_PER_SESSION - st.session_state.get("api_calls_used", 0)
        allow_resample = (remaining >= 2)
        _consume_api_quota()
        api_consumed = True
        try:
            with st.spinner("Avaluant resposta del reforç..."):
                result = L.judge_prereq(pre, answer, allow_resample=allow_resample)
        except Exception:
            _push("warning",
                  "⚠️ El servei d'avaluació no respon ara mateix. "
                  "Torna a enviar la mateixa resposta d'aquí uns segons.")
            return
        # Comptem extra crides de re-mostreig.
        extra_calls = max(0, result.get("n_api_calls", 1) - 1)
        for _ in range(extra_calls):
            _consume_api_quota()

    v = result["verdict"]
    reason = result.get("reason", "")
    state["prereq_attempts"] += 1
    attempt = state["prereq_attempts"]

    state["history"].append({
        "type": "prereq",
        "prereq_id": state["active_prereq"],
        "student": answer,
        "verdict": v,
        "reason": reason,
        "attempt": attempt,
        "api_call": api_consumed,
        # Metadades de self-consistency (Proposta 5).
        "confidence": result.get("confidence"),
        "resampled": result.get("resampled", False),
        "initial_verdict": result.get("initial_verdict"),
        "agreement": result.get("agreement"),
        "resample_failed": result.get("resample_failed", False),
        "n_api_calls": result.get("n_api_calls", 0 if not api_consumed else 1),
        "ts": time.time(),
    })

    if v == "correct":
        praise = (reason + "\n\n") if reason else ""
        _push("prereq_done",
              f"✓ Molt bé. {praise}Tornem ara al problema principal, "
              "prova de respondre el pas anterior tenint això al cap.",
              persistent=True)
        state["active_prereq"] = None
        state["prereq_attempts"] = 0
        state["prereq_hints"] = []
        return

    if v == "keyword_only" and attempt == 1:
        # Segon intent: la micropista ara la genera la IA dirigida a la
        # resposta concreta de l'alumne (Proposta 3). Si la quota està
        # plena o la IA falla, fallback a la micropista estàtica que
        # vam introduir al Canvi 2.
        state["prereq_hints"] = []  # comença el tracking del reforç
        hint_text = None
        if not _api_quota_exhausted():
            _consume_api_quota()
            try:
                with st.spinner("Generant micropista..."):
                    hint_text = L.generate_prereq_hint(
                        pre,
                        student_answer=answer,
                        judge_reason=reason,
                        prior_hints=[],
                    )
            except Exception:
                hint_text = None

        if hint_text:
            state["prereq_hints"].append(hint_text)
            state["history"].append({
                "type": "hint",
                "scope": "prereq",
                "prereq_id": state["active_prereq"],
                "text": hint_text,
                "had_student_context": True,
                "n_prior_hints": 0,
                "auto": True,  # generada automàticament al keyword_only-1
                "ts": time.time(),
            })
            _push("prereq_feedback", f"💡 {hint_text}")
        else:
            # Fallback: micropista estàtica.
            _push("prereq_feedback",
                  "La teva resposta toca el tema però falta concretar. "
                  "Assegura't que diguis explícitament **què és μ** i "
                  "**què és x̄**, i **quina de les dues és aleatòria**.")
        # No tanquem active_prereq: l'alumne respon de nou.
        return

    # Cas final: keyword_only al segon intent, o incorrect → tanquem
    # amb explicació canònica i retornem al problema.
    intro = (reason + "\n\n") if (reason and v == "incorrect") else ""
    _push("prereq_done",
          f"{intro}{pre['explanation']}\n\nTornem ara al problema "
          "principal amb aquesta idea clara.",
          persistent=True)
    state["active_prereq"] = None
    state["prereq_attempts"] = 0
    state["prereq_hints"] = []


def _activate_prereq():
    state = st.session_state.tutor
    pre_id = PB.DEPENDENCIES["param_vs_stat"]["prerequisite"]
    state["active_prereq"] = pre_id
    # Reset defensiu: si quedés residual d'una activació prèvia
    # (no hauria de passar, però defensiu millor que recuperar bugs).
    state["prereq_attempts"] = 0
    state["prereq_hints"] = []
    _push("prereq",
          "🔁 **Sembla que cal aclarir un concepte previ.** "
          "Pots veure la pregunta de reforç a la part superior; "
          "respon-la a continuació.")


def _maybe_finish():
    state = st.session_state.tutor
    if state["current_step_idx"] >= len(PB.PROBLEM["passos"]):
        state["finished"] = "solved"
        _push("system",
              "🎉 **Has completat el problema!** "
              "Has interpretat correctament l'interval de confiança "
              "evitant l'error clàssic. Bona feina.")


def _build_judge_context(step_id: int) -> dict:
    """Construeix el context de trajectòria que es passa a `judge_step`
    (Proposta 1).

    Compacte i agregat — no traslladem text íntegre de respostes
    anteriors al judge perquè faria créixer molt els tokens d'input
    per crida; passem només els indicadors que les regles P3a/P3b/P3c
    del system prompt necessiten per decidir.

    Camps:
      recent_steps          fins als 3 torns 'step' més recents, més
                            nou primer, amb step_id, verdict i
                            error_label.
      prereq                {activated, final_verdict, attempts} del
                            darrer cicle del reforç. "final_verdict"
                            és l'últim verdict registrat (sigui correct,
                            keyword_only o incorrect). Si el cicle es
                            va tancar amb explicació canònica després
                            d'un keyword_only-2 o incorrect, el camp
                            reflecteix l'últim verdict abans del
                            tancament — això vol dir "no l'ha
                            demostrat", que és el que el judge
                            necessita saber.
      step_attempts         intents previs al MATEIX step_id (sense
                            comptar el torn que estem a punt de
                            jutjar).
      concept_failure_streak  comptador de conceptual_gap consecutius
                              actual (mateix camp d'estat).
    """
    state = st.session_state.tutor

    # Últims 3 torns step en ordre invers (més recents primer).
    recent_steps = []
    for h in reversed(state["history"]):
        if h.get("type") != "step":
            continue
        recent_steps.append({
            "step_id": h.get("step_id"),
            "verdict": h.get("verdict"),
            "error_label": h.get("error_label"),
        })
        if len(recent_steps) >= 3:
            break

    # Estat del reforç: ens interessa el darrer cicle.
    prereq_entries = [h for h in state["history"] if h.get("type") == "prereq"]
    if prereq_entries:
        # El darrer cicle acaba a l'últim entry; recorrem cap enrere
        # mentre l'attempt vagi decreixent (signal de mateix cicle).
        last = prereq_entries[-1]
        attempts_in_cycle = 1
        prev_attempt = last.get("attempt", 1)
        for entry in reversed(prereq_entries[:-1]):
            a = entry.get("attempt")
            if a is not None and a < prev_attempt:
                attempts_in_cycle += 1
                prev_attempt = a
            else:
                break
        prereq_info = {
            "activated": True,
            "final_verdict": last.get("verdict"),
            "attempts": attempts_in_cycle,
        }
    else:
        prereq_info = {
            "activated": False,
            "final_verdict": None,
            "attempts": 0,
        }

    # Intents previs al pas que estem a punt de jutjar (NO inclou la
    # resposta que estem a punt de classificar — encara no està a
    # history).
    step_attempts = sum(
        1 for h in state["history"]
        if h.get("type") == "step" and h.get("step_id") == step_id
    )

    return {
        "recent_steps": recent_steps,
        "prereq": prereq_info,
        "step_attempts": step_attempts,
        "concept_failure_streak": state.get("concept_failure_streak", 0),
    }



def _last_non_correct_answer_for_step(step_id: int):
    """Retorna (student_answer, reason, error_label) de l'últim torn
    no-correct al pas indicat. Si no n'hi ha, retorna tres None.
    Helper de _try_generate_hint (Proposta 3)."""
    state = st.session_state.tutor
    for h in reversed(state["history"]):
        if h.get("type") != "step":
            continue
        if h.get("step_id") != step_id:
            continue
        if h.get("verdict") == "correct":
            continue
        return (h.get("student"), h.get("reason"), h.get("error_label"))
    return (None, None, None)


def _last_non_correct_prereq_answer(prereq_id: str):
    """Anàleg per al reforç. Retorna (student_answer, reason)."""
    state = st.session_state.tutor
    for h in reversed(state["history"]):
        if h.get("type") != "prereq":
            continue
        if h.get("prereq_id") != prereq_id:
            continue
        if h.get("verdict") == "correct":
            continue
        return (h.get("student"), h.get("reason"))
    return (None, None)


def _try_generate_hint(step) -> bool:
    """Genera una pista DIRIGIDA respectant la quota.

    Canvis respecte de la versió original (Proposta 3): la pista ja no
    és genèrica per al pas — el generador rep la darrera resposta no-
    correct de l'alumne a aquest pas, la raó del judge, l'etiqueta
    d'error i les pistes anteriors per al mateix pas. Quan no hi ha
    cap d'aquests contexts (`?` al principi del pas), genera una pista
    genèrica però el prompt sap diferenciar el cas.

    Retorna True si s'ha generat alguna pista, False si la quota era
    plena o hi ha hagut error tècnic.
    """
    if _api_quota_exhausted():
        _push_quota_exhausted_warning()
        return False

    state = st.session_state.tutor
    step_id = step["id"]
    last_answer, last_reason, last_label = _last_non_correct_answer_for_step(step_id)
    prior_hints = list(state["hints_by_step"].get(step_id, []))

    _consume_api_quota()
    try:
        with st.spinner("Generant pista..."):
            hint = L.generate_hint(
                step, "param_vs_stat",
                student_answer=last_answer,
                judge_reason=last_reason,
                error_label=last_label,
                prior_hints=prior_hints,
            )
        _push("hint", f"💡 {hint}")
        # Tracking: guardem la pista per al pas i a l'historial.
        state["hints_by_step"].setdefault(step_id, []).append(hint)
        state["history"].append({
            "type": "hint",
            "scope": "step",
            "step_id": step_id,
            "text": hint,
            "had_student_context": last_answer is not None,
            "n_prior_hints": len(prior_hints),
            "ts": time.time(),
        })
        return True
    except Exception:
        _push("warning",
              "⚠️ No s'ha pogut generar la pista (servei IA no disponible). "
              "Pots tornar-ho a provar.")
        return False


def _try_generate_prereq_hint() -> bool:
    """Genera una pista DIRIGIDA per al reforç actiu (Proposta 3).

    Substitueix l'antic comportament del `?` durant el reforç, que era
    dispar l'explicació canònica completa. Ara, si hi ha quota, fem
    una crida al generador socràtic adaptat al reforç.

    Retorna True si s'ha generat alguna pista; False si la quota era
    plena o hi ha hagut error tècnic. En cas de fallada amb quota
    disponible, l'invocador pot decidir si fer fallback a l'explicació
    canònica.
    """
    state = st.session_state.tutor
    pre_id = state["active_prereq"]
    if pre_id is None:
        return False
    pre = PB.PREREQUISITES[pre_id]

    if _api_quota_exhausted():
        _push_quota_exhausted_warning()
        return False

    last_answer, last_reason = _last_non_correct_prereq_answer(pre_id)
    prior_hints = list(state["prereq_hints"])

    _consume_api_quota()
    try:
        with st.spinner("Generant pista del reforç..."):
            hint = L.generate_prereq_hint(
                pre,
                student_answer=last_answer,
                judge_reason=last_reason,
                prior_hints=prior_hints,
            )
        _push("hint", f"💡 {hint}")
        state["prereq_hints"].append(hint)
        state["history"].append({
            "type": "hint",
            "scope": "prereq",
            "prereq_id": pre_id,
            "text": hint,
            "had_student_context": last_answer is not None,
            "n_prior_hints": len(prior_hints),
            "ts": time.time(),
        })
        return True
    except Exception:
        _push("warning",
              "⚠️ No s'ha pogut generar la pista del reforç. "
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
        # Dins de prereq, abans empenyíem l'explicació canònica completa
        # — això revelava la distinció demanada i invalidava la idea
        # socràtica del reintent. Ara generem una pista adaptada
        # (Proposta 3). Si la quota està plena, fallback a l'explicació
        # canònica (no cal IA per a aquest text).
        if state["active_prereq"] is not None:
            if _api_quota_exhausted():
                # Fallback gratuït: l'explicació canònica.
                pre = PB.PREREQUISITES[state["active_prereq"]]
                _push("hint", pre["explanation"])
                state["hints_requested"] += 1
            elif _try_generate_prereq_hint():
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
    # Construïm el context de trajectòria de la sessió (Proposta 1).
    judge_context = _build_judge_context(step["id"])

    # Self-consistency selectiva (Proposta 5): si tenim quota per a 2
    # crides, deixem que el judge re-mostregi quan reporta confiança
    # baixa. Si només en queda 1, desactivem el resample per evitar
    # exhaurir la quota a mig torn.
    remaining = MAX_API_CALLS_PER_SESSION - st.session_state.get("api_calls_used", 0)
    allow_resample = (remaining >= 2)

    _consume_api_quota()
    try:
        with st.spinner("Avaluant resposta..."):
            verdict_obj = L.judge_step(
                step, s,
                context=judge_context,
                allow_resample=allow_resample,
            )
    except Exception:
        _push("warning",
              "⚠️ El servei d'avaluació no respon ara mateix. "
              "Torna a enviar la mateixa resposta d'aquí uns segons.")
        return

    # Si hi ha hagut re-mostreig, comptem la segona crida a la quota.
    # (La primera ja s'ha consumit abans.)
    extra_calls = max(0, verdict_obj.get("n_api_calls", 1) - 1)
    for _ in range(extra_calls):
        _consume_api_quota()

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
        "judge_context": judge_context,
        # Metadades de self-consistency (Proposta 5) per a auditoria.
        "confidence": verdict_obj.get("confidence"),
        "resampled": verdict_obj.get("resampled", False),
        "initial_verdict": verdict_obj.get("initial_verdict"),
        "initial_error_label": verdict_obj.get("initial_error_label"),
        "agreement": verdict_obj.get("agreement"),
        "resample_failed": verdict_obj.get("resample_failed", False),
        "n_api_calls": verdict_obj.get("n_api_calls", 1),
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
        # Si hi ha un reforç actiu, mostrem la seva pregunta de manera
        # persistent perquè l'alumne pugui veure-la durant tota la
        # mini-sessió, inclosos els reintents introduïts a la proposta 2.
        if state["active_prereq"] is not None:
            pre = PB.PREREQUISITES[state["active_prereq"]]
            attempt = state.get("prereq_attempts", 0)
            attempt_label = f" (intent {attempt + 1})" if attempt > 0 else ""
            st.warning(
                f"🔁 **Exercici de reforç{attempt_label}:** "
                f"{pre['question']}"
            )


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
        elif kind == "prereq_feedback":
            # Reintent del reforç: ni èxit ni fallada definitiva.
            # Estil "advertència" perquè l'alumne ha de tornar a respondre.
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
                # Metadades de self-consistency (Proposta 5): mostrem
                # confiança i, si hi ha hagut re-mostreig, si els dos
                # samples coincidien.
                conf = h.get("confidence")
                conf_str = f" · conf={conf}" if conf else ""
                if h.get("resampled"):
                    init = h.get("initial_verdict", "?")
                    agree = h.get("agreement")
                    if agree:
                        rs = f" · re-mostrejat (acord amb {init})"
                    else:
                        rs = f" · re-mostrejat (canvi: {init}→{v})"
                else:
                    rs = ""
                st.markdown(
                    f"**Pas {h.get('step_id')}** — {icon} *{v}*{conf_str}{rs}  \n"
                    f"_Alumne:_ {h.get('student', '')}  \n"
                    f"_IA:_ {h.get('reason', '')}"
                )
            elif t == "prereq":
                # Compatibilitat: format antic feia servir "correct" (bool);
                # format nou (proposta 2) fa servir "verdict" (str de tres
                # valors). Si tots dos hi són, "verdict" mana.
                v = h.get("verdict")
                if v is not None:
                    icon = "✓" if v == "correct" else (
                        "↻" if v == "keyword_only" else "✗"
                    )
                    attempt = h.get("attempt", "?")
                    conf = h.get("confidence")
                    conf_str = f" · conf={conf}" if conf else ""
                    if h.get("resampled"):
                        init = h.get("initial_verdict", "?")
                        agree = h.get("agreement")
                        rs = (f" · re-mostrejat (acord amb {init})"
                              if agree
                              else f" · re-mostrejat (canvi: {init}→{v})")
                    else:
                        rs = ""
                    st.markdown(
                        f"**Prereq {h.get('prereq_id')}** "
                        f"(intent {attempt}) — {icon} *{v}*{conf_str}{rs}  \n"
                        f"_Alumne:_ {h.get('student', '')}  \n"
                        f"_IA:_ {h.get('reason', '')}"
                    )
                else:
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
            elif t == "hint":
                # Entries de pista afegides a la Proposta 3.
                scope = h.get("scope", "step")
                if scope == "prereq":
                    where = f"prereq {h.get('prereq_id', '?')}"
                else:
                    where = f"pas {h.get('step_id', '?')}"
                ctx = "amb context" if h.get("had_student_context") else "sense context"
                auto = " (auto)" if h.get("auto") else ""
                st.markdown(
                    f"**💡 Pista** ({where}, {ctx}){auto}  \n"
                    f"_IA:_ {h.get('text', '')}"
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
