"""
test_inspector.py — tests aïllats per a la capa de presentació (Tasca 2) i
el panell inspector docent (Tasca 1) del Tutor de Divisibilitat.

Cobreix funcions PURES (sense Streamlit), més una passada de render del
panell amb un stub d'streamlit que captura l'HTML:

  - simple_md_to_html  (ara amb suport d'encapçalaments ## / # / ###)
  - _source_chip       (xip 🐍 Python vs 🤖 IA)
  - bubble_style       (regla d'estil de cada bombolla del display)
  - _position_summary_div
  - inspector_snapshot_div
  - render_inspector   (camí de render complet, via stub)

L'app.py de div executa la UI a nivell de mòdul (no té main()), així que
abans d'importar-lo cal: (1) un stub d'streamlit prou ric (session_state amb
accés per clau i atribut, context managers per a sidebar/expander/columns…),
i (2) pre-sembrar st.session_state.state amb una sessió real perquè la
pantalla d'inici no cridi st.stop() i el mòdul s'importi sencer.

NO es fa cap crida a la IA: sense GEMINI_API_KEY, llm cau al mode de reserva.

Executar:
    python3 test_inspector.py
"""

import os
import sys
import types


# ───────────────────────── stub d'streamlit ──────────────────────────── #

class _Stop(Exception):
    pass


class _CM:
    """Context manager neutre (sidebar, expander, spinner, columns…)."""
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _SessionState(dict):
    """Suporta accés per clau (`"x" in ss`, `ss["x"]`) i per atribut
    (`ss.x`), com el session_state real d'streamlit."""
    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v


class _QueryParams:
    def __init__(self):
        self._d = {}

    def get(self, k, default=None):
        return self._d.get(k, default)


class _StreamlitStub:
    def __init__(self):
        self.session_state = _SessionState()
        self.sidebar = _CM()
        self.query_params = _QueryParams()
        self.captured = []          # HTML/text capturat per markdown/caption…
        self._toggle_return = False  # què retorna st.toggle()

    # mètodes que retornen context managers
    def expander(self, *a, **k):
        return _CM()

    def spinner(self, *a, **k):
        return _CM()

    def container(self, *a, **k):
        return _CM()

    def columns(self, spec, *a, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_CM() for _ in range(n)]

    # mètodes que retornen valors
    def button(self, *a, **k):
        return False

    def toggle(self, *a, **k):
        return self._toggle_return

    def chat_input(self, *a, **k):
        return None

    # captura de sortida
    def markdown(self, body="", *a, **k):
        self.captured.append(str(body))

    def caption(self, body="", *a, **k):
        self.captured.append(str(body))

    def code(self, body="", *a, **k):
        self.captured.append(str(body))

    def write(self, body="", *a, **k):
        self.captured.append(str(body))

    def json(self, obj=None, *a, **k):
        self.captured.append(str(obj))

    def stop(self):
        raise _Stop()

    def __getattr__(self, name):
        # qualsevol altra crida (set_page_config, title, info, success,
        # warning, divider, error, rerun…) → noop
        return lambda *a, **kw: None


_stub = _StreamlitStub()
sys.modules["streamlit"] = _stub
# stubs de la SDK de Google (no s'usa: llm cau al mode de reserva)
sys.modules["google"] = types.ModuleType("google")
sys.modules["google.genai"] = types.ModuleType("google.genai")
sys.modules["google.genai.types"] = types.ModuleType("google.genai.types")
# IMPORTANT: NO definim GEMINI_API_KEY → ia_disponible() == False (fallback)
os.environ.pop("GEMINI_API_KEY", None)

import tutor  # noqa: E402
import problems  # noqa: E402

# Pre-sembrem una sessió real perquè la pantalla d'inici no cridi st.stop()
# i app.py s'importi sencer (totes les funcions queden definides).
_stub.session_state["state"] = tutor.new_session()

import app  # noqa: E402


# ───────────────────────────── arnès ──────────────────────────────────── #

PASSED = 0
FAILED = 0
FAILED_DETAILS = []


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✓ {name}")
    else:
        FAILED += 1
        FAILED_DETAILS.append(f"{name}: {detail}")
        print(f"  ✗ {name}  {detail}")


def fresh_state_with_turn(action="advance", parse_ok=True, diagnostic=None,
                          transition="seguent_pas"):
    """Sessió real + un torn fictici afegit a l'history, com el deixaria
    processa(). Deixem cap_idx/pas_idx al valor inicial (capítol 1, pas 1)."""
    s = tutor.new_session()
    s["history"].append({
        "position_before": {"capitol": 1, "pas": 1},
        "action": action,
        "diagnostic": diagnostic,
        "transition": transition,
        "control_parse_ok": parse_ok,
        "n_api_calls": 0 if not parse_ok else 1,
    })
    return s


# =============================================================================
# simple_md_to_html — encapçalaments (afegit per a div)
# =============================================================================
print("\nTest 1 — simple_md_to_html: bàsic i inline (heretat d'ic)")
check("text pla → <p>", app.simple_md_to_html("Hola") == "<p>Hola</p>")
check("buit → ''", app.simple_md_to_html("") == "")
check("None → ''", app.simple_md_to_html(None) == "")
h = app.simple_md_to_html("Això és **clau** i això *menys*.")
check("negreta", "<strong>clau</strong>" in h)
check("cursiva", "<em>menys</em>" in h)
check("codi inline", "<code>x</code>" in app.simple_md_to_html("usa `x`"))

print("\nTest 2 — simple_md_to_html: encapçalaments (## de les obertures)")
h = app.simple_md_to_html("## Capítol 1: Els múltiples")
check("## → <h2>", "<h2>Capítol 1: Els múltiples</h2>" in h)
check("## no embolcallat en <p>", "<p><h2>" not in h)
h = app.simple_md_to_html("### Subtítol")
check("### → <h3>", "<h3>Subtítol</h3>" in h)
h = app.simple_md_to_html("# Títol gran")
check("# → <h2> (mateix aspecte blau)", "<h2>Títol gran</h2>" in h)
h = app.simple_md_to_html("## Obertura\n\nText normal aquí.")
check("encapçalament + paràgraf coexisteixen",
      "<h2>Obertura</h2>" in h and "<p>Text normal aquí.</p>" in h)

print("\nTest 3 — simple_md_to_html: escape d'HTML es manté")
h = app.simple_md_to_html("Perill: <script>")
check("entitats escapades", "&lt;script&gt;" in h and "<script>" not in h)


# =============================================================================
# _source_chip
# =============================================================================
print("\nTest 4 — _source_chip: 🐍 Python vs 🤖 IA")
py = app._source_chip("py")
ai = app._source_chip("ai")
check("py → xip Python", "chip-py" in py and "🐍" in py)
check("ai → xip IA", "chip-ai" in ai and "🤖" in ai)
check("desconegut → ''", app._source_chip("???") == "")


# =============================================================================
# bubble_style — regla d'estil de cada bombolla del display
# =============================================================================
print("\nTest 5 — bubble_style: resposta (amb action) vs estructural (sense)")
c, src, det = app.bubble_style({"role": "tutor", "content": "x",
                                "source": "ai", "action": "advance"})
check("advance → verd", c == "green")
check("advance → no determinista", det is False)
check("source propagat", src == "ai")

c, src, det = app.bubble_style({"role": "tutor", "content": "x",
                                "source": "ai", "action": "stay"})
check("stay → gris", c == "gray")

c, src, det = app.bubble_style({"role": "tutor", "content": "obertura",
                                "source": "py"})
check("sense action → determinista", det is True and c == "deterministic")
check("estructural → source py", src == "py")

c, src, det = app.bubble_style({"role": "tutor", "content": "x"})
check("source per defecte → ai", src == "ai")
check("div mai usa groc (no hi ha retrocés)",
      "yellow" not in app.DIV_ACTION_COLOR.values())


# =============================================================================
# _position_summary_div
# =============================================================================
print("\nTest 6 — _position_summary_div")
check("posició normal", app._position_summary_div({"capitol": 2, "pas": 3})
      == "cap. 2 · pas 3")
check("buit → —", app._position_summary_div({}) == "—")
check("None → —", app._position_summary_div(None) == "—")
check("incompleta → —", app._position_summary_div({"capitol": 1}) == "—")


# =============================================================================
# inspector_snapshot_div — funció PURA
# =============================================================================
print("\nTest 7 — inspector_snapshot_div: sense torns → None")
check("history buit → None", app.inspector_snapshot_div(tutor.new_session())
      is None)

print("\nTest 8 — inspector_snapshot_div: torn advance net (verd)")
s = fresh_state_with_turn(action="advance", transition="seguent_pas")
snap = app.inspector_snapshot_div(s)
check("acció advance", snap["action"] == "advance")
check("etiqueta 'avança'", snap["action_label"] == "avança")
check("color verd", snap["color"] == "green")
check("swatch == valors CSS del verd",
      snap["swatch"] == app.ACTION_SWATCH["green"])
check("parse_ok True", snap["parse_ok"] is True)
check("transition propagada", snap["transition"] == "seguent_pas")
check("sense diagnostic", snap["diagnostic"] is None)
check("before formatat", snap["before"] == "cap. 1 · pas 1")
# 'after' es deriva de l'estat viu (post-acció del torn més recent)
check("after derivat de l'estat viu", snap["after"] == "cap. 1 · pas 1")

print("\nTest 9 — inspector_snapshot_div: swatch SEMPRE casa amb el color")
for act, expected in [("advance", "green"), ("stay", "gray")]:
    s = fresh_state_with_turn(action=act)
    snap = app.inspector_snapshot_div(s)
    same = snap["swatch"] == app.ACTION_SWATCH[expected]
    check(f"{act} → swatch del color {expected}", same,
          detail=f"{snap['swatch']} vs {app.ACTION_SWATCH[expected]}")

print("\nTest 10 — inspector_snapshot_div: stay amb parse fallit")
s = fresh_state_with_turn(action="stay", parse_ok=False, transition="stay")
snap = app.inspector_snapshot_div(s)
check("acció stay", snap["action"] == "stay")
check("color gris", snap["color"] == "gray")
check("parse_ok False (mostrarà ⚠)", snap["parse_ok"] is False)

print("\nTest 11 — inspector_snapshot_div: diagnostic resolt al catàleg")
code = "MUL_div_inexacta"  # codi real del capítol 1
s = fresh_state_with_turn(action="stay", diagnostic=code, transition="stay")
snap = app.inspector_snapshot_div(s)
expected_desc = problems.error_catalog(problems.CAPITOLS[0]).get(code, "")
check("diagnostic propagat", snap["diagnostic"] == code)
check("descripció resolta del catàleg",
      snap["diagnostic_desc"] == expected_desc and expected_desc != "")


# =============================================================================
# render_inspector — camí de render (via stub). Ja no hi ha toggle: el panell
# sempre pinta quan es crida (mode docent és per defecte; el gating viu al
# nivell de pàgina via DOCENT_MODE, no dins render_inspector).
# =============================================================================
print("\nTest 12 — render_inspector: sempre pinta (sense torns → missatge buit)")
_stub.query_params._d = {}
_stub.captured = []
app.render_inspector({"history": []})
blob = "\n".join(_stub.captured)
check("pinta la capçalera de senyals", "Senyals en directe" in blob)
check("diu que encara no hi ha torns", "Encara no hi ha cap torn" in blob)

print("\nTest 13 — render_inspector: torn advance net")
_stub.query_params._d = {}
_stub.captured = []
app.render_inspector(fresh_state_with_turn(action="advance"))
blob = "\n".join(_stub.captured)
check("mostra l'acció 'avança'", "avança" in blob)
check("mostra la posició", "cap. 1 · pas 1" in blob)
check("sense ⚠ quan el parse és correcte", "⚠" not in blob)
check("diu que no hi ha malentesa", "Sense malentesa" in blob)
# Soroll eliminat: ja no es pinta el codi d'acció cru com a xip a la fila.
check("NO pinta el codi cru 'advance' a la fila d'acció",
      '<span class="act-code">advance' not in blob
      and "advance</span>" not in blob)
# La tesi es diu un sol cop a la capçalera, no com a línia repetida per torn.
check("la tesi apareix una sola vegada (capçalera)",
      blob.count("decideix la posició") == 1)

print("\nTest 14 — render_inspector: parse fallit → ⚠ i avís")
_stub.query_params._d = {}
_stub.captured = []
app.render_inspector(fresh_state_with_turn(action="stay", parse_ok=False,
                                           transition="stay"))
blob = "\n".join(_stub.captured)
check("apareix el marcador ⚠", "⚠" in blob)
check("apareix l'avís de control block",
      "no s'ha pogut llegir" in blob)

print("\nTest 15 — render_inspector: diagnostic mostrat amb descripció")
_stub.query_params._d = {}
_stub.captured = []
code = "MUL_div_inexacta"
app.render_inspector(fresh_state_with_turn(action="stay", diagnostic=code,
                                           transition="stay"))
blob = "\n".join(_stub.captured)
check("mostra el codi de malentesa", code in blob)
check("mostra la paraula 'Malentesa'", "Malentesa" in blob)

print("\nTest 16 — render_inspector: ?debug=1 obre la traça completa")
_stub.query_params._d = {"debug": "1"}
_stub.captured = []
app.render_inspector(fresh_state_with_turn(action="advance"))
blob = "\n".join(_stub.captured)
check("pinta el panell (senyals)", "avança" in blob)
check("revela l'etiqueta de raw_output", "raw_output" in blob)

print("\nTest 17 — render_inspector NO muta l'estat")
_stub.query_params._d = {}
_stub.captured = []
s = fresh_state_with_turn(action="advance")
before = (s["cap_idx"], s["pas_idx"], s["turn_count"],
          len(s["transcript"]), len(s["display"]), len(s["history"]))
app.render_inspector(s)
after = (s["cap_idx"], s["pas_idx"], s["turn_count"],
         len(s["transcript"]), len(s["display"]), len(s["history"]))
check("l'estat queda intacte després de renderitzar", before == after,
      detail=f"{before} != {after}")

print("\nTest 18 — _query_flag: convenció docent per defecte")
check("_query_flag default=True sense paràmetre → True",
      app._query_flag("docent", default=True) is True)
_stub.query_params._d = {"docent": "0"}
check("?docent=0 → False (alumne)",
      app._query_flag("docent", default=True) is False)
_stub.query_params._d = {"docent": "1"}
check("?docent=1 → True (docent)",
      app._query_flag("docent", default=True) is True)
_stub.query_params._d = {}

# reset del stub per si s'importa des d'un altre lloc
_stub.query_params._d = {}


# =============================================================================
# _trailing_tutor_cluster — només el TORN ACTUAL (com tutor-ic)
# =============================================================================
print("\nTest 19 — _trailing_tutor_cluster: obertura → només la bombolla "
      "d'obertura")
s = tutor.new_session()
cl = app._trailing_tutor_cluster(s)
check("a l'inici hi ha 1 bombolla de tutor", len(cl) == 1)
check("és l'obertura del capítol", "Capítol 1" in cl[0]["content"])

print("\nTest 20 — _trailing_tutor_cluster: després d'un 'stay' → només la "
      "resposta del model")
s = tutor.new_session()
tutor.add_student(s, "no ho sé")
tutor.add_tutor(s, "Pensa-hi una mica més…", source="ai")
s["display"][-1]["action"] = "stay"
cl = app._trailing_tutor_cluster(s)
check("només 1 bombolla (la resposta)", len(cl) == 1)
check("no inclou el missatge de l'alumne",
      all(m["role"] == "tutor" for m in cl))
check("manté la clau action per pintar el color",
      cl[0].get("action") == "stay")

print("\nTest 21 — _trailing_tutor_cluster: després d'un 'advance' → resposta "
      "+ enunciat nou (py), sense arrossegar l'historial")
s = tutor.new_session()
# torn 1: avança
tutor.add_student(s, "4")
tutor.add_tutor(s, "Molt bé!", source="ai")
s["display"][-1]["action"] = "advance"
tutor.enrich_last_tutor(s, "**PREGUNTA.** Següent pregunta?")
cl = app._trailing_tutor_cluster(s)
check("clúster de 2 bombolles (resposta + enunciat py)", len(cl) == 2)
check("la 1a és la resposta de la IA", cl[0].get("action") == "advance")
check("la 2a és determinista (py, sense action)",
      cl[1]["source"] == "py" and "action" not in cl[1])
# torn 2: encara que el display creixi, el clúster segueix sent del torn actual
tutor.add_student(s, "no ho sé")
tutor.add_tutor(s, "Tornem-hi…", source="ai")
s["display"][-1]["action"] = "stay"
cl2 = app._trailing_tutor_cluster(s)
check("després d'un 2n torn, el clúster torna a ser curt (1)", len(cl2) == 1)
check("display complet conservat a l'estat (historial intacte)",
      len(s["display"]) > len(cl2))


# =============================================================================
print("\n" + "=" * 60)
print(f"Tests passats: {PASSED}")
print(f"Tests fallits: {FAILED}")
if FAILED_DETAILS:
    print("-" * 60)
    for d in FAILED_DETAILS:
        print("  ✗ " + d)
print("=" * 60)
sys.exit(1 if FAILED else 0)
