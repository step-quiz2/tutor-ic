"""
app.py · Interfície Streamlit del Tutor de Divisibilitat (arquitectura v2).

Executa amb:   streamlit run app.py

Flux de cada torn (igual que els tutors germans):
  1. afegim el missatge de l'alumne al transcript,
  2. cridem llm.tutor_turn amb el transcript del capítol,
  3. si l'API falla, treiem el missatge de l'alumne (per no trencar
     l'alternança) i ho tractem com a incident tècnic, NO com a error,
  4. afegim el reply del tutor al transcript ABANS d'aplicar l'acció,
  5. apliquem l'acció (stay/advance) a la màquina d'estats.

UI (unificada amb el tutor germà `tutor-ic`, Tasca 2):
  - Targetes `.tutor-card` amb DUES capes de color ortogonals:
      · color d'acció (fons/vora): verd = avança, gris = es queda;
      · xip d'origen: 🐍 Python (determinista) vs 🤖 IA (heurística).
    Les bombolles deterministes que posa Python (obertures de capítol,
    pregunta canònica del pas nou, missatge final) porten l'estil
    `tutor-deterministic` (vora discontínua) per marcar-les com a
    garantides pel sistema.
  - Llegenda de les dues capes al capdamunt de la conversa.
  - Panell inspector "Com pensa el tutor" a la barra lateral (Tasca 1),
    que mostra la decisió determinista del darrer torn i consolida el
    contingut de `?debug=1`.
"""

from __future__ import annotations

import re

import streamlit as st

import llm
import problems
import tutor


def _query_flag(name, default=False):
    """Llegeix un flag booleà de la URL de manera defensiva.

    Convenció: `?name=1` → True, `?name=0` → False. Si el paràmetre no hi és
    (o no podem llegir query_params, p. ex. amb un stub de test), es retorna
    `default`. No peta mai a l'import.
    """
    try:
        qp = st.query_params
        getter = getattr(qp, "get", None)
        if callable(getter):
            val = getter(name)
            if val is None:
                return default
            return str(val) == "1"
    except Exception:
        pass
    return default


# Mode docent: ACTIU PER DEFECTE. El panell de senyals (sempre visible, al
# costat de la conversa) és la vista per a demostracions davant professorat.
# Per a una sessió amb alumnes cal desactivar-lo EXPLÍCITAMENT amb ?docent=0
# a la URL: així els codis de malentesa (MUL_direccio, PRIME_imparell, etc.)
# — vocabulari de docent — no es mostren a l'alumne i l'experiència socràtica
# queda intacta. El layout és "wide" en mode docent (hi cap la segona columna)
# i "centered" en mode alumne.
DOCENT_MODE = _query_flag("docent", default=True)

st.set_page_config(page_title="Tutor de Divisibilitat", page_icon="➗",
                   layout="wide" if DOCENT_MODE else "centered")

# =============================================================================
# CSS — sistema de targetes portat del tutor germà (tutor-ic), més els
# elements propis de div (barra de progrés, mides de font). Copiat gairebé
# literal perquè els dos tutors es vegin com una sola família de producte.
# =============================================================================

st.markdown(
    """
    <style>
    .block-container { max-width: 780px; }
    .stChatInput textarea { font-size: 1.2rem !important; }
    h1 { font-size: 1.65rem !important; }
    h2 { color: #1f4e79; font-size: 1.35rem !important; margin-top: 0 !important; }
    p, li, label, .stMarkdown { font-size: 1.12rem; }

    /* Barra de progrés (pròpia de div, es conserva) */
    .barra { background:#eef2f7; border-radius:10px; height:12px;
             overflow:hidden; margin:4px 0 10px 0; }
    .barra > div { background:linear-gradient(90deg,#4f8df9,#6fc3a0); height:100%; }
    .petit { color:#6b7280; font-size:1.0rem; }

    /* ── Targeta del tutor (capa de color d'ACCIÓ pedagògica) ───────────── */
    .tutor-card {
        padding: 1.3rem 1.5rem 1.1rem 1.5rem;
        border-radius: 12px;
        margin: 1.2rem 0;
        border-left: 5px solid;
        line-height: 1.6;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .tutor-header {
        display: flex; align-items: center; gap: 0.5rem;
        font-weight: 600; font-size: 0.85rem; margin-bottom: 0.7rem;
        opacity: 0.75; text-transform: uppercase; letter-spacing: 0.05em;
    }
    .tutor-body { font-size: 1.1rem; }
    .tutor-body p { margin: 0.6em 0; }
    .tutor-body p:first-child { margin-top: 0; }
    .tutor-body p:last-child { margin-bottom: 0; }
    .tutor-body h2 { margin: 0 0 0.5rem 0; }
    .tutor-body code {
        background: rgba(0,0,0,0.06); padding: 0.1em 0.35em;
        border-radius: 3px; font-size: 0.95em;
    }
    .tutor-body blockquote {
        border-left: 3px solid rgba(0,0,0,0.18);
        padding: 0.3rem 0 0.3rem 0.8rem; margin: 0.7em 0;
        font-style: italic; opacity: 0.88;
    }

    /* Colors semàntics (acció pedagògica). Mateixos valors que tutor-ic. */
    .tutor-green    { background: #e8f5e9; border-color: #2e7d32; }
    .tutor-yellow   { background: #fff8e1; border-color: #ef6c00; }
    .tutor-gray     { background: #f5f5f5; border-color: #757575; }
    .tutor-neutral  { background: #e3f2fd; border-color: #1976d2; }

    /* Targeta determinista: text posat per Python (no pel model). Blau
       pissarra amb vora discontínua → "això ho garanteix el sistema". */
    .tutor-deterministic {
        background: #eef2f7; border-color: #334e68; border-left-style: dashed;
    }

    /* Targeta de l'alumne */
    .student-card {
        padding: 0.9rem 1.2rem; border-radius: 12px; margin: 1.2rem 0 1.2rem auto;
        background: #f3f4f6; border-right: 5px solid #9ca3af;
        max-width: 85%; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .student-header {
        font-weight: 600; font-size: 0.85rem; margin-bottom: 0.4rem;
        opacity: 0.7; text-transform: uppercase; letter-spacing: 0.05em;
        text-align: right;
    }

    /* Xips d'origen: capa ORTOGONAL al color d'acció. Diu QUI ha generat
       la bombolla — codi determinista (Python) o model estocàstic (IA). */
    .source-chip {
        display: inline-flex; align-items: center; gap: 0.3rem;
        padding: 0.1rem 0.5rem; border-radius: 999px;
        font-size: 0.72rem; font-weight: 700; letter-spacing: 0.03em;
        text-transform: none; margin-left: 0.5rem;
    }
    .chip-py { background: #d1e3f8; color: #1a3c5e; border: 1px solid #7fa8d4; }
    .chip-ai { background: #ede7f6; color: #4527a0; border: 1px solid #b39ddb; }

    /* Llegenda de les dues capes de color */
    .layer-legend {
        display: flex; flex-wrap: wrap; gap: 0.75rem;
        font-size: 0.82rem; color: rgba(0,0,0,0.6);
        margin: 0.2rem 0 1.0rem 0; align-items: center;
    }
    .layer-legend .lg { display: inline-flex; align-items: center; gap: 0.35rem; }
    .layer-legend .sw {
        width: 0.85rem; height: 0.85rem; border-radius: 3px;
        border: 1px solid rgba(0,0,0,0.25); display: inline-block;
    }

    /* Panell inspector (Tasca 1) a la barra lateral */
    .inspector-row {
        display: flex; align-items: center; gap: 0.45rem;
        font-size: 0.9rem; margin: 0.35rem 0 0.5rem 0;
    }
    .inspector-row .sw {
        width: 0.9rem; height: 0.9rem; border-radius: 3px;
        border: 1px solid rgba(0,0,0,0.25); display: inline-block; flex: none;
    }
    .inspector-row .act-code {
        margin-left: auto; background: rgba(0,0,0,0.06);
        padding: 0.05rem 0.4rem; border-radius: 4px; font-size: 0.82rem;
    }
    .inspector-line { font-size: 0.86rem; color: rgba(0,0,0,0.68); margin: 0.3rem 0; }
    .inspector-line code {
        background: rgba(0,0,0,0.06); padding: 0.03em 0.32em;
        border-radius: 3px; font-size: 0.95em;
    }
    .inspector-warn { color: #8b0000; font-weight: 600; }
    .inspector-muted { color: rgba(0,0,0,0.45); }
    /* Capçalera del panell de senyals sempre visible (mode docent) i la
       tesi, que es diu UN sol cop (no a cada torn), en gris discret. */
    .signals-title {
        font-weight: 700; font-size: 1.0rem; color: #1f4e79;
        margin: 0 0 0.5rem 0;
    }
    .signals-title .signals-sub {
        font-weight: 500; font-size: 0.78rem; color: rgba(0,0,0,0.45);
    }
    .signals-thesis {
        font-size: 0.74rem; color: rgba(0,0,0,0.5);
        margin: 0.1rem 0 0.7rem 0; line-height: 1.5;
        border-bottom: 1px solid rgba(0,0,0,0.08); padding-bottom: 0.6rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Ajustos de layout NOMÉS en mode docent ─────────────────────────────────
# Objectiu: donar més amplada a la conversa i al panell de senyals. El panell
# ja no marxa de la vista perquè ara la conversa només mostra el torn actual
# (columna curta), així que no cal cap truc de posicionament. (En mode alumne
# no hi ha panell ni columnes, així que aquests retocs no s'apliquen.)
if DOCENT_MODE:
    st.markdown(
        """
        <style>
        /* Barra lateral ~20% més estreta (només conté estat i controls). */
        section[data-testid="stSidebar"] {
            width: 17rem !important;
            min-width: 17rem !important;
            max-width: 17rem !important;
        }
        /* Aprofitem tota l'amplada i reduïm la separació esquerra/dreta. */
        .block-container {
            max-width: 100% !important;
            padding-left: 3rem !important;
            padding-right: 2.5rem !important;
        }
        /* Menys espai vertical entre bombolles (~-20%). */
        .tutor-card   { margin: 0.95rem 0 !important; }
        .student-card { margin: 0.95rem 0 0.95rem auto !important; }
        [data-testid="stVerticalBlock"] { gap: 0.8rem !important; }
        /* Menys separació entre la conversa i el panell de senyals. */
        [data-testid="stHorizontalBlock"] { gap: 1.6rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# Helpers de presentació (portats de tutor-ic; markdown amb suport
# d'encapçalaments perquè les obertures de capítol "## …" es vegin bé)
# =============================================================================

def simple_md_to_html(text):
    """Conversió minimalista markdown → HTML (negretes, cursives, codi
    inline, quotes, encapçalaments, paràgrafs). Sense dependències externes.
    És el mateix helper que tutor-ic, ampliat amb `#`/`##`/`###` perquè les
    obertures de capítol de div (que comencen amb `##`) es renderitzin com a
    títol també dins la targeta."""
    if not text:
        return ""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"^###\s+(.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+(.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^#\s+(.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
    text = re.sub(r"^&gt;\s?(.+)$", r"<blockquote>\1</blockquote>",
                  text, flags=re.MULTILINE)
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
        if p.startswith("<blockquote>") or p.startswith("<h"):
            html_parts.append(p)
        else:
            html_parts.append(f"<p>{p}</p>")
    return "\n".join(html_parts)


def _source_chip(source):
    """HTML del xip d'origen (capa ortogonal al color d'acció)."""
    if source == "py":
        return '<span class="source-chip chip-py">🐍 Python · determinista</span>'
    if source == "ai":
        return '<span class="source-chip chip-ai">🤖 IA · heurística</span>'
    return ""


# Color d'acció pedagògica de div. div no té retrocés (retreat), per tant
# no fa servir el groc: només verd (avança) i gris (es queda).
DIV_ACTION_COLOR = {"advance": "green", "stay": "gray"}

DIV_ACTION_LABELS = {"advance": "avança", "stay": "es queda"}

# Color (fons, vora) de cada classe semàntica — EXACTAMENT els valors de les
# regles .tutor-* del CSS, perquè el swatch de l'inspector coincideixi amb la
# targeta del tutor del mateix torn.
ACTION_SWATCH = {
    "green": ("#e8f5e9", "#2e7d32"),
    "yellow": ("#fff8e1", "#ef6c00"),
    "gray": ("#f5f5f5", "#757575"),
    "neutral": ("#e3f2fd", "#1976d2"),
}


def _render_tutor_card(content, color, source, deterministic=False):
    """Renderitza una bombolla del tutor com a targeta amb color d'acció
    (o estil determinista) i xip d'origen."""
    body = simple_md_to_html(content)
    chip = _source_chip(source)
    cls = "tutor-deterministic" if deterministic else f"tutor-{color}"
    html = (
        f'<div class="tutor-card {cls}">'
        f'<div class="tutor-header"><span>🎓 Tutor</span>{chip}</div>'
        f'<div class="tutor-body">{body}</div>'
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_student_card(content):
    """Bombolla de l'alumne (estil propi de div; el germà ic no en mostra
    perquè només ensenya el clúster del tutor del torn actual)."""
    body = simple_md_to_html(content)
    html = (
        '<div class="student-card">'
        '<div class="student-header">👤 Alumne</div>'
        f'<div class="tutor-body">{body}</div>'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def bubble_style(m):
    """Decideix l'estil d'una bombolla de tutor del `display`. Funció PURA
    (sense Streamlit) per poder-se testejar. Retorna
    (color, source, deterministic):

      - Bombolla amb clau `action` → bombolla de RESPOSTA (model o reserva):
        color d'acció (advance→verd, stay→gris); el xip d'origen és ortogonal.
      - Bombolla sense `action` → bombolla ESTRUCTURAL determinista posada per
        Python (obertura, pregunta canònica, missatge final): estil
        determinista (vora discontínua), xip 🐍 Python.
    """
    source = m.get("source", "ai")
    if "action" in m:
        return DIV_ACTION_COLOR.get(m["action"], "neutral"), source, False
    return "deterministic", source, True


def render_layer_legend():
    """Llegenda de les DUES capes: acció pedagògica + origen. Semàntica
    idèntica a la del germà ic (els colors signifiquen el mateix); div no
    fa servir el groc perquè no té retrocés."""
    st.markdown(
        '<div class="layer-legend">'
        '<span class="lg"><b>Acció:</b></span>'
        '<span class="lg"><span class="sw" style="background:#e8f5e9;'
        'border-color:#2e7d32"></span>avança</span>'
        '<span class="lg"><span class="sw" style="background:#f5f5f5;'
        'border-color:#757575"></span>es queda</span>'
        '<span class="lg" style="margin-left:0.6rem">'
        '<span class="source-chip chip-py">🐍 Python</span>'
        '<span class="source-chip chip-ai">🤖 IA</span></span>'
        '</div>',
        unsafe_allow_html=True,
    )


# =============================================================================
# Inspector (Tasca 1): "Com pensa el tutor"
# =============================================================================

def _position_summary_div(pos):
    """Etiqueta curta d'una posició {capitol, pas} per a les transicions."""
    if not pos:
        return "—"
    c = pos.get("capitol")
    p = pos.get("pas")
    if c is None or p is None:
        return "—"
    return f"cap. {c} · pas {p}"


def inspector_snapshot_div(state):
    """Resum del darrer torn per al panell inspector. Funció PURA (sense
    Streamlit): només LLEGEIX state['history'] i deriva la posició posterior
    de l'estat viu (per al torn més recent, l'estat actual ÉS l'estat
    post-acció). No muta res. Retorna None si encara no hi ha torns.

    El color ve del mateix mapatge d'acció que pinta la targeta del tutor,
    de manera que el swatch i la targeta coincideixen sempre."""
    history = state.get("history") or []
    if not history:
        return None
    latest = history[-1]
    action = latest.get("action", "stay")
    color = DIV_ACTION_COLOR.get(action, "neutral")
    parse_ok = latest.get("control_parse_ok", True)
    before = latest.get("position_before") or {}
    after = tutor.position_dict(state)  # estat post-acció del torn més recent
    transition = latest.get("transition")
    diagnostic = latest.get("diagnostic")

    desc = ""
    if diagnostic:
        cap = tutor.capitol_actual(state)
        desc = problems.error_catalog(cap).get(diagnostic, "")

    return {
        "action": action,
        "action_label": DIV_ACTION_LABELS.get(action, action),
        "color": color,
        "swatch": ACTION_SWATCH.get(color, ACTION_SWATCH["neutral"]),
        "parse_ok": bool(parse_ok),
        "before": _position_summary_div(before),
        "after": _position_summary_div(after),
        "transition": transition,
        "diagnostic": diagnostic,
        "diagnostic_desc": desc,
        "n_api_calls": latest.get("n_api_calls"),
    }


def render_inspector(state):
    """Panell de senyals "Com pensa el tutor" (Tasca 1).

    Mostra, torn a torn, només el que CANVIA: l'acció emesa pel model (amb el
    seu color), com ha quedat la posició —que decideix Python, no el model—,
    i, si n'hi ha, la malentesa diagnosticada. La tesi (IA emet l'acció /
    Python decideix la posició) es diu UN sol cop a la capçalera, no a cada
    torn. Llegeix només history/estat; no muta res ni el comportament del
    tutor.

    Visibilitat: es renderitza en MODE DOCENT (actiu per defecte; ?docent=0
    el desactiva). Quan es renderitza, és SEMPRE VISIBLE — sense toggle ni
    plegar. Consolida el `?debug=1`: amb aquest flag, el panell també revela
    el raw_output i el rastre complet."""
    show_debug = _query_flag("debug", default=False)

    st.markdown(
        '<div class="signals-title">🔬 Senyals en directe '
        '<span class="signals-sub">(mode docent)</span></div>'
        '<div class="signals-thesis">🤖 la IA emet l\'acció · '
        "🐍 Python decideix la posició</div>",
        unsafe_allow_html=True,
    )

    snap = inspector_snapshot_div(state)
    if snap is None:
        st.caption("Encara no hi ha cap torn. Els senyals apareixeran "
                   "després de la primera resposta de l'alumne.")
    else:
        bg, border = snap["swatch"]
        st.markdown(
            f'<div class="inspector-row">'
            f'<span class="sw" style="background:{bg};border-color:{border}"></span>'
            f'<b>Acció: {snap["action_label"]}</b>'
            f"</div>",
            unsafe_allow_html=True,
        )
        trans_html = (
            f' <span class="inspector-muted">({snap["transition"]})</span>'
            if snap["transition"] else ""
        )
        st.markdown(
            f'<div class="inspector-line">Posició: '
            f'<code>{snap["before"]}</code> → <code>{snap["after"]}</code>'
            f"{trans_html}</div>",
            unsafe_allow_html=True,
        )
        if not snap["parse_ok"]:
            st.markdown(
                '<div class="inspector-line inspector-warn">'
                "⚠ El control block no s'ha pogut llegir; s'ha aplicat "
                "<code>stay</code> per defecte.</div>",
                unsafe_allow_html=True,
            )
        if snap["diagnostic"]:
            desc = snap["diagnostic_desc"]
            desc_html = (
                f' — <span class="inspector-muted">{desc}</span>' if desc else ""
            )
            st.markdown(
                f'<div class="inspector-line">Malentesa: '
                f'<code>{snap["diagnostic"]}</code>{desc_html}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="inspector-line inspector-muted">'
                "Sense malentesa registrada (l'alumne va per bon camí).</div>",
                unsafe_allow_html=True,
            )

    # Capa de depuració: només amb ?debug=1. Revela el raw_output i el rastre
    # complet, consolidant l'antic expander dins d'aquest mateix inspector.
    if show_debug:
        with st.expander("🔧 Traça completa (debug)"):
            st.json({
                "cap_idx": state["cap_idx"], "pas_idx": state["pas_idx"],
                "finished": state["finished"], "turn_count": state["turn_count"],
                "transcript_len": len(state["transcript"]),
            })
            st.write("Últim raw_output:")
            st.code(state.get("last_raw_output") or "(cap)")
            st.write("Rastre:")
            st.json(state["history"])


# ───────────────────────────── estat de sessió ────────────────────────── #

if "state" not in st.session_state:
    st.session_state.state = None  # None = encara no s'ha començat


def reinicia():
    st.session_state.state = None


# ─────────────────────────────── sidebar ──────────────────────────────── #

with st.sidebar:
    if llm.ia_disponible():
        st.success(f"IA connectada ✓ ({llm.MODEL})")
    else:
        st.warning(
            "Sense `GEMINI_API_KEY`: mode de **reserva** (avaluació "
            "senzilla, sense IA). Defineix la variable d'entorn i recarrega "
            "per a l'experiència completa."
        )

    state = st.session_state.state
    if state is not None:
        st.divider()
        if state["finished"]:
            st.success("Tots els capítols completats! 🎉")
        else:
            cap = tutor.capitol_actual(state)
            pas_num = state["pas_idx"] + 1
            total_passos = len(cap["passos"])
            frac = (state["cap_idx"] + (pas_num - 1) / total_passos) / tutor.total_capitols()
            st.markdown(
                f"**Capítol {state['cap_idx']+1}/{tutor.total_capitols()}** · "
                f"pregunta {pas_num}/{total_passos}"
            )
            st.markdown(
                f'<div class="barra"><div style="width:{frac*100:.0f}%"></div></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<span class="petit">{cap["emoji"]} {cap["titol"]}</span>',
                unsafe_allow_html=True,
            )

    st.divider()
    if st.button("🔄 Tornar a començar", use_container_width=True):
        reinicia()
        st.rerun()

    with st.expander("Com funciona?"):
        st.markdown(
            "- El tutor et fa preguntes i tu respons al quadre de baix.\n"
            "- No et donarà la solució: t'ajudarà amb **pistes**.\n"
            "- Si et quedes encallat, prem **💡 Pista**.\n"
            "- Pots equivocar-te tantes vegades com calgui."
        )


# ─────────────────────────────── capçalera ────────────────────────────── #

st.title("Tutor de Divisibilitat")


# ─────────────────────────── pantalla d'inici ─────────────────────────── #

if st.session_state.state is None:
    st.info(tutor.MISSATGE_BENVINGUDA)
    if st.button("🚀 Comença", type="primary", use_container_width=True):
        st.session_state.state = tutor.new_session()
        st.rerun()
    st.stop()

state = st.session_state.state


# ─────────────────────────── historial del xat ────────────────────────── #

def _trailing_tutor_cluster(state):
    """Bombolles del tutor des de l'últim torn de l'alumne fins al final del
    display. Normalment: la resposta del model + (si Python ha avançat)
    l'enunciat canònic del pas nou; a l'obertura, el missatge d'obertura del
    capítol. Igual que fa tutor-ic: mostrem NOMÉS el torn actual, no tot
    l'historial, perquè la columna no creixi i el panell de senyals es
    mantingui sempre a la vista sense necessitat de cap truc."""
    cluster = []
    for m in reversed(state["display"]):
        if m["role"] == "student":
            break
        cluster.append(m)
    cluster.reverse()
    return [m for m in cluster if m["role"] == "tutor"]


def _render_current_turn():
    """Pinta la llegenda de capes i NOMÉS el clúster de tutor del torn actual
    (vegeu _trailing_tutor_cluster). Substitueix el render de tot l'historial
    perquè div es comporti com ic: la conversa no s'acumula en pantalla."""
    render_layer_legend()
    for m in _trailing_tutor_cluster(state):
        # L'estil (color d'acció vs. determinista, xip d'origen) el decideix
        # la funció pura `bubble_style`, fàcil de testejar sense Streamlit.
        color, source, deterministic = bubble_style(m)
        _render_tutor_card(m["content"], color=color, source=source,
                           deterministic=deterministic)


# En mode docent: conversa a l'esquerra, panell de senyals a la dreta. Com que
# ara només pintem el torn actual, la columna és curta i el panell no marxa de
# la vista. En mode alumne: conversa a tota amplada, sense panell.
if DOCENT_MODE:
    _col_conv, _col_signals = st.columns([2, 1], gap="large")
    with _col_conv:
        _render_current_turn()
    with _col_signals:
        with st.container(border=True):
            render_inspector(state)
else:
    _render_current_turn()


# ─────────────────────────── processament d'un torn ───────────────────── #

def processa(text_alumne: str):
    state = st.session_state.state
    tutor.add_student(state, text_alumne)

    try:
        result = llm.tutor_turn(
            tutor.capitol_actual(state),
            tutor.position_dict(state),
            state["transcript"],
            cap_total=tutor.total_capitols(),
        )
    except Exception as e:
        # Incident tècnic: treiem el torn de l'alumne perquè el transcript
        # no quedi amb dos torns 'student' seguits al reintent.
        tutor.pop_last_student(state)
        st.error(
            "Ui, ara mateix no em puc connectar a la IA 😅. "
            f"Torna-ho a provar d'aquí un moment.\n\n_({e})_"
        )
        return

    # font determinista (py) si ha respost el mode de reserva; si no, IA (ai).
    font = "py" if result.get("mode") == "py" or result["n_api_calls"] == 0 else "ai"
    tutor.add_tutor(state, result["reply"], source=font)  # ABANS d'aplicar l'acció
    # Capa de presentació (Tasca 2): desem l'acció d'aquest torn a la bombolla
    # de resposta perquè la UI la pinti amb el color d'acció (verd=avança,
    # gris=es queda). Només marca la bombolla de display; el transcript NO es
    # toca, i les bombolles estructurals (py) no porten aquesta clau.
    state["display"][-1]["action"] = result["action"]
    state["turn_count"] += 1
    state["last_raw_output"] = result["raw_output"]
    pos_abans = tutor.position_dict(state)

    trans = tutor.apply_action(state, result["action"])

    if trans == "seguent_pas":
        # El model (o el mode de reserva) NO inclou la pregunta del pas nou:
        # Python la mostra com a bombolla determinista pròpia, sempre.
        pas = tutor.pas_actual(state)
        q_canonica = f"**PREGUNTA.** {pas['pregunta']}"
        tutor.enrich_last_tutor(state, q_canonica)

    if trans == "fi":
        tutor.add_tutor(state, tutor.MISSATGE_FINAL, source="py")

    state["history"].append({
        "position_before": pos_abans,
        "action": result["action"],
        "diagnostic": result.get("diagnostic"),
        "transition": trans,
        "control_parse_ok": result["control_parse_ok"],
        "n_api_calls": result["n_api_calls"],
    })


# ─────────────────────────── entrada de l'alumne ──────────────────────── #

if not state["finished"]:
    col1, col2 = st.columns([4, 1])
    with col2:
        demana_pista = st.button("💡 Pista", use_container_width=True)
    with col1:
        acabar = st.button("🚪 Acabar", use_container_width=True)

    if demana_pista:
        with st.spinner("En Pitàgores prepara una pista…"):
            processa(tutor.PISTA_MARKER)
        st.rerun()

    if acabar:
        state["finished"] = True
        st.rerun()

    entrada = st.chat_input("Escriu la teva resposta aquí…")
    if entrada:
        with st.spinner("En Pitàgores hi està pensant…"):
            processa(entrada)
        st.rerun()
else:
    st.success("Has acabat. Prem «Tornar a començar» per repetir-ho. 🎉")
