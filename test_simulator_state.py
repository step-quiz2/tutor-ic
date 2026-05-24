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
# Test 13 (quality_signals): sessió buida
# -----------------------------------------------------------------------------
print("\nTest 13 — quality_signals d'una sessió buida (no history)")
state = S.new_session()
qs = S.compute_quality_signals(state)
check("completed False", qs["completed"] is False)
check("total_turns_llm 0", qs["total_turns_llm"] == 0)
check("action_counts tots a zero",
      qs["action_counts"] == {"stay": 0, "advance": 0, "retreat_to_prereq": 0})
check("stay_advance_ratio és None (no advances)",
      qs["stay_advance_ratio"] is None)
check("turns_per_step tot a zero",
      all(v == 0 for v in qs["turns_per_step"].values()))
check("used_prereq False", qs["used_prereq"] is False)
check("hint_requests 0", qs["hint_requests"] == 0)
check("parse_failures 0", qs["parse_failures"] == 0)


# -----------------------------------------------------------------------------
# Test 14 (quality_signals): sessió amb dades reals d'alumne1 (3 advances)
# -----------------------------------------------------------------------------
print("\nTest 14 — quality_signals d'una sessió amb 3 advances seguits")
state = S.new_session()
# Simulem la trajectòria de l'alumne1: 3 torns, tots advance
fake_history = [
    {
        "turn": 1, "student_msg": "Resposta 1",
        "action": "advance", "objectives_met": [],
        "control_parse_ok": True,
        "position_before": {"step": 1, "prereq": None},
        "position_after": {"step": 2, "prereq": None},
        "elapsed_seconds": 1.5,
    },
    {
        "turn": 2, "student_msg": "Resposta 2",
        "action": "advance", "objectives_met": [],
        "control_parse_ok": True,
        "position_before": {"step": 2, "prereq": None},
        "position_after": {"step": 3, "prereq": None},
        "elapsed_seconds": 2.0,
    },
    {
        "turn": 3, "student_msg": "Resposta 3",
        "action": "advance", "objectives_met": [],
        "control_parse_ok": True,
        "position_before": {"step": 3, "prereq": None},
        "position_after": {"step": 3, "prereq": None},
        "elapsed_seconds": 1.0,
    },
]
state["history"] = fake_history
state["turn_count"] = 3
state["finished"] = True

qs = S.compute_quality_signals(state)
check("completed True", qs["completed"] is True)
check("total_turns_llm 3", qs["total_turns_llm"] == 3)
check("advance count 3", qs["action_counts"]["advance"] == 3)
check("stay count 0", qs["action_counts"]["stay"] == 0)
check("stay_advance_ratio 0.0", qs["stay_advance_ratio"] == 0.0)
check("turns per step 1=1, 2=1, 3=1",
      qs["turns_per_step"] == {1: 1, 2: 1, 3: 1})
check("used_prereq False", qs["used_prereq"] is False)
check("avg_elapsed = 1.5", qs["avg_elapsed_seconds_per_turn"] == 1.5)


# -----------------------------------------------------------------------------
# Test 15 (quality_signals): sessió amb stays, retreat, pista i parse fail
# -----------------------------------------------------------------------------
print("\nTest 15 — quality_signals amb tot l'arsenal d'esdeveniments")
state = S.new_session()
state["history"] = [
    # 2 stays al pas 1
    {"turn": 1, "student_msg": "Resp 1", "action": "stay",
     "objectives_met": [], "control_parse_ok": True,
     "position_before": {"step": 1, "prereq": None},
     "position_after": {"step": 1, "prereq": None}, "elapsed_seconds": 1.0},
    {"turn": 2, "student_msg": "Resp 2", "action": "stay",
     "objectives_met": [], "control_parse_ok": False,  # parse fail!
     "position_before": {"step": 1, "prereq": None},
     "position_after": {"step": 1, "prereq": None}, "elapsed_seconds": 1.0},
    # Retreat
    {"turn": 3, "student_msg": "Resp 3", "action": "retreat_to_prereq",
     "objectives_met": [], "control_parse_ok": True,
     "position_before": {"step": 1, "prereq": None},
     "position_after": {"step": 1, "prereq": "PRE-PARAM"},
     "elapsed_seconds": 2.0},
    # 2 torns dins reforç
    {"turn": 4, "student_msg": "(L'alumne demana una pista)",  # pista!
     "action": "stay", "objectives_met": [], "control_parse_ok": True,
     "position_before": {"step": 1, "prereq": "PRE-PARAM"},
     "position_after": {"step": 1, "prereq": "PRE-PARAM"},
     "elapsed_seconds": 1.5},
    {"turn": 5, "student_msg": "Resp 5", "action": "advance",
     "objectives_met": [], "control_parse_ok": True,
     "position_before": {"step": 1, "prereq": "PRE-PARAM"},
     "position_after": {"step": 1, "prereq": None},
     "elapsed_seconds": 1.0},
    # Avancen fins finalitzar
    {"turn": 6, "student_msg": "Resp 6", "action": "advance",
     "objectives_met": [], "control_parse_ok": True,
     "position_before": {"step": 1, "prereq": None},
     "position_after": {"step": 2, "prereq": None}, "elapsed_seconds": 1.0},
]
state["turn_count"] = 6
state["finished"] = False

qs = S.compute_quality_signals(state)
check("stay count 3", qs["action_counts"]["stay"] == 3)
check("advance count 2", qs["action_counts"]["advance"] == 2)
check("retreat count 1", qs["action_counts"]["retreat_to_prereq"] == 1)
check("stay/advance ratio 1.5",
      qs["stay_advance_ratio"] == 1.5)
check("turns at step 1 (no prereq) = 4",
      qs["turns_per_step"][1] == 4,
      f"got {qs['turns_per_step']}")
check("turns_in_prereq = 2",
      qs["turns_in_prereq"] == 2)
check("used_prereq True", qs["used_prereq"] is True)
check("hint_requests = 1", qs["hint_requests"] == 1)
check("parse_failures = 1", qs["parse_failures"] == 1)


# -----------------------------------------------------------------------------
# Test 16 (quality_signals): format_quality_signals retorna text llegible
# -----------------------------------------------------------------------------
print("\nTest 16 — format_quality_signals dóna text llegible")
qs = {
    "completed": True, "total_turns_llm": 3,
    "elapsed_seconds_total": 5.5, "avg_elapsed_seconds_per_turn": 1.83,
    "action_counts": {"stay": 1, "advance": 2, "retreat_to_prereq": 0},
    "stay_advance_ratio": 0.5,
    "turns_per_step": {1: 1, 2: 2, 3: 0},
    "used_prereq": False, "turns_in_prereq": 0,
    "hint_requests": 0, "parse_failures": 0,
}
text = S.format_quality_signals(qs)
check("conté 'Quality signals'", "Quality signals" in text)
check("conté 'Completat: True'", "Completat: True" in text)
check("conté ràtio formatada", "0.50" in text)
check("conté 'Torns LLM: 3'", "Torns LLM: 3" in text)
check("línies múltiples", "\n" in text)

# Ràtio None es mostra 'n/a'
qs_no_advance = dict(qs)
qs_no_advance["stay_advance_ratio"] = None
text2 = S.format_quality_signals(qs_no_advance)
check("ràtio None es renderitza 'n/a'", "n/a" in text2)


# -----------------------------------------------------------------------------
# Test 17 (quality_signals): elapsed_total amb timestamps reals
# -----------------------------------------------------------------------------
# Regressió: a una versió anterior, elapsed_seconds_total es calculava
# com time.time() - started_at, donant temps falsos si es processava un
# JSON desat hores després. Verifiquem que ara fa servir history[-1].ts
# si està present.
print("\nTest 17 — elapsed_seconds_total prové del timestamp del darrer torn")
state = S.new_session()
# Inicialitzem started_at i ts a valors fixes (com si fos un JSON desat)
state["started_at"] = 1000.0
state["history"] = [
    {"turn": 1, "student_msg": "x", "action": "advance",
     "objectives_met": [], "control_parse_ok": True,
     "position_before": {"step": 1, "prereq": None},
     "position_after": {"step": 2, "prereq": None},
     "elapsed_seconds": 1.0, "ts": 1015.0},  # 15s després
]
state["turn_count"] = 1
qs = S.compute_quality_signals(state)
check("elapsed_total = ts_last - started_at = 15.0",
      qs["elapsed_seconds_total"] == 15.0,
      f"got {qs['elapsed_seconds_total']}")

# Cas sense ts al rastre (rastres antics o sintètics): cau a la suma
# d'elapsed_seconds.
state["history"] = [
    {"turn": 1, "student_msg": "x", "action": "stay",
     "objectives_met": [], "control_parse_ok": True,
     "position_before": {"step": 1, "prereq": None},
     "position_after": {"step": 1, "prereq": None},
     "elapsed_seconds": 2.5},
    {"turn": 2, "student_msg": "y", "action": "stay",
     "objectives_met": [], "control_parse_ok": True,
     "position_before": {"step": 1, "prereq": None},
     "position_after": {"step": 1, "prereq": None},
     "elapsed_seconds": 1.5},
]
qs2 = S.compute_quality_signals(state)
check("sense ts → suma d'elapsed_seconds",
      qs2["elapsed_seconds_total"] == 4.0,
      f"got {qs2['elapsed_seconds_total']}")


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
