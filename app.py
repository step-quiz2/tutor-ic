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

def _query_flag(name):
    """Llegeix un flag de la URL (?name=1) de manera defensiva. Streamlit
    real exposa st.query_params amb .get(); alguns stubs de test no, així
    que tolerem qualsevol forma i caiem a False sense petar a l'import."""
    try:
        qp = st.query_params
        getter = getattr(qp, "get", None)
        if callable(getter):
            return getter(name) == "1"
    except Exception:
        pass
    return False


# Mode docent: s'activa de manera estable amb ?docent=1 a la URL. En aquest
# mode l'app mostra un panell de senyals SEMPRE VISIBLE (no plegable, sense
# toggle) al costat de la conversa, per a demostracions davant professorat.
# Els senyals (acció stay/advance, codi de malentesa, origen IA/Python) són
# vocabulari de docent: els alumnes (URL normal) no els veuen mai i mantenen
# l'experiència socràtica intacta. El layout passa a "wide" només en docent
# perquè hi càpiga la segona columna; en mode alumne queda "centered".
DOCENT_MODE = _query_flag("docent")

st.set_page_config(
    page_title="Tutor d'estadística",
    page_icon="🎓",
    layout="wide" if DOCENT_MODE else "centered",
    initial_sidebar_state="expanded",
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

# Comandes de sortida heretades del CLI (simulator.py). A la UI de Streamlit
# NO són un mecanisme real — el tancament es fa amb el botó "🚪 Acabar sessió".
# Però alumnes (i el propi model, si el prompt en parla) poden escriure-les.
# Les interceptem aquí i les tractem com el botó Acabar, perquè MAI arribin al
# model com si fossin una resposta de l'alumne (evita el bucle "escriu !! per
# tancar" → l'alumne escriu !! → no passa res → el tutor hi torna a insistir).
EXIT_COMMANDS = {"!!", "/quit", "/exit"}


def is_exit_command(text):
    """True si `text` és una comanda de sortida heretada del CLI (només la
    comanda, tolerant espais). Aïllat de Streamlit per poder-se testejar."""
    return isinstance(text, str) and text.strip() in EXIT_COMMANDS


# =============================================================================
# CSS
# =============================================================================

CSS = """
<style>
/* Amaga la barra superior de Streamlit (3 puntets, hamburguesa, etc.)
   i el peu "Made with Streamlit". Recupera l'espai vertical que es
   menjaven. */
header[data-testid="stHeader"] { display: none; }
#MainMenu { display: none; }
footer { display: none; }

/* Reducció agressiva del marge superior: Streamlit afegeix padding al
   block-container, marge a l'h1, i un decorador d'app pintat al damunt.
   Cal atacar-ho a tres llocs. */
.stApp > [data-testid="stDecoration"] { display: none; }
.main .block-container {
    font-size: 1.08rem;
    padding-top: 0.5rem !important;
    max-width: 780px;
}
.stMarkdown p, .stMarkdown li { font-size: 1.08rem; line-height: 1.6; }
h1 {
    font-size: 1.65rem !important;
    margin-top: 0 !important;
    padding-top: 0 !important;
    margin-bottom: 1.2rem !important;
}

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
.tutor-body { font-size: 1.05rem; }
.tutor-body p { margin: 0.6em 0; }
.tutor-body p:first-child { margin-top: 0; }
.tutor-body p:last-child { margin-bottom: 0; }
.pregunta-label {
    font-weight: 700;
    font-size: 1.05rem;
    margin: 0 0 0.8rem 0;
    color: rgba(0,0,0,0.78);
}
.page-suffix {
    margin: 0.8rem 0 0 0;
    font-size: 0.78rem;
    font-style: italic;
    color: rgba(0,0,0,0.45);
    text-align: right;
}
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

/* Colors semàntics (acció pedagògica) */
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

/* Targeta determinista: enunciat posat per Python (no pel model).
   Color sobri i diferent dels semàntics d'acció: blau pissarra amb
   vora discontínua, perquè es llegeixi "això ho garanteix el sistema". */
.tutor-deterministic {
    background: #eef2f7;
    border-color: #334e68;
    border-left-style: dashed;
}

/* Xips d'origen: capa ortogonal al color d'acció. Diu QUI ha generat
   la bombolla — codi determinista (Python) o model estocàstic (IA). */
.source-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: none;
    margin-left: 0.5rem;
}
.chip-py { background: #d1e3f8; color: #1a3c5e; border: 1px solid #7fa8d4; }
.chip-ai { background: #ede7f6; color: #4527a0; border: 1px solid #b39ddb; }

/* Llegenda de les dues capes de color */
.layer-legend {
    display: flex; flex-wrap: wrap; gap: 0.75rem;
    font-size: 0.78rem; color: rgba(0,0,0,0.6);
    margin: 0.2rem 0 1.0rem 0; align-items: center;
}
.layer-legend .lg { display: inline-flex; align-items: center; gap: 0.35rem; }
.layer-legend .sw {
    width: 0.85rem; height: 0.85rem; border-radius: 3px;
    border: 1px solid rgba(0,0,0,0.25); display: inline-block;
}
.ia-status {
    font-size: 0.8rem; padding: 0.35rem 0.7rem; border-radius: 8px;
    margin-bottom: 0.8rem; display: inline-block;
}
.ia-ok   { background: #e8f5e9; color: #1b5e20; border: 1px solid #66bb6a; }
.ia-warn { background: #fff3e0; color: #7c4a03; border: 1px solid #ffb74d; }

.stButton button { border-radius: 8px; font-weight: 500; }

/* La barra lateral (columna d'accions) ha d'estar SEMPRE desplegada: amaguem
   el botó "<<" de plegar i qualsevol control de re-obrir. Combinat amb
   initial_sidebar_state="expanded", la columna no es pot compactar mai.
   Inofensiu si el testid no existeix en aquesta versió. */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] { display: none !important; }

/* La columna d'accions ocupa l'amplada MÍNIMA: s'encongeix fins a encabir els
   botons amb el text en una sola línia, sense espai sobrant. Cal anul·lar el
   min-width per defecte de Streamlit (si no, no es deixaria estrènyer) i
   posar els botons a amplada de contingut amb nowrap perquè no saltin de
   línia. max-width és només un sostre de seguretat. */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div:first-child,
section[data-testid="stSidebar"] [data-testid="stSidebarContent"],
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    width: fit-content !important;
    min-width: unset !important;
}
section[data-testid="stSidebar"] { max-width: 20rem !important; }
section[data-testid="stSidebar"] .stButton > button {
    width: auto !important;
    white-space: nowrap !important;
}

/* -------------------------------------------------------------------------
   Botons del selector de problema (pantalla inicial).
   Cada botó es pinta pel seu `key` (Streamlit afegeix la classe
   st-key-<key> al contenidor del widget). En repòs, fons fluix i vora
   fina del color; en hover, fons més fort i vora negra més gruixuda.
   box-sizing: border-box evita que el gruix extra de la vora desplaci res.
   ------------------------------------------------------------------------- */
.st-key-pick_IC-001 button,
.st-key-pick_CAUS-001 button {
    box-sizing: border-box;
    transition: background-color 0.12s ease, border-color 0.12s ease,
                border-width 0.12s ease, color 0.12s ease;
}
/* IC-001 → blau fluix */
.st-key-pick_IC-001 button {
    background: #e3f2fd !important;
    color: #0d47a1 !important;
    border: 1.5px solid #90caf9 !important;
}
.st-key-pick_IC-001 button:hover {
    background: #64b5f6 !important;
    color: #0d2c54 !important;
    border: 3px solid #000 !important;
}
/* CAUS-001 → verd fluix */
.st-key-pick_CAUS-001 button {
    background: #e8f5e9 !important;
    color: #1b5e20 !important;
    border: 1.5px solid #a5d6a7 !important;
}
.st-key-pick_CAUS-001 button:hover {
    background: #81c784 !important;
    color: #0d3d12 !important;
    border: 3px solid #000 !important;
}

/* Resum final */
.summary-header {
    text-align: center;
    padding: 2.5rem 1.5rem;
    margin-bottom: 2rem;
    border-radius: 14px;
}
.summary-header h1 { margin: 0 0 0.5rem 0 !important; font-size: 1.8rem !important; }
.summary-header p { margin: 0; opacity: 0.85; font-size: 1.0rem; }
.summary-success { background: #e8f5e9; border: 2px solid #2e7d32; color: #1b5e20; }
.summary-neutral { background: #f5f5f5; border: 2px solid #9e9e9e; color: #424242; }

/* Panell inspector (Tasca 1): "Com pensa el tutor". Mostra, torn a torn,
   la decisió DETERMINISTA de Python (acció, transició, parse) llegint només
   state["history"]. El swatch d'acció reusa els mateixos colors que la
   targeta del tutor, de manera que sempre coincideixen. */
.inspector-row {
    display: flex; align-items: center; gap: 0.45rem;
    font-size: 0.86rem; margin: 0.35rem 0 0.5rem 0;
}
.inspector-row .sw {
    width: 0.9rem; height: 0.9rem; border-radius: 3px;
    border: 1px solid rgba(0,0,0,0.25); display: inline-block; flex: none;
}
.inspector-row .act-code {
    margin-left: auto; background: rgba(0,0,0,0.06);
    padding: 0.05rem 0.4rem; border-radius: 4px; font-size: 0.78rem;
}
.inspector-line {
    font-size: 0.8rem; color: rgba(0,0,0,0.68); margin: 0.3rem 0;
    line-height: 1.45;
}
.inspector-line code {
    background: rgba(0,0,0,0.06); padding: 0.03em 0.32em; border-radius: 3px;
    font-size: 0.95em;
}
.inspector-warn { color: #8b0000; font-weight: 600; }
.inspector-muted { color: rgba(0,0,0,0.45); }

/* Títol del panell de senyals sempre visible (mode docent) i línia
   d'atribució IA-vs-Python. El panell viu en una columna fixa a la dreta
   de la conversa; no és plegable ni té toggle. */
.signals-title {
    font-weight: 700; font-size: 1.0rem; color: #334e68;
    margin: 0 0 0.6rem 0;
}
.signals-title .signals-sub {
    font-weight: 500; font-size: 0.78rem; color: rgba(0,0,0,0.45);
}
.inspector-attr {
    font-size: 0.74rem; color: rgba(0,0,0,0.6);
    margin: 0.55rem 0 0.2rem 0; line-height: 1.6;
}
</style>
"""


# CSS per a les pantalles SENSE columna d'accions (selector i resum). Com que
# ara la barra lateral arrenca desplegada de manera global, en aquestes
# pantalles (que no hi posen res) amaguem el panell sencer perquè es vegin a
# tota amplada. A la pantalla de xat NO s'injecta, així la columna hi surt.
HIDE_SIDEBAR_CSS = """
<style>
[data-testid="stSidebar"] { display: none !important; }
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
        pid = state.get("problem_id", PB.DEFAULT_PROBLEM_ID)
        total = len(PB.PROBLEMS[pid]["problem"]["passos"])
        return f"Pas {step} de {total}"
    return None


# =============================================================================
# Inspector (Tasca 1): dades del darrer torn
# =============================================================================

# Etiquetes humanes de l'acció pedagògica (en català, per al docent).
ACTION_LABELS = {
    "advance": "avança",
    "stay": "es queda",
    "retreat_to_prereq": "retrocedeix al reforç",
}

# Color (bg, vora) de cada classe semàntica. Són EXACTAMENT els mateixos
# valors que les regles .tutor-* del CSS, de manera que el swatch de
# l'inspector coincideix sempre amb la targeta del tutor del mateix torn.
ACTION_SWATCH = {
    "green": ("#e8f5e9", "#2e7d32"),
    "yellow": ("#fff8e1", "#ef6c00"),
    "gray": ("#f5f5f5", "#757575"),
    "bordeaux": ("#fbe9e7", "#8b0000"),
    "neutral": ("#e3f2fd", "#1976d2"),
}


def inspector_snapshot(state):
    """Resum del darrer torn per al panell inspector. Funció PURA (sense
    Streamlit) per poder-se testejar: només LLEGEIX state['history'] i les
    posicions desades; no muta res. Retorna None si encara no hi ha torns.

    La clau `color` ve de determine_turn_color(state) — la mateixa funció
    que pinta la targeta del tutor — així el swatch i la targeta coincideixen.
    """
    history = state.get("history") or []
    if not history:
        return None
    latest = history[-1]
    action = latest.get("action", "stay")
    color = determine_turn_color(state)
    parse_ok = latest.get("control_parse_ok", True)
    before = latest.get("position_before") or {}
    after = latest.get("position_after") or {}
    diagnostic = latest.get("diagnostic")

    desc = ""
    if diagnostic:
        pid = state.get("problem_id", PB.DEFAULT_PROBLEM_ID)
        desc = PB.error_catalog(pid).get(diagnostic, "")

    return {
        "action": action,
        "action_label": ACTION_LABELS.get(action, action),
        "color": color,
        "swatch": ACTION_SWATCH.get(color, ACTION_SWATCH["neutral"]),
        "parse_ok": bool(parse_ok),
        "before": S.position_summary_from(before) if before else "—",
        "after": S.position_summary_from(after) if after else "—",
        "diagnostic": diagnostic,
        "diagnostic_desc": desc,
        "elapsed_seconds": latest.get("elapsed_seconds"),
    }


# =============================================================================
# Render: components
# =============================================================================

def _source_chip(source):
    """HTML del xip d'origen (capa ortogonal al color d'acció)."""
    if source == "py":
        return ('<span class="source-chip chip-py">🐍 Python · determinista</span>')
    if source == "ai":
        return ('<span class="source-chip chip-ai">🤖 IA · heurística</span>')
    return ""


def _split_opening(problem_id, content):
    """Separa el contingut d'obertura en (enunciat, pregunta).

    L'obertura la construeix simulator.new_session com
    `enunciat + "\\n\\n" + passos[0]['text']`. Aquí fem servir l'enunciat
    del problema com a prefix per tallar el contingut real de la bombolla,
    de manera que l'enunciat vagi a una targeta i la pregunta del Pas 1 a
    una altra just a sota. És purament de presentació: no toca ni el
    `display` ni el `transcript` (el model continua veient el text sencer).

    Si el contingut no encaixa amb aquest patró (estats heretats o text
    editat), retorna (content, None) i es mostra com una sola bombolla.
    """
    try:
        p = PB.PROBLEMS[problem_id]["problem"]
    except (KeyError, TypeError):
        return content, None
    enunciat = (p.get("enunciat") or "").strip()
    body = (content or "").strip()
    if enunciat and body.startswith(enunciat):
        pregunta = body[len(enunciat):].strip()
        return enunciat, (pregunta or None)
    return content, None


# -----------------------------------------------------------------------------
# Paginació de bombolles llargues (UI pura, no toca dades ni transcript)
# -----------------------------------------------------------------------------
# Algunes bombolles deterministes (sobretot l'obertura de CAUS-001) són
# massa llargues per a una sola viewport. Les partim en "subpantalles" i en
# revelem una cada cop que l'usuari prem "Continuar", sense esborrar les
# anteriors. És purament de presentació: el `content` real de la bombolla
# (el que veuen el model i el transcript) no canvia mai.

# Pressupost de caràcters per pàgina. Per sota d'això, la bombolla es
# mostra sencera i no apareix cap botó. Ajustat perquè una obertura llarga
# quedi en ~2 pàgines i els enunciats/pistes curts en 1.
PAGE_CHAR_BUDGET = 600

# Prefixos que marquen l'inici "natural" d'una secció nova: si un bloc en
# comença per un, és un bon lloc per tallar pàgina encara que no s'hagi
# esgotat el pressupost (evita partir, p. ex., una llista de dades a/b/c o
# separar les preguntes del seu context).
_SECTION_STARTS = ("Pregunta", "── PAS", "Tenim aquestes dades",
                   "Calcula", "a)", "Fes ", "1)", "1.", "Imagina")


def paginate_text(text):
    """Parteix un text en pàgines acumulant paràgrafs (separats per línia
    en blanc) fins a esgotar el pressupost de caràcters. Mai parteix un
    paràgraf pel mig: respecta els salts que ha posat el docent. A més,
    prefereix tallar just abans d'un bloc que obre una secció nova (dades,
    preguntes), perquè cada subpantalla quedi conceptualment sencera.
    Retorna una llista de strings (>=1); un text curt retorna una pàgina."""
    if not text:
        return [""]
    blocks = [b for b in text.split("\n\n")]
    pages, cur, cur_len = [], [], 0
    for b in blocks:
        bstrip = b.lstrip()
        opens_section = any(bstrip.startswith(p) for p in _SECTION_STARTS)
        blen = len(b)
        over_budget = cur and (cur_len + blen > PAGE_CHAR_BUDGET)
        # Tallem si: passem pressupost, O bé el bloc obre secció i la pàgina
        # actual ja té prou cos perquè valgui la pena un tall net.
        natural_break = cur and opens_section and cur_len > PAGE_CHAR_BUDGET * 0.5
        if over_budget or natural_break:
            pages.append("\n\n".join(cur))
            cur, cur_len = [b], blen
        else:
            cur.append(b)
            cur_len += blen + 2
    if cur:
        pages.append("\n\n".join(cur))
    return pages or [""]


def render_paginated_card(bubble_key, text, color, badge, source, label):
    """Renderitza una bombolla possiblement paginada.

    - Si el text cap en una pàgina: el comportament és idèntic a abans
      (una targeta, cap botó).
    - Si té diverses pàgines: mostra les pàgines ja revelades com a
      targetes successives (les anteriors NO desapareixen) i, si en
      queden, un botó "Continuar" que en revela una més.

    El nombre de pàgines revelades es desa a st.session_state amb una clau
    estable per bombolla (`bubble_key`), de manera que sobreviu als reruns
    i és independent per a cada bombolla.
    """
    pages = paginate_text(text)
    n = len(pages)

    if n == 1:
        # Cas comú: una sola targeta, sense paginació.
        _render_one(text, color, badge, source, label, suffix="")
        return

    shown_key = f"pages_shown::{bubble_key}"
    shown = st.session_state.get(shown_key, 1)
    shown = max(1, min(shown, n))

    for idx in range(shown):
        # Etiqueta: la primera pàgina manté l'etiqueta original; les
        # continuacions porten un peu discret "(continua)".
        pg_label = label if idx == 0 else None
        suffix = "" if idx == 0 else f"(part {idx + 1} de {n})"
        _render_one(pages[idx], color, badge if idx == 0 else None,
                    source, pg_label, suffix=suffix)

    if shown < n:
        restant = n - shown
        if st.button(f"Continuar ({restant} més) ↓",
                     key=f"more::{bubble_key}",
                     use_container_width=True):
            st.session_state[shown_key] = shown + 1
            st.rerun()


def _render_one(text, color, badge, source, label, suffix=""):
    """Renderitza una única targeta (una pàgina). `suffix` és un peu
    discret opcional (p. ex. 'part 2 de 2')."""
    badge_html = f'<span class="step-badge">{badge}</span>' if badge else ""
    body_html = simple_md_to_html(text)
    chip_html = _source_chip(source)
    label_html = (f'<p class="pregunta-label">{label}</p>' if label else "")
    suffix_html = (f'<p class="page-suffix">{suffix}</p>' if suffix else "")
    html = (
        f'<div class="tutor-card tutor-{color}">'
        f'<div class="tutor-header">'
        f'<span>🎓 Tutor</span>'
        f"{chip_html}"
        f"{badge_html}"
        f"</div>"
        f"{label_html}"
        f'<div class="tutor-body">{body_html}</div>'
        f"{suffix_html}"
        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_layer_legend():
    """Llegenda de les DUES capes de color: acció pedagògica + origen.

    Per a una demo davant professorat de mètodes, fa explícit que el
    sistema combina control determinista (Python) i generació estocàstica
    (IA), i que el color de fons codifica la decisió pedagògica del tutor."""
    st.markdown(
        '<div class="layer-legend">'
        '<span class="lg"><b>Acció:</b></span>'
        '<span class="lg"><span class="sw" style="background:#e8f5e9;'
        'border-color:#2e7d32"></span>avança</span>'
        '<span class="lg"><span class="sw" style="background:#fff8e1;'
        'border-color:#ef6c00"></span>avança amb dubtes / reforç</span>'
        '<span class="lg"><span class="sw" style="background:#f5f5f5;'
        'border-color:#757575"></span>es queda</span>'
        '<span class="lg" style="margin-left:0.6rem">'
        '<span class="source-chip chip-py">🐍 Python</span>'
        '<span class="source-chip chip-ai">🤖 IA</span></span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_thinking_card():
    html = (
        '<div class="tutor-card tutor-thinking">'
        '<div class="tutor-header"><span>🎓 Tutor</span></div>'
        '<div class="tutor-body"><p>Pensant…</p></div>'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_inspector(state):
    """Panell de senyals "Com pensa el tutor" (Tasca 1).

    Mostra, torn a torn, la decisió DETERMINISTA que hi ha darrere de la
    resposta: quina acció ha emès el model, com ha quedat la posició
    (Python decideix on som, no el model), si el control block s'ha pogut
    llegir, i —si n'hi ha— quina malentesa conceptual s'ha diagnosticat.

    Llegeix NOMÉS state['history']; no muta res ni el comportament del tutor.

    Visibilitat: aquest panell només es renderitza en MODE DOCENT
    (?docent=1). Quan es renderitza, és SEMPRE VISIBLE — sense toggle ni
    plegar — perquè en una demo en directe els senyals no desapareguin per
    accident. Els alumnes (URL normal) no el veuen mai: els codis de
    malentesa (INT_prob_param, etc.) són vocabulari de docent i veure'ls en
    temps real podria condicionar com respon l'alumne.
    """
    st.markdown(
        '<div class="signals-title">🔬 Senyals en directe '
        '<span class="signals-sub">(mode docent)</span></div>',
        unsafe_allow_html=True,
    )

    snap = inspector_snapshot(state)
    if snap is None:
        st.caption("Encara no hi ha cap torn. Els senyals apareixeran "
                   "després de la primera resposta de l'alumne.")
        return

    bg, border = snap["swatch"]
    warn_mark = " ⚠" if not snap["parse_ok"] else ""
    st.markdown(
        f'<div class="inspector-row">'
        f'<span class="sw" style="background:{bg};border-color:{border}"></span>'
        f'<b>Acció: {snap["action_label"]}</b>'
        f'<span class="act-code">{snap["action"]}{warn_mark}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="inspector-line">Posició: '
        f'<code>{snap["before"]}</code> → <code>{snap["after"]}</code></div>',
        unsafe_allow_html=True,
    )

    # Atribució explícita (el cor de la tesi): la IA només EMET l'acció;
    # Python DECIDEIX la posició i, si cal, injecta l'enunciat canònic.
    st.markdown(
        '<div class="inspector-attr">'
        '<span class="source-chip chip-ai">🤖 IA</span> emet l\'acció · '
        '<span class="source-chip chip-py">🐍 Python</span> decideix la posició'
        "</div>",
        unsafe_allow_html=True,
    )

    if not snap["parse_ok"]:
        st.markdown(
            '<div class="inspector-line inspector-warn">'
            "⚠ El control block no s'ha pogut llegir; s'ha aplicat "
            "<code>stay</code> per defecte.</div>",
            unsafe_allow_html=True,
        )

    # Malentesa diagnosticada (Tasca 4). És metadada: NO altera el flux.
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


# =============================================================================
# Render: vista de conversa
# =============================================================================

def _trailing_tutor_cluster(state):
    """Bombolles del tutor des de l'últim torn de l'alumne fins al final
    del display. Normalment: el reply del model + (si n'hi ha) l'enunciat
    canònic que Python ha injectat en avançar. A l'obertura: l'enunciat
    inicial. Si encara no hi ha display (estats heretats), cau al reply
    del transcript."""
    display = state.get("display")
    if not display:
        latest = next(
            (t["content"] for t in reversed(state["transcript"])
             if t["role"] == "tutor"), None,
        )
        return [{"role": "tutor", "content": latest, "source": "ai"}] if latest else []

    cluster = []
    for item in reversed(display):
        if item["role"] == "student":
            break
        cluster.append(item)
    cluster.reverse()
    return [c for c in cluster if c["role"] == "tutor"]


def _render_conversation_body(state):
    """Renderitza el clúster de bombolles del tutor del torn actual i
    retorna el `tutor_slot` (st.empty) perquè el caller hi pugui pintar
    "Pensant…" durant la crida LLM. Extret de render_chat_view perquè es
    pugui col·locar dins d'una columna en mode docent sense reindentar."""
    cluster = _trailing_tutor_cluster(state)
    color = determine_turn_color(state)
    badge = position_label(state)
    pid = state.get("problem_id", "")
    display = state.get("display", [])
    base_idx = len(display) - len(cluster)

    render_layer_legend()

    tutor_slot = st.empty()
    with tutor_slot.container():
        if not cluster:
            render_thinking_card()
        for i, item in enumerate(cluster):
            bubble_key = f"{pid}#{base_idx + i}"
            if item["source"] == "py" and i > 0:
                render_paginated_card(
                    bubble_key, item["content"], color="deterministic",
                    badge=badge, source="py", label="Pregunta.",
                )
            elif item["source"] == "py":
                if state.get("turn_count", 0) == 0:
                    enunciat_txt, pregunta_txt = _split_opening(
                        pid, item["content"]
                    )
                    render_paginated_card(
                        f"{bubble_key}::enunciat", enunciat_txt, color=color,
                        badge=badge, source="py", label="Enunciat.",
                    )
                    if pregunta_txt:
                        render_paginated_card(
                            f"{bubble_key}::pregunta", pregunta_txt, color=color,
                            badge=None, source="", label="Pregunta.",
                        )
                else:
                    render_paginated_card(
                        bubble_key, item["content"], color=color, badge=badge,
                        source="py", label="Pregunta.",
                    )
            else:
                render_paginated_card(
                    bubble_key, item["content"], color=color, badge=badge,
                    source="ai", label="Pregunta.",
                )
    return tutor_slot


def render_chat_view(state):
    """Mostra el clúster de tutor del torn actual: la resposta del model
    (acolorida per acció) i, si Python ha posat l'enunciat del pas següent,
    la seva bombolla determinista a sota. Les bombolles llargues es
    paginen en subpantalles amb un botó "Continuar".

    En MODE DOCENT (?docent=1) la conversa es renderitza en una columna a
    l'esquerra i el panell de senyals SEMPRE VISIBLE en una columna a la
    dreta. En mode alumne, la conversa ocupa l'amplada habitual i no hi ha
    panell de senyals."""
    if DOCENT_MODE:
        col_conv, col_signals = st.columns([2, 1], gap="large")
        with col_conv:
            tutor_slot = _render_conversation_body(state)
        with col_signals:
            with st.container(border=True):
                render_inspector(state)
    else:
        tutor_slot = _render_conversation_body(state)

    with st.sidebar:
        st.markdown("### Accions")
        hint_clicked = st.button(
            "💡 Demanar pista",
            key="btn_hint",
        )
        end_clicked = st.button(
            "🚪 Acabar sessió",
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

    # Comandes de sortida heretades del CLI: si l'alumne escriu només "!!"
    # (o /quit, /exit), tanquem la sessió com faria el botó Acabar. No ho
    # enviem al model. Comparem sobre el text net per tolerar espais.
    if is_exit_command(student_msg):
        state["finished"] = True
        st.rerun()

    # Substituïm la targeta amb "Pensant…" abans de la crida.
    with tutor_slot.container():
        render_thinking_card()

    state["transcript"].append({"role": "student", "content": student_msg})
    S.append_display(state, "student", student_msg, "student")
    state["turn_count"] += 1

    try:
        t0 = time.time()
        active_problem = PB.PROBLEMS[state["problem_id"]]["problem"]
        result = L.tutor_turn(
            active_problem,
            S.position_dict(state),
            state["transcript"],
        )
        elapsed = time.time() - t0
    except Exception as exc:
        st.error(
            f"Error tècnic en cridar el model: {type(exc).__name__}: {exc}"
        )
        state["transcript"].pop()
        if state.get("display") and state["display"][-1]["role"] == "student":
            state["display"].pop()
        state["turn_count"] -= 1
        st.stop()

    # Origen del reply: "py" si ha respost el mode de reserva, "ai" si IA.
    reply_source = "py" if result.get("mode") == "py" else "ai"

    # CRÍTIC: afegir el reply al transcript abans del següent torn.
    # (Bug original del simulator que el sistema arrastrava.)
    state["transcript"].append({"role": "tutor", "content": result["reply"]})
    S.append_display(state, "tutor", result["reply"], reply_source)

    position_before = {
        "step": state["current_step"],
        "prereq": state["active_prereq"],
    }
    transition = S.apply_action(state, result["action"])
    # Tier 1: Python garanteix la pregunta canònica del nou pas/reforç com a
    # bombolla determinista (source="py"). Així l'enunciat sempre apareix
    # encara que el model no l'escrigui, i el color/xip el distingeixen.
    S.enrich_after_transition(state, transition)
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
        "diagnostic": result.get("diagnostic"),
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
        st.markdown(f"**Reforç PRE-CONFOUNDER** — {qs['turns_in_prereq']} torn{s}")
        st.progress(qs["turns_in_prereq"] / max_count)

    # Malentesos detectats per pas (Tasca 4). Traduïm els codis del catàleg
    # a la seva descripció humana per al docent. Només mostrem la secció si
    # s'ha registrat algun diagnòstic durant la sessió.
    diag_counts = qs.get("diagnostic_counts") or {}
    if diag_counts:
        st.markdown("---")
        st.markdown("### Malentesos detectats")
        pid = state.get("problem_id", PB.DEFAULT_PROBLEM_ID)
        catalog = PB.error_catalog(pid)
        dominant = qs.get("dominant_diagnostic_per_step") or {}
        per_step = qs.get("diagnostic_per_step") or {}
        any_row = False
        for step in sorted(per_step.keys()):
            code = dominant.get(step)
            if not code:
                continue
            any_row = True
            n = per_step[step].get(code, 0)
            desc = catalog.get(code, "")
            s = "s" if n != 1 else ""
            st.markdown(
                f"**Pas {step}** — malentesa dominant: `{code}` "
                f"({n} torn{s})"
            )
            if desc:
                st.markdown(
                    f"<div style='color:#666; font-size:0.95em; "
                    f"margin:-0.4rem 0 0.6rem 0;'>{desc}</div>",
                    unsafe_allow_html=True,
                )
        if not any_row:
            st.markdown("Cap malentesa conceptual recurrent registrada.")

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

def render_picker():
    """Pantalla inicial: l'alumne tria quin problema vol treballar.

    Es mostra una sola vegada per sessió de navegador. La selecció
    es desa a st.session_state.problem_id i a partir d'aquí la resta
    del flux de l'app utilitza aquest id per crear la sessió i passar
    el bundle correcte a tutor_turn.
    """
    st.title("Tutoria")
    st.markdown("Escull un d'aquests problemes")
    st.markdown("")

    for pid, title_human in PB.list_ids():
        bundle = PB.PROBLEMS[pid]
        with st.container(border=True):
            st.markdown(f"### {title_human}")
            st.markdown(
                f"<div style='color:#666; font-size:1.08em;'>"
                f"<code>{pid}</code> — {bundle['problem']['tema']}"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown("")
            if st.button(
                "Treballar aquest problema",
                key=f"pick_{pid}",
            ):
                st.session_state.problem_id = pid
                st.session_state.state = S.new_session(pid)
                st.rerun()


def main():
    st.markdown(CSS, unsafe_allow_html=True)

    # Picker: si l'alumne encara no ha triat problema, mostra'l i atura.
    if "problem_id" not in st.session_state:
        st.markdown(HIDE_SIDEBAR_CSS, unsafe_allow_html=True)
        render_picker()
        return

    problem_id = st.session_state.problem_id
    title_human = PB.PROBLEMS[problem_id]["title_human"]
    st.title(f"Tutoria ({title_human.lower()})")

    # Indicador d'estat de la IA. Si l'API no està disponible, l'app no
    # peta: opera en mode de reserva (heurística). Útil de tenir visible
    # en una demo en directe.
    if L.ia_disponible():
        st.markdown(
            f'<span class="ia-status ia-ok">🤖 IA connectada · {L.MODEL}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="ia-status ia-warn">🐍 Mode de reserva (sense IA) · '
            "avaluació heurística per paraules clau. Defineix "
            "<code>GEMINI_API_KEY</code> per a l'experiència completa.</span>",
            unsafe_allow_html=True,
        )

    if "state" not in st.session_state:
        st.session_state.state = S.new_session(problem_id)

    state = st.session_state.state

    if state.get("finished"):
        if "quality_signals" not in state:
            state["quality_signals"] = S.compute_quality_signals(state)
        st.markdown(HIDE_SIDEBAR_CSS, unsafe_allow_html=True)
        render_summary_view(state)
    else:
        render_chat_view(state)


if __name__ == "__main__":
    main()
