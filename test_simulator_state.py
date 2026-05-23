"""
test_simulator_state.py — tests aïllats de la màquina d'estats del
simulator. NO crida Gemini; només verifica que apply_action() actualitza
l'estat correctament per a totes les transicions.

Executar:
    python3 test_simulator_state.py
"""

import os
import sys
import types

# Stubs per evitar dependència de google.genai i de la clau
sys.modules["google"] = types.ModuleType("google")
sys.modules["google.genai"] = types.ModuleType("google.genai")
sys.modules["google.genai.types"] = types.ModuleType("google.genai.types")
sys.modules["google.api_core"] = types.ModuleType("google.api_core")
sys.modules["google.api_core.exceptions"] = types.ModuleType("google.api_core.exceptions")
os.environ.setdefault("GEMINI_API_KEY", "fake-key-for-tests")

import simulator as S
import problem as PB

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


# -----------------------------------------------------------------------------
# Test 1: estat inicial coherent
# -----------------------------------------------------------------------------
print("\nTest 1 — estat inicial coherent")
state = S.new_session()
check("transcript té 1 element (opening)", len(state["transcript"]) == 1)
check("opening és role=tutor", state["transcript"][0]["role"] == "tutor")
check("current_step és 1", state["current_step"] == 1)
check("active_prereq és None", state["active_prereq"] is None)
check("step_before_prereq és None", state["step_before_prereq"] is None)
check("finished és False", state["finished"] is False)
check("turn_count és 0", state["turn_count"] == 0)


# -----------------------------------------------------------------------------
# Test 2: action="stay" no canvia res
# -----------------------------------------------------------------------------
print("\nTest 2 — action='stay' no modifica l'estat")
state = S.new_session()
snapshot = dict(state)
del snapshot["transcript"]
del snapshot["history"]
S.apply_action(state, "stay")
new_snapshot = dict(state)
del new_snapshot["transcript"]
del new_snapshot["history"]
check("estat sense canvis", snapshot == new_snapshot)


# -----------------------------------------------------------------------------
# Test 3: action="advance" del pas 1 al pas 2
# -----------------------------------------------------------------------------
print("\nTest 3 — advance de pas 1 → pas 2")
state = S.new_session()
S.apply_action(state, "advance")
check("current_step ara és 2", state["current_step"] == 2)
check("active_prereq segueix None", state["active_prereq"] is None)
check("finished segueix False", state["finished"] is False)


# -----------------------------------------------------------------------------
# Test 4: action="advance" del pas 2 al pas 3
# -----------------------------------------------------------------------------
print("\nTest 4 — advance de pas 2 → pas 3")
state = S.new_session()
state["current_step"] = 2
S.apply_action(state, "advance")
check("current_step ara és 3", state["current_step"] == 3)
check("finished segueix False", state["finished"] is False)


# -----------------------------------------------------------------------------
# Test 5: action="advance" des de l'últim pas finalitza
# -----------------------------------------------------------------------------
print("\nTest 5 — advance de pas 3 → finished=True")
state = S.new_session()
state["current_step"] = 3
S.apply_action(state, "advance")
check("current_step segueix 3", state["current_step"] == 3,
      f"got {state['current_step']}")
check("finished és True", state["finished"] is True)


# -----------------------------------------------------------------------------
# Test 6: retreat des de pas 1 activa el reforç
# -----------------------------------------------------------------------------
print("\nTest 6 — retreat_to_prereq des de pas 1")
state = S.new_session()
S.apply_action(state, "retreat_to_prereq")
check("active_prereq ara és PRE-PARAM",
      state["active_prereq"] == S.PREREQ_ID)
check("step_before_prereq guardat com a 1",
      state["step_before_prereq"] == 1)
check("current_step preservat", state["current_step"] == 1)


# -----------------------------------------------------------------------------
# Test 7: retreat des de pas 2 guarda 2 com a retorn
# -----------------------------------------------------------------------------
print("\nTest 7 — retreat_to_prereq des de pas 2")
state = S.new_session()
state["current_step"] = 2
S.apply_action(state, "retreat_to_prereq")
check("step_before_prereq guardat com a 2",
      state["step_before_prereq"] == 2)


# -----------------------------------------------------------------------------
# Test 8: advance dins del reforç torna al pas guardat
# -----------------------------------------------------------------------------
print("\nTest 8 — advance des del reforç torna al pas que el va activar")
state = S.new_session()
state["current_step"] = 2
S.apply_action(state, "retreat_to_prereq")
check("primer setup correcte: a prereq, ve de pas 2",
      state["active_prereq"] == S.PREREQ_ID and state["step_before_prereq"] == 2)
S.apply_action(state, "advance")
check("active_prereq tornat a None", state["active_prereq"] is None)
check("step_before_prereq netejat", state["step_before_prereq"] is None)
check("current_step és 2 (retorn correcte)", state["current_step"] == 2)


# -----------------------------------------------------------------------------
# Test 9: retreat dins del reforç és no-op
# -----------------------------------------------------------------------------
print("\nTest 9 — retreat_to_prereq mentre ja és a prereq és no-op")
state = S.new_session()
state["current_step"] = 1
S.apply_action(state, "retreat_to_prereq")  # 1 → prereq
saved_step = state["step_before_prereq"]
S.apply_action(state, "retreat_to_prereq")  # no-op
check("step_before_prereq no s'ha sobreescrit",
      state["step_before_prereq"] == saved_step)
check("active_prereq segueix actiu", state["active_prereq"] == S.PREREQ_ID)


# -----------------------------------------------------------------------------
# Test 10: position_dict i position_summary coherents
# -----------------------------------------------------------------------------
print("\nTest 10 — funcions de posició")
state = S.new_session()
pd = S.position_dict(state)
check("position_dict: step=1, prereq=None",
      pd == {"step": 1, "prereq": None})

state_p = S.new_session()
S.apply_action(state_p, "retreat_to_prereq")
pd_p = S.position_dict(state_p)
check("position_dict en prereq: prereq=PRE-PARAM",
      pd_p["prereq"] == "PRE-PARAM")

ps = S.position_summary(state)
check("position_summary inclou 'pas 1'", "pas 1" in ps)
ps_p = S.position_summary(state_p)
check("position_summary en prereq inclou 'reforç'", "reforç" in ps_p)

state_f = S.new_session()
state_f["finished"] = True
check("position_summary quan finished",
      "acabada" in S.position_summary(state_f))


# -----------------------------------------------------------------------------
# Test 11: position_summary_from amb dict aïllat
# -----------------------------------------------------------------------------
print("\nTest 11 — position_summary_from amb dicts aïllats")
ps = S.position_summary_from({"step": 2, "prereq": None})
check("pas 2 al text", "pas 2" in ps)
ps = S.position_summary_from({"step": 2, "prereq": "PRE-PARAM"})
check("reforç prioritzat sobre pas", "reforç" in ps)


# -----------------------------------------------------------------------------
# Test 12: trajectòria completa simulada (sense LLM)
# -----------------------------------------------------------------------------
print("\nTest 12 — trajectòria completa amb seqüència d'accions")
state = S.new_session()
# Alumne: pas 1, model retreats
S.apply_action(state, "retreat_to_prereq")
# Alumne dins reforç, model fa stay
S.apply_action(state, "stay")
# Alumne dins reforç, model fa stay
S.apply_action(state, "stay")
# Alumne demostra concepte, model advances
S.apply_action(state, "advance")
check("retorn a pas 1 després del reforç",
      state["current_step"] == 1 and state["active_prereq"] is None)
# Alumne resol pas 1
S.apply_action(state, "advance")
check("avenç a pas 2", state["current_step"] == 2)
# Pas 2
S.apply_action(state, "advance")
check("avenç a pas 3", state["current_step"] == 3)
# Pas 3
S.apply_action(state, "advance")
check("finalització després del pas 3", state["finished"] is True)


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
