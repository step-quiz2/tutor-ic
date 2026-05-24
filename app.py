"""
app.py — Streamlit UI per al tutor IC (arquitectura Nivell 1).

Substitueix la versió anterior basada en classificadors. La lògica
d'estat (nova sessió, apply_action, compute_quality_signals) ve
directament de `simulator.py` — sense duplicació de codi.

UI:
  - Capçalera fixa amb l'enunciat (sempre visible).
  - Una sola targeta del tutor a la vista, colorada per acció:
      verd     = advance net (sense stays previs al mateix pas)
      groc     = advance amb stays previs o retreat al reforç
      gris     = stay (error conceptual, tutoria en curs)
      bordeus  = sospita que l'alumne està vacil·lant (heurística)
  - Botons 💡 Pista i 🚪 Acabar.
  - Font base +20%.
  - Resum visual final amb mètriques i distribució per pas.

Comporta amb la mateixa rigidesa que el simulador: el reply del tutor
s'afegeix al transcript després de cada crida (bug del simulator
original).
"""

import re
import time

import streamlit as st

import problem as PB
import llm as L
import simulator as S


# =============================================================================
# Configuració
# =============================================================================

st.set_page_config(
    page_title="Tutor d'intervals de confiança",
    page_icon="🎓",
    layout="centered",
)

# Patrons mofa per a la detecció de "vacil·lar". Llista deliberadament
# curta — falsos positius són pitjors que falsos negatius en aquesta
# senyal (un bordeus injustificat amaga el color real).
MOCKERY_PATTERNS = (
    "haha", "jaja", "jeje", "jiji",
    "lol", "xd",
    "patata", "tontain", "tontus",
    "ke pasa", "wtf",
)

# Marca literal que l'app injecta quan l'alumne demana pista.
# Ha de coincidir amb el que espera el system prompt.
HINT_MARKER = "(L'alumne demana una pista)"


# =============================================================================
# CSS
# =============================================================================

CSS = """
<style>
/* Font +20% al contingut principal */
.main .block-container {
    font-size: 1.2rem;
    padding-top: 2rem;
    max-width: 780px;
}
.stMarkdown p, .stMarkdown li { font-size: 1.2rem; line-height: 1.6; }
h1 { font-size: 1.8rem !important; margin-bottom: 1.5rem !important; }

/* Capçalera persistent amb l'enunciat */
.problem-card {
    background: #f0f4f8;
    border-left: 4px solid #1565c0;
    padding: 1rem 1.25rem;
    margin-bottom: 1.75rem;
    border-radius: 6px;
}
.problem-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #1565c0;
    margin-bottom: 0.35rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.problem-text { font-size: 1.05rem; line-height: 1.55; color: #1a2733; }

/* Targeta del tutor */
.tutor-card {
    padding: 1.5rem 1.5rem 1.25rem 1.5rem;
    border-radius: 12px;
    margin: 1.5rem 0;
    border-left: 5px solid;
    line-height: 1.6;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.tutor-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
    font-size: 0.85rem;
    margin-bottom: 0.8rem;
    opacity: 0.75;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.tutor-body { font-size: 1.15rem; }
.tutor-body p { margin: 0.6em 0; }
.tutor-body p:first-child { margin-top: 0; }
.tutor-body p:last-child { margin-bottom: 0; }
.tutor-body blockquote {
    border-left: 3px solid rgba(0,0,0,0.18);
    padding: 0.3rem 0 0.3rem 0.8rem;
    margin: 0.7em 0;
    font-style: italic;
    opacity: 0.88;
}
.tutor-body code {
    background: rgba(0,0,0,0.06);
    padding: 0.1em 0.35em;
    border-radius: 3px;
    font-size: 0.95em;
}
.step-badge {
    display: inline-block;
    padding: 0.15rem 0.55rem;
    background: rgba(0,0,0,0.07);
    color: rgba(0,0,0,0.65);
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-left: auto;
}

/* Colors semàntics */
.tutor-green    { background: #e8f5e9; border-color: #2e7d32; }
.tutor-yellow   { background: #fff8e1; border-color: #ef6c00; }
.tutor-gray     { background: #f5f5f5; border-color: #757575; }
.tutor-bordeaux { background: #fbe9e7; border-color: #8b0000; }
.tutor-neutral  { background: #e3f2fd; border-color: #1976d2; }
.tutor-thinking {
    background: #fafafa;
    border-color: #bdbdbd;
    font-style: italic;
    opacity: 0.85;
}

.stButton button { border-radius: 8px; font-weight: 500; }

/* Resum final */
.summary-header {
    text-align: center;
    padding: 2.5rem 1.5rem;
    margin-bottom: 2rem;
    border-radius: 14px;
}
.summary-header h1 { margin: 0 0 0.5rem 0 !important; font-size: 2rem !important; }
.summary-header p { margin: 0; opacity: 0.85; font-size: 1.1rem; }
.summary-success { background: #e8f5e9; border: 2px solid #2e7d32; color: #1b5e20; }
.summary-neutral { background: #f5f5f5; border: 2px solid #9e9e9e; color: #424242; }
</style>
"""


# =============================================================================
# Helpers: markdown → HTML
# =============================================================================

def simple_md_to_html(text):
    """Conversió minimalista markdown → HTML, suficient per als replies
    típics del tutor (negretes, cursives, codi inline, quotes,
    paràgrafs). Conscientment no usa cap dependència externa."""
    if not text:
        return ""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(
        r"^&gt;\s?(.+)$",
        r"<blockquote>\1</blockquote>",
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

    paragraphs = text.split("\n\n")
    html_parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        p = p.replace("\n", "<br>")
        if p.startswith("<blockquote>"):
            html_parts.append(p)
        else:
            html_parts.append(f"<p>{p}</p>")
    return "\n".join(html_parts)


# =============================================================================
# Helpers: color i posició
# =============================================================================

def is_disengaged(state):
    """Heurística per detectar que l'alumne sembla vacil·lant.

    Triggers:
      - Últim missatge conté algun patró de mofa (haha, patata, etc.)
      - 2 dels últims 3 missatges (no comptant pista) tenen <8 caràcters

    Falsos positius: alumnes que escriuen molt curt per estil. Acceptable
    perquè el bordeus només AFEGEIX informació al professor; no canvia
    el comportament del tutor."""
    history = state.get("history", [])
    if not history:
        return False

    latest_msg = (history[-1].get("student_msg") or "").lower().strip()
    if not latest_msg or latest_msg == HINT_MARKER.lower():
        return False

    if any(p in latest_msg for p in MOCKERY_PATTERNS):
        return True

    if len(history) >= 3:
        recent_msgs = [
            (h.get("student_msg") or "")
            for h in history[-3:]
            if h.get("student_msg") != HINT_MARKER
        ]
        very_short = sum(1 for m in recent_msgs if len(m.strip()) < 8)
        if very_short >= 2:
            return True

    return False


def count_consecutive_stays_in_same_position(history, last_idx):
    """Compta quants 'stay' consecutius hi va haver immediatament abans
    de history[last_idx], a la mateixa posició (step, prereq) que
    history[last_idx]['position_before']. Aïllat per facilitar test."""
    if last_idx < 1:
        return 0
    target_pos = history[last_idx]["position_before"]
    count = 0
    for prev in reversed(history[:last_idx]):
        if prev["action"] != "stay":
            break
        if prev["position_before"] != target_pos:
            break
        count += 1
    return count


def determine_turn_color(state):
    """Retorna la classe CSS de color per a la targeta del tutor del
    torn actual."""
    history = state.get("history", [])
    if not history:
        return "neutral"

    if is_disengaged(state):
        return "bordeaux"

    latest = history[-1]
    action = latest["action"]

    if action == "advance":
        stays_before = count_consecutive_stays_in_same_position(
            history, len(history) - 1
        )
        return "green" if stays_before == 0 else "yellow"

    if action == "retreat_to_prereq":
        return "yellow"

    return "gray"


def position_label(state):
    """Etiqueta curta per al badge de la targeta del tutor."""
    if state.get("finished"):
        return None
    if state.get("active_prereq"):
        return f"Reforç → Pas {state['step_before_prereq']}"
    step = state.get("current_step")
    if step:
        total = len(PB.PROBLEM["passos"])
        return f"Pas {step} de {total}"
    return None


# =============================================================================
# Render: components
# =============================================================================

def render_problem_header():
    html = (
        f'<div class="problem-card">'
        f'<div class="problem-label">Problema</div>'
        f'<div class="problem-text">{simple_md_to_html(PB.PROBLEM["enunciat"])}</div>'
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_tutor_card(text, color, badge=None):
    badge_html = f'<span class="step-badge">{badge}</span>' if badge else ""
    body_html = simple_md_to_html(text)
    html = (
        f'<div class="tutor-card tutor-{color}">'
        f'<div class="tutor-header">'
        f'<span>🎓 Tutor</span>'
        f"{badge_html}"
        f"</div>"
        f'<div class="tutor-body">{body_html}</div>'
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_thinking_card():
    html = (
        '<div class="tutor-card tutor-thinking">'
        '<div class="tutor-header"><span>🎓 Tutor</span></div>'
        '<div class="tutor-body"><p>Pensant…</p></div>'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


# =============================================================================
# Render: vista de conversa
# =============================================================================

def render_chat_view(state):
    """Mostra només el torn actual: cap historial al viewport."""
    render_problem_header()

    latest_tutor = next(
        (t["content"] for t in reversed(state["transcript"])
         if t["role"] == "tutor"),
        None,
    )
    color = determine_turn_color(state)
    badge = position_label(state)

    # st.empty() ens permet substituir el contingut durant la crida
    # LLM amb el placeholder "Pensant…".
    tutor_slot = st.empty()
    with tutor_slot.container():
        render_tutor_card(latest_tutor, color, badge)

    col_hint, col_end = st.columns(2)
    with col_hint:
        hint_clicked = st.button(
            "💡 Demanar pista",
            use_container_width=True,
            key="btn_hint",
        )
    with col_end:
        end_clicked = st.button(
            "🚪 Acabar sessió",
            use_container_width=True,
            key="btn_end",
        )

    user_input = st.chat_input("Escriu la teva resposta…")

    if end_clicked:
        state["finished"] = True
        st.rerun()

    student_msg = None
    if hint_clicked:
        student_msg = HINT_MARKER
    elif user_input:
        student_msg = user_input

    if student_msg is None:
        return

    # Substituïm la targeta amb "Pensant…" abans de la crida.
    with tutor_slot.container():
        render_thinking_card()

    state["transcript"].append({"role": "student", "content": student_msg})
    state["turn_count"] += 1

    try:
        t0 = time.time()
        result = L.tutor_turn(
            PB.PROBLEM,
            S.position_dict(state),
            state["transcript"],
        )
        elapsed = time.time() - t0
    except Exception as exc:
        st.error(
            f"Error tècnic en cridar el model: {type(exc).__name__}: {exc}"
        )
        state["transcript"].pop()
        state["turn_count"] -= 1
        st.stop()

    # CRÍTIC: afegir el reply al transcript abans del següent torn.
    # (Bug original del simulator que el sistema arrastrava.)
    state["transcript"].append({"role": "tutor", "content": result["reply"]})

    position_before = {
        "step": state["current_step"],
        "prereq": state["active_prereq"],
    }
    S.apply_action(state, result["action"])
    position_after = {
        "step": state["current_step"],
        "prereq": state["active_prereq"],
    }
    state["history"].append({
        "turn": state["turn_count"],
        "ts": time.time(),
        "student_msg": student_msg,
        "tutor_reply": result["reply"],
        "action": result["action"],
        "objectives_met": result["objectives_met"],
        "control_parse_ok": result["control_parse_ok"],
        "position_before": position_before,
        "position_after": position_after,
        "elapsed_seconds": elapsed,
    })

    st.rerun()


# =============================================================================
# Render: vista de resum
# =============================================================================

def render_summary_view(state):
    qs = state.get("quality_signals") or S.compute_quality_signals(state)

    if qs["completed"]:
        title = "🎉 Sessió completada"
        s = "s" if qs["total_turns_llm"] != 1 else ""
        subtitle = f"Has acabat el problema en {qs['total_turns_llm']} torn{s}."
        header_class = "summary-success"
    else:
        title = "Sessió finalitzada"
        s = "s" if qs["total_turns_llm"] != 1 else ""
        subtitle = f"Has fet {qs['total_turns_llm']} torn{s} abans d'acabar."
        header_class = "summary-neutral"

    st.markdown(
        f'<div class="summary-header {header_class}">'
        f"<h1>{title}</h1>"
        f"<p>{subtitle}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Torns LLM", qs["total_turns_llm"])
    with col2:
        secs = int(qs["elapsed_seconds_total"])
        label = f"{secs // 60}m {secs % 60}s" if secs >= 60 else f"{secs}s"
        st.metric("Durada", label)
    with col3:
        ratio = qs["stay_advance_ratio"]
        label = f"{ratio:.2f}" if ratio is not None else "—"
        st.metric(
            "Stays / advance",
            label,
            help="Quants torns d'insistència per cada avenç (menor = més fluït).",
        )

    st.markdown("---")

    st.markdown("### Distribució de torns")
    tps = qs["turns_per_step"]
    max_count = max(list(tps.values()) + [qs["turns_in_prereq"]] + [1])

    for step in sorted(tps.keys()):
        count = tps[step]
        if count == 0:
            st.markdown(f"**Pas {step}** — cap torn")
        else:
            s = "s" if count != 1 else ""
            st.markdown(f"**Pas {step}** — {count} torn{s}")
            st.progress(count / max_count)

    if qs["used_prereq"]:
        s = "s" if qs["turns_in_prereq"] != 1 else ""
        st.markdown(f"**Reforç PRE-PARAM** — {qs['turns_in_prereq']} torn{s}")
        st.progress(qs["turns_in_prereq"] / max_count)

    st.markdown("---")

    st.markdown("### Senyals")
    col_a, col_b = st.columns(2)
    with col_a:
        ac = qs["action_counts"]
        st.markdown(
            "**Decisions del tutor**\n\n"
            f"- ✅ Avenços: **{ac['advance']}**\n"
            f"- ⏸️ Stays: **{ac['stay']}**\n"
            f"- 📘 Retreats: **{ac['retreat_to_prereq']}**"
        )
    with col_b:
        notes = []
        if qs["hint_requests"]:
            notes.append(f"💡 {qs['hint_requests']} sol·licituds de pista")
        if qs["used_prereq"]:
            notes.append(f"📘 Reforç actiu durant {qs['turns_in_prereq']} torns")
        if qs["parse_failures"]:
            notes.append(
                f"⚠ {qs['parse_failures']} falles tècniques del control block"
            )
        if not notes:
            notes.append("✓ Cap incidència destacada.")
        st.markdown(
            "**Esdeveniments**\n\n" + "\n".join(f"- {n}" for n in notes)
        )

    st.markdown("---")

    col_new, _ = st.columns([1, 1])
    with col_new:
        if st.button(
            "🔄 Iniciar nova sessió",
            use_container_width=True,
            key="btn_new",
        ):
            st.session_state.clear()
            st.rerun()

    with st.expander("📜 Veure transcripció completa"):
        for turn in state["transcript"]:
            role = "🎓 Tutor" if turn["role"] == "tutor" else "👤 Alumne"
            st.markdown(f"**{role}**")
            st.markdown(turn["content"])
            st.markdown("")


# =============================================================================
# Main
# =============================================================================

def main():
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("Tutor d'intervals de confiança")

    if "state" not in st.session_state:
        st.session_state.state = S.new_session()

    state = st.session_state.state

    if state.get("finished"):
        if "quality_signals" not in state:
            state["quality_signals"] = S.compute_quality_signals(state)
        render_summary_view(state)
    else:
        render_chat_view(state)


if __name__ == "__main__":
    main()
