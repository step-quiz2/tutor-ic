"""
test_enrichment.py — tests del transvasament d'arquitectura des de
tutor-div (A) cap a tutor-ic (B).

Cobreix:
  - els codis de transició que retorna apply_action,
  - la injecció determinista de la pregunta canònica
    (simulator.enrich_after_transition) en avançar i en retrocedir,
  - l'anti-duplicació quan el model ja ha escrit la pregunta,
  - el registre `display` amb el camp `source`,
  - els accessors de problem.py (canonical_question / step_hints /
    prereq_question),
  - el mode de reserva de llm.tutor_turn (sense IA).

Executar:
    python3 test_enrichment.py
"""

import os
import sys
import types

# Stubs perquè els imports funcionin sense google.genai ni clau real.
sys.modules["google"] = types.ModuleType("google")
sys.modules["google.genai"] = types.ModuleType("google.genai")
sys.modules["google.genai.types"] = types.ModuleType("google.genai.types")
sys.modules["google.api_core"] = types.ModuleType("google.api_core")
sys.modules["google.api_core.exceptions"] = types.ModuleType(
    "google.api_core.exceptions"
)

import simulator as S  # noqa: E402
import problem as PB    # noqa: E402
import llm as L         # noqa: E402


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


def _raises(fn, exc):
    try:
        fn()
        return False
    except exc:
        return True
    except Exception:
        return False


def _last_py_bubble(state):
    for b in reversed(state["display"]):
        if b["source"] == "py" and b["role"] == "tutor":
            return b
    return None


# -----------------------------------------------------------------------------
print("\n--- Accessors de problem.py ---")

for pid in ("IC-001", "CAUS-001"):
    for n in (1, 2, 3):
        q = PB.canonical_question(pid, n)
        h = PB.step_hints(pid, n)
        check(f"{pid} pas {n}: canonical_question no buida", bool(q), repr(q))
        check(f"{pid} pas {n}: té almenys 1 pista", len(h) >= 1, f"{len(h)}")
    check(f"{pid}: prereq_question no buida", bool(PB.prereq_question(pid)))

check("canonical_question fora de rang llança IndexError",
      _raises(lambda: PB.canonical_question("IC-001", 9), IndexError))


# -----------------------------------------------------------------------------
print("\n--- new_session inclou display amb opening determinista ---")

st = S.new_session("IC-001")
check("display existeix", "display" in st)
check("display[0] és tutor/py",
      st["display"][0]["role"] == "tutor" and st["display"][0]["source"] == "py")
check("transcript i display comencen sincronitzats",
      st["transcript"][0]["content"] == st["display"][0]["content"])


# -----------------------------------------------------------------------------
print("\n--- apply_action retorna codis de transició ---")

st = S.new_session("IC-001")
check("stay → 'stay'", S.apply_action(st, "stay") == "stay")

st = S.new_session("IC-001")
check("advance des de pas 1 → 'next_step'",
      S.apply_action(st, "advance") == "next_step" and st["current_step"] == 2)

st = S.new_session("IC-001")
st["current_step"] = 3
check("advance des de l'últim pas → 'finished'",
      S.apply_action(st, "advance") == "finished" and st["finished"])

st = S.new_session("IC-001")
check("retreat des de pas → 'enter_prereq'",
      S.apply_action(st, "retreat_to_prereq") == "enter_prereq"
      and st["active_prereq"] == "PRE-PARAM")
check("retreat dins reforç → 'noop'",
      S.apply_action(st, "retreat_to_prereq") == "noop")
check("advance dins reforç → 'exit_prereq'",
      S.apply_action(st, "advance") == "exit_prereq"
      and st["active_prereq"] is None)


# -----------------------------------------------------------------------------
print("\n--- enrich_after_transition injecta la pregunta canònica ---")

# Simulem un torn complet: alumne respon, tutor (model) felicita SENSE
# escriure la pregunta del pas següent, Python l'ha d'injectar.
st = S.new_session("IC-001")
S.append_display(st, "student", "el 95% és del procediment", "student")
st["transcript"].append({"role": "student", "content": "el 95% és del procediment"})
reply = "Molt bé! Has clavat la idea. Passem al següent."
st["transcript"].append({"role": "tutor", "content": reply})
S.append_display(st, "tutor", reply, "ai")
transition = S.apply_action(st, "advance")
canonical = S.enrich_after_transition(st, transition)

check("enrich retorna la pregunta canònica del pas 2",
      canonical == PB.canonical_question("IC-001", 2), repr(canonical))
py_bubble = _last_py_bubble(st)
check("s'afegeix una bombolla py al display amb la pregunta",
      py_bubble is not None and py_bubble["content"] == canonical)
check("la pregunta s'enganxa també al darrer tutor del transcript",
      canonical in st["transcript"][-1]["content"])
check("el transcript segueix alternant (acaba en tutor)",
      st["transcript"][-1]["role"] == "tutor")


# -----------------------------------------------------------------------------
print("\n--- anti-duplicació: si el model ja ha escrit la pregunta ---")

st = S.new_session("IC-001")
st["transcript"].append({"role": "student", "content": "..."})
# El model SÍ que ha escrit la pregunta canònica del pas 2 al seu reply.
q2 = PB.canonical_question("IC-001", 2)
reply = f"Molt bé. {q2}"
st["transcript"].append({"role": "tutor", "content": reply})
S.append_display(st, "tutor", reply, "ai")
n_py_before = sum(1 for b in st["display"] if b["source"] == "py")
transition = S.apply_action(st, "advance")
canonical = S.enrich_after_transition(st, transition)
n_py_after = sum(1 for b in st["display"] if b["source"] == "py")

check("enrich detecta el duplicat i retorna None", canonical is None)
check("no s'afegeix bombolla py duplicada", n_py_after == n_py_before)


# -----------------------------------------------------------------------------
print("\n--- enrich en retrocés injecta la pregunta del prerequisit ---")

st = S.new_session("CAUS-001")
st["transcript"].append({"role": "student", "content": "no ho entenc"})
st["transcript"].append({"role": "tutor", "content": "Tornem un pas enrere."})
S.append_display(st, "tutor", "Tornem un pas enrere.", "ai")
transition = S.apply_action(st, "retreat_to_prereq")
canonical = S.enrich_after_transition(st, transition)
check("retreat injecta la pregunta del prerequisit",
      canonical == PB.prereq_question("CAUS-001"), repr(canonical))

# En sortir del reforç, torna a injectar la pregunta del pas que el va activar.
transition = S.apply_action(st, "advance")  # exit_prereq → torna a pas 1
canonical = S.enrich_after_transition(st, transition)
check("exit_prereq injecta la pregunta canònica del pas de retorn",
      canonical == PB.canonical_question("CAUS-001", st["current_step"]))


# -----------------------------------------------------------------------------
print("\n--- 'stay' no injecta res ---")

st = S.new_session("IC-001")
st["transcript"].append({"role": "student", "content": "hmm"})
st["transcript"].append({"role": "tutor", "content": "Pensa-ho una mica més."})
S.append_display(st, "tutor", "Pensa-ho una mica més.", "ai")
n_py_before = sum(1 for b in st["display"] if b["source"] == "py")
transition = S.apply_action(st, "stay")
canonical = S.enrich_after_transition(st, transition)
n_py_after = sum(1 for b in st["display"] if b["source"] == "py")
check("stay no retorna pregunta canònica", canonical is None)
check("stay no afegeix bombolla determinista", n_py_after == n_py_before)


# -----------------------------------------------------------------------------
print("\n--- Mode de reserva (sense IA) ---")

# Sense GEMINI_API_KEY → ia_disponible() és False → tutor_turn cau al
# fallback i no crida l'API.
os.environ.pop("GEMINI_API_KEY", None)
check("ia_disponible() és False sense clau", L.ia_disponible() is False)

problem = PB.PROBLEMS["IC-001"]["problem"]
transcript = [
    {"role": "tutor", "content": problem["passos"][0]["text"]},
    {"role": "student", "content": "(L'alumne demana una pista)"},
]
res = L.tutor_turn(problem, {"step": 1, "prereq": None}, transcript)
check("fallback respon amb una pista i es queda (stay)",
      res["action"] == "stay" and "Pista" in res["reply"]
      and res["mode"] == "py" and res["n_api_calls"] == 0)

# Resposta amb prou keywords → el fallback avança.
transcript = [
    {"role": "tutor", "content": problem["passos"][0]["text"]},
    {"role": "student", "content":
        "μ és un paràmetre fix, constant i no aleatori; la mostra varia "
        "i és aleatòria, per això el 95% és del procediment."},
]
res = L.tutor_turn(problem, {"step": 1, "prereq": None}, transcript)
check("fallback avança quan hi ha prou keywords",
      res["action"] == "advance" and res["mode"] == "py")


# -----------------------------------------------------------------------------
print("\n" + "=" * 60)
print(f"Tests passats: {PASSED}")
print(f"Tests fallits: {FAILED}")
print("=" * 60)
if FAILED:
    for d in FAILED_DETAILS:
        print("  -", d)
    sys.exit(1)
