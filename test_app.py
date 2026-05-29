"""
test_app.py — tests aïllats per a les funcions helper de l'app
Streamlit. Verifiquem la lògica de:
  - simple_md_to_html (conversor markdown)
  - is_disengaged (heurística de vacil·lar)
  - count_consecutive_stays_in_same_position
  - determine_turn_color
  - position_label

Sense necessitat de Streamlit ni Gemini: stub d'streamlit perquè
l'import d'app.py no exploti.

Executar:
    python3 test_app.py
"""

import os
import sys
import types


# --- Stubs perquè l'import d'app.py funcioni sense streamlit/genai ---
class _StreamlitStub:
    def __getattr__(self, name):
        # Qualsevol crida (set_page_config, markdown, etc.) torna un noop
        return lambda *a, **kw: None

    def __call__(self, *a, **kw):
        return None

sys.modules["streamlit"] = _StreamlitStub()
sys.modules["google"] = types.ModuleType("google")
sys.modules["google.genai"] = types.ModuleType("google.genai")
sys.modules["google.genai.types"] = types.ModuleType("google.genai.types")
os.environ.setdefault("GEMINI_API_KEY", "fake-for-tests")

import app  # noqa: E402


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


# =============================================================================
# simple_md_to_html
# =============================================================================
print("\nTest 1 — simple_md_to_html: bàsic")
check("text pla queda en <p>",
      app.simple_md_to_html("Hola") == "<p>Hola</p>")
check("buit retorna ''", app.simple_md_to_html("") == "")
check("None retorna ''", app.simple_md_to_html(None) == "")

print("\nTest 2 — simple_md_to_html: formats inline")
h = app.simple_md_to_html("Això és **important** i això *no tant*.")
check("negreta convertida", "<strong>important</strong>" in h)
check("cursiva convertida", "<em>no tant</em>" in h)

h = app.simple_md_to_html("Usa `print()` al teu codi")
check("inline code convertit", "<code>print()</code>" in h)

print("\nTest 3 — simple_md_to_html: paràgrafs múltiples i salts")
h = app.simple_md_to_html("Primer paràgraf.\n\nSegon paràgraf.")
check("dos paràgrafs", h.count("<p>") == 2)

h = app.simple_md_to_html("Línia 1\nLínia 2")
check("salt simple → <br>", "Línia 1<br>Línia 2" in h)

print("\nTest 4 — simple_md_to_html: blockquote")
h = app.simple_md_to_html("> Aquesta és una cita")
check("blockquote convertit",
      "<blockquote>Aquesta és una cita</blockquote>" in h)

print("\nTest 5 — simple_md_to_html: escape d'HTML")
h = app.simple_md_to_html("Codi: <script>alert(1)</script>")
check("entitats escapades",
      "&lt;script&gt;" in h and "<script>" not in h)


# =============================================================================
# is_disengaged
# =============================================================================
print("\nTest 6 — is_disengaged: cas buit")
check("history buit → False",
      app.is_disengaged({"history": []}) is False)
check("estat sense history → False",
      app.is_disengaged({}) is False)

print("\nTest 7 — is_disengaged: paraules de mofa")
state = {"history": [{"student_msg": "patata patata"}]}
check("'patata' triga bordeus", app.is_disengaged(state) is True)

state = {"history": [{"student_msg": "atrapame si puedes hahaha"}]}
check("'hahaha' triga bordeus", app.is_disengaged(state) is True)

state = {"history": [{"student_msg": "vinga, jo crec que..."}]}
check("text normal no triga", app.is_disengaged(state) is False)

state = {"history": [{"student_msg": app.HINT_MARKER}]}
check("sol·licitud de pista no triga",
      app.is_disengaged(state) is False)

print("\nTest 8 — is_disengaged: missatges curts repetits")
state = {"history": [
    {"student_msg": "fix"},
    {"student_msg": "sí"},
    {"student_msg": "no"},
]}
check("3 missatges curts → bordeus", app.is_disengaged(state) is True)

state = {"history": [
    {"student_msg": "Una resposta llarga i ben pensada"},
    {"student_msg": "Una altra resposta argumentada"},
    {"student_msg": "fix"},
]}
check("només 1 curt al final no triga (1 < 2)",
      app.is_disengaged(state) is False)

state = {"history": [
    {"student_msg": "Resposta llarga"},
    {"student_msg": "fix"},
    {"student_msg": "no"},
]}
check("2 dels 3 últims molt curts → bordeus",
      app.is_disengaged(state) is True)


# =============================================================================
# count_consecutive_stays_in_same_position
# =============================================================================
print("\nTest 9 — count_consecutive_stays_in_same_position")
check("idx 0 retorna 0",
      app.count_consecutive_stays_in_same_position([], 0) == 0)

history = [
    {"action": "stay", "position_before": {"step": 1, "prereq": None}},
    {"action": "stay", "position_before": {"step": 1, "prereq": None}},
    {"action": "advance", "position_before": {"step": 1, "prereq": None}},
]
check("2 stays al mateix pas abans d'advance → 2",
      app.count_consecutive_stays_in_same_position(history, 2) == 2)

# Si abans del stay hi havia advance, no compta més enrere
history = [
    {"action": "advance", "position_before": {"step": 1, "prereq": None}},
    {"action": "stay", "position_before": {"step": 2, "prereq": None}},
    {"action": "advance", "position_before": {"step": 2, "prereq": None}},
]
check("stay aïllat al pas 2 (advance previ al pas 1) → 1",
      app.count_consecutive_stays_in_same_position(history, 2) == 1)


# =============================================================================
# determine_turn_color
# =============================================================================
print("\nTest 10 — determine_turn_color")
check("history buit → neutral",
      app.determine_turn_color({"history": []}) == "neutral")

state = {"history": [{
    "action": "advance",
    "student_msg": "Resposta bona",
    "position_before": {"step": 1, "prereq": None},
}]}
check("advance sense stays previs → green",
      app.determine_turn_color(state) == "green")

state = {"history": [
    {"action": "stay", "student_msg": "Intent 1",
     "position_before": {"step": 1, "prereq": None}},
    {"action": "stay", "student_msg": "Intent 2",
     "position_before": {"step": 1, "prereq": None}},
    {"action": "advance", "student_msg": "Intent 3",
     "position_before": {"step": 1, "prereq": None}},
]}
check("advance amb 2 stays previs al mateix pas → yellow",
      app.determine_turn_color(state) == "yellow")

state = {"history": [{
    "action": "stay", "student_msg": "Una resposta normal",
    "position_before": {"step": 1, "prereq": None},
}]}
check("stay normal → gray", app.determine_turn_color(state) == "gray")

state = {"history": [{
    "action": "stay", "student_msg": "patata",
    "position_before": {"step": 1, "prereq": None},
}]}
check("stay amb mofa → bordeaux (override)",
      app.determine_turn_color(state) == "bordeaux")

state = {"history": [{
    "action": "retreat_to_prereq", "student_msg": "fix",
    "position_before": {"step": 2, "prereq": None},
}]}
check("retreat_to_prereq → yellow (no és mofa: 'fix' és curt però sol)",
      app.determine_turn_color(state) == "yellow")


# =============================================================================
# position_label
# =============================================================================
print("\nTest 11 — position_label")
check("sessió acabada → None",
      app.position_label({"finished": True, "current_step": 3}) is None)

check("pas 2 → 'Pas 2 de 3'",
      app.position_label({"current_step": 2, "active_prereq": None}) ==
      "Pas 2 de 3")

check("reforç → 'Reforç → Pas N'",
      app.position_label({
          "current_step": 1,
          "active_prereq": "PRE-CONFOUNDER",
          "step_before_prereq": 1,
      }) == "Reforç → Pas 1")

check("sense step ni reforç → None",
      app.position_label({"current_step": None, "active_prereq": None}) is None)


print("\nTest 12 — paginate_text")
# Text curt → una sola pàgina.
check("text curt → 1 pàgina",
      len(app.paginate_text("Una frase curta.")) == 1)
check("text buit → 1 pàgina amb cadena buida",
      app.paginate_text("") == [""])
# Text llarg amb molts paràgrafs → més d'una pàgina.
long_text = "\n\n".join([f"Paràgraf número {i} amb força text per omplir "
                          f"espai i superar el pressupost de pàgina, prou "
                          f"llarg de debò." for i in range(10)])
pages = app.paginate_text(long_text)
check("text llarg → més d'una pàgina", len(pages) > 1, f"{len(pages)}")
# Integritat: juntar pàgines reconstrueix l'original exactament.
check("les pàgines reconstrueixen el text original",
      "\n\n".join(pages) == long_text)
# Mai parteix un paràgraf pel mig: cap pàgina conté un tros de paràgraf.
all_blocks = set(long_text.split("\n\n"))
recon_blocks = set("\n\n".join(pages).split("\n\n"))
check("no parteix paràgrafs pel mig", all_blocks == recon_blocks)
# Tall natural: un bloc que obre secció ('Pregunta 1.') comença pàgina nova.
sectioned = ("Context inicial prou llarg per superar amb folgança la "
             "meitat del pressupost de pàgina, de manera que el tall "
             "natural just abans de la pregunta tingui sentit i no deixi "
             "una pàgina ridículament curta al davant; hi afegim encara "
             "una mica més de text per assegurar que passem el llindar de "
             "tall natural sense problemes de marge.\n\n"
             "Pregunta 1. Què en penses?")
pgs = app.paginate_text(sectioned)
check("tall natural davant 'Pregunta'", len(pgs) == 2 and
      pgs[1].lstrip().startswith("Pregunta 1."), f"{len(pgs)}")


# =============================================================================
# Resum
# =============================================================================
print()
print("=" * 60)
print(f"Tests passats: {PASSED}")
print(f"Tests fallits: {FAILED}")
if FAILED:
    print()
    print("Detalls:")
    for d in FAILED_DETAILS:
        print(f"  - {d}")
print("=" * 60)
sys.exit(0 if FAILED == 0 else 1)
