"""
test_tutor_turn.py — test mínim de la funció tutor_turn sense necessitat
de clau Gemini real.

Stubeja `_call` amb respostes preconstruïdes i verifica:
  - Parse correcte de respostes ben formades amb cada acció.
  - Coerció a "stay" davant d'accions invàlides.
  - Fallback a "stay" + control_parse_ok=False amb JSON malformat.
  - Fallback a "stay" + control_parse_ok=False quan falta el separador.
  - Tolerància a control block embolicat en fences ```json.
  - Validació d'invariants del transcript.
  - Construcció correcta del multi-turn contents.
  - Càrrega i interpolació del system prompt.

Executar des del directori del projecte:
    python3 test_tutor_turn.py
"""

import os
import sys
import types

# --- Stubs per evitar dependències pesades en l'entorn de test ---
# El client Gemini real no es construeix mai (la cache `_client` queda
# a None i `_call` el sobreescrivim als tests). Però l'import de
# `google.genai` ha de funcionar.
sys.modules["google"] = types.ModuleType("google")
sys.modules["google.genai"] = types.ModuleType("google.genai")
sys.modules["google.genai.types"] = types.ModuleType("google.genai.types")
sys.modules["google.api_core"] = types.ModuleType("google.api_core")
sys.modules["google.api_core.exceptions"] = types.ModuleType("google.api_core.exceptions")

os.environ.setdefault("GEMINI_API_KEY", "fake-key-for-tests")

import llm  # noqa: E402
import problem as PB  # noqa: E402


# --- Helpers de test ---

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


def stub(text):
    """Retorna una funció que ignora els seus arguments i retorna `text`."""
    def _stub(*args, **kwargs):
        return text
    return _stub


# Un transcript bàsic vàlid (acaba en torn 'student')
BASIC_TRANSCRIPT = [
    {"role": "tutor", "content": "Hola, comencem el pas 1: a què es refereix el 95%?"},
    {"role": "student", "content": "la mitjana té probabilitat 95% de caure a l'interval"},
]


# -----------------------------------------------------------------------------
# Test 1: resposta ben formada amb action=stay
# -----------------------------------------------------------------------------
print("\nTest 1 — resposta ben formada amb action=stay")
llm._call = stub(
    "Has dit que la mitjana 'té probabilitat de caure'. Què hauria de ser "
    "cert sobre la mitjana perquè aquesta frase tingués sentit?\n\n"
    "---CONTROL---\n"
    '{"action": "stay", "objectives_met": []}'
)
result = llm.tutor_turn(PB.PROBLEM, {"step": 1, "prereq": None}, BASIC_TRANSCRIPT)
check("reply conté text rellevant", "mitjana" in result["reply"])
check("reply no conté el separador",
      llm.CONTROL_SEPARATOR not in result["reply"])
check("reply no conté el JSON control", '"action"' not in result["reply"])
check("action és 'stay'", result["action"] == "stay",
      f"got {result['action']!r}")
check("objectives_met és []", result["objectives_met"] == [])
check("n_api_calls és 1", result["n_api_calls"] == 1)
check("control_parse_ok és True", result["control_parse_ok"] is True)


# -----------------------------------------------------------------------------
# Test 2: action=advance amb objectives_met
# -----------------------------------------------------------------------------
print("\nTest 2 — action=advance amb objectiu")
llm._call = stub(
    "Exacte. Passem al següent pas: quin valor puntual estimaries?\n"
    "---CONTROL---\n"
    '{"action": "advance", "objectives_met": ["95_es_procediment"]}'
)
result = llm.tutor_turn(PB.PROBLEM, {"step": 1, "prereq": None}, BASIC_TRANSCRIPT)
check("action és 'advance'", result["action"] == "advance")
check("objectives_met conté l'objectiu",
      result["objectives_met"] == ["95_es_procediment"])


# -----------------------------------------------------------------------------
# Test 3: action=retreat_to_prereq
# -----------------------------------------------------------------------------
print("\nTest 3 — action=retreat_to_prereq")
llm._call = stub(
    "Sembla que ens cal aclarir un concepte previ.\n"
    "---CONTROL---\n"
    '{"action": "retreat_to_prereq", "objectives_met": []}'
)
result = llm.tutor_turn(PB.PROBLEM, {"step": 1, "prereq": None}, BASIC_TRANSCRIPT)
check("action és 'retreat_to_prereq'",
      result["action"] == "retreat_to_prereq")


# -----------------------------------------------------------------------------
# Test 4: action invàlida es coerceix a 'stay'
# -----------------------------------------------------------------------------
print("\nTest 4 — action invàlida es coerceix a 'stay'")
llm._call = stub(
    "Resposta.\n"
    "---CONTROL---\n"
    '{"action": "finish", "objectives_met": []}'  # "finish" no existeix
)
result = llm.tutor_turn(PB.PROBLEM, {"step": 1, "prereq": None}, BASIC_TRANSCRIPT)
check("action invàlida ('finish') → 'stay'", result["action"] == "stay")


# -----------------------------------------------------------------------------
# Test 5: JSON malformat al control block
# -----------------------------------------------------------------------------
print("\nTest 5 — JSON malformat")
llm._call = stub(
    "La meva resposta a l'alumne.\n"
    "---CONTROL---\n"
    "{this is not valid json"
)
result = llm.tutor_turn(PB.PROBLEM, {"step": 1, "prereq": None}, BASIC_TRANSCRIPT)
check("JSON malformat → action 'stay'", result["action"] == "stay")
check("JSON malformat → control_parse_ok False",
      result["control_parse_ok"] is False)
check("reply preservat", "La meva resposta a l'alumne" in result["reply"])


# -----------------------------------------------------------------------------
# Test 6: separador absent (model oblida ---CONTROL---)
# -----------------------------------------------------------------------------
print("\nTest 6 — separador absent")
llm._call = stub("Una resposta sense control block")
result = llm.tutor_turn(PB.PROBLEM, {"step": 1, "prereq": None}, BASIC_TRANSCRIPT)
check("sense separador → action 'stay'", result["action"] == "stay")
check("sense separador → control_parse_ok False",
      result["control_parse_ok"] is False)
check("tot el text com a reply",
      result["reply"] == "Una resposta sense control block")


# -----------------------------------------------------------------------------
# Test 7: control block embolicat en fences ```json
# -----------------------------------------------------------------------------
print("\nTest 7 — control block embolicat en ```json fences")
llm._call = stub(
    "Resposta.\n"
    "---CONTROL---\n"
    '```json\n{"action": "advance", "objectives_met": []}\n```'
)
result = llm.tutor_turn(PB.PROBLEM, {"step": 1, "prereq": None}, BASIC_TRANSCRIPT)
check("fences strippades, action parsejada",
      result["action"] == "advance")
check("control_parse_ok True", result["control_parse_ok"] is True)


# -----------------------------------------------------------------------------
# Test 8: invariants del transcript
# -----------------------------------------------------------------------------
print("\nTest 8 — invariants del transcript")

raised_empty = False
try:
    llm.tutor_turn(PB.PROBLEM, {}, [])
except ValueError:
    raised_empty = True
check("transcript buit → ValueError", raised_empty)

raised_tutor_last = False
try:
    llm.tutor_turn(PB.PROBLEM, {}, [{"role": "tutor", "content": "X"}])
except ValueError:
    raised_tutor_last = True
check("transcript acabant en tutor → ValueError", raised_tutor_last)


# -----------------------------------------------------------------------------
# Test 9: format multi-turn de `contents` passat a `_call`
# -----------------------------------------------------------------------------
print("\nTest 9 — format multi-turn de contents")
captured = {"contents": None, "system": None}
def capture_call(system, contents):
    captured["system"] = system
    captured["contents"] = contents
    return ("Resposta.\n---CONTROL---\n"
            '{"action": "stay", "objectives_met": []}')
llm._call = capture_call

transcript_4 = [
    {"role": "tutor", "content": "Welcome"},
    {"role": "student", "content": "Resposta 1"},
    {"role": "tutor", "content": "Reformulació"},
    {"role": "student", "content": "Resposta 2"},
]
llm.tutor_turn(PB.PROBLEM, {"step": 1, "prereq": None}, transcript_4)
c = captured["contents"]
check("contents té 4 items", len(c) == 4, f"got {len(c)}")
check("ordre rol: model, user, model, user",
      [t["role"] for t in c] == ["model", "user", "model", "user"])
check("primer text correcte",
      c[0]["parts"][0]["text"] == "Welcome")
check("últim text correcte",
      c[3]["parts"][0]["text"] == "Resposta 2")
check("system_instruction passat", captured["system"] is not None)


# -----------------------------------------------------------------------------
# Test 10: càrrega i interpolació del system prompt
# -----------------------------------------------------------------------------
print("\nTest 10 — càrrega i interpolació del system prompt")
llm._system_prompt_cache = None  # invalidar cache per al test
sp = llm._load_system_prompt()
check("PROBLEM_ENUNCIAT substituït",
      PB.PROBLEM["enunciat"] in sp)
check("STEP1_TEXT substituït",
      PB.PROBLEM["passos"][0]["text"] in sp)
check("STEP1_EXPECTED substituït",
      PB.PROBLEM["passos"][0]["expected_summary"] in sp)
check("STEP3_TYPICAL_ERROR substituït",
      PB.PROBLEM["passos"][2]["typical_error"] in sp)
import re
unresolved = re.findall(r"\{\{[A-Z_0-9]+\}\}", sp)
check("cap placeholder {{...}} sense resoldre",
      unresolved == [], f"unresolved: {unresolved}")


# -----------------------------------------------------------------------------
# Test 11: text estrany abans/després del separador
# -----------------------------------------------------------------------------
print("\nTest 11 — robustesa amb espais/blanks al voltant")
llm._call = stub(
    "  Text amb espais a l'inici i final.   \n\n"
    "---CONTROL---\n\n"
    '   {"action": "advance", "objectives_met": []}   \n\n'
)
result = llm.tutor_turn(PB.PROBLEM, {"step": 1, "prereq": None}, BASIC_TRANSCRIPT)
check("reply strippat correctament",
      result["reply"] == "Text amb espais a l'inici i final.")
check("action parsejada", result["action"] == "advance")


# -----------------------------------------------------------------------------
# Test 12: el reply MAI inclou el control block
# -----------------------------------------------------------------------------
print("\nTest 12 — el reply mai filtra el control block")
# Aquest cas és crític per la UX: si el reply contingués el JSON,
# l'alumne ho veuria a la pantalla.
samples = [
    ('Reply normal.\n---CONTROL---\n{"action":"stay","objectives_met":[]}',
     "stay"),
    ('Reply.\n---CONTROL---\n{"action":"advance","objectives_met":["a"]}',
     "advance"),
    ('Multi\nlínia\nreply.\n\n---CONTROL---\n{"action":"stay","objectives_met":[]}',
     "stay"),
]
for i, (raw, expected_action) in enumerate(samples):
    llm._call = stub(raw)
    result = llm.tutor_turn(PB.PROBLEM, {"step": 1, "prereq": None}, BASIC_TRANSCRIPT)
    check(f"sample {i+1}: control no apareix al reply",
          '"action"' not in result["reply"] and "---CONTROL---" not in result["reply"])
    check(f"sample {i+1}: action correcta",
          result["action"] == expected_action)


# -----------------------------------------------------------------------------
# Resum
# -----------------------------------------------------------------------------
print()
print("=" * 60)
print(f"Tests passats: {PASSED}")
print(f"Tests fallits: {FAILED}")
if FAILED:
    print()
    print("Detalls de les fallades:")
    for d in FAILED_DETAILS:
        print(f"  - {d}")
print("=" * 60)
sys.exit(0 if FAILED == 0 else 1)
