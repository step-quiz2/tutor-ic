"""
test_diagnostic.py — Tasca 4: el control block retorna un diagnòstic.

Verifica les dues garanties crítiques de l'spec (improve.MD, Task 4):

  A) Tolerància del parser i normalització del caller:
       - diagnostic present i vàlid → es propaga
       - absent / null / tipus erroni / codi desconegut → no peta i no
         marca control_parse_ok=False per ell mateix
       - codi fora del catàleg → GEN_other (normalització al caller)
       - action="advance" → diagnostic forçat a None

  B) Invariància del flux:
       - apply_action produeix EXACTAMENT la mateixa transició tant si
         el resultat porta diagnostic com si no. El diagnòstic és
         metadada; mai toca la màquina d'estats.

Executar des del directori del projecte:
    python3 test_diagnostic.py
"""

import os
import sys
import types

# Stubs perquè l'import de google.genai no falli (mateix patró que
# test_tutor_turn.py). El client real no es construeix mai: _call es
# sobreescriu als tests.
sys.modules["google"] = types.ModuleType("google")
sys.modules["google.genai"] = types.ModuleType("google.genai")
sys.modules["google.genai.types"] = types.ModuleType("google.genai.types")
sys.modules["google.api_core"] = types.ModuleType("google.api_core")
sys.modules["google.api_core.exceptions"] = types.ModuleType(
    "google.api_core.exceptions"
)

os.environ.setdefault("GEMINI_API_KEY", "fake-key-for-tests")

import llm  # noqa: E402
import problem as PB  # noqa: E402
import simulator as S  # noqa: E402


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
    def _stub(*args, **kwargs):
        return text
    return _stub


PID = "CAUS-001"
PROBLEM = PB.get(PID)["problem"]
# Un codi real del catàleg de CAUS-001 i un que NO hi és.
REAL_CODE = "CAUS_direct"
UNKNOWN_CODE = "ZZZ_not_a_real_code"

BASIC_TRANSCRIPT = [
    {"role": "tutor", "content": "Comencem: la diferència de taxes implica causa?"},
    {"role": "student", "content": "sí, l'origen migrat causa més abandonament directament"},
]


def run_turn(control_json):
    """Fa un tutor_turn amb _call stubejat a un raw amb el control donat,
    en posició Pas 1 de CAUS-001."""
    raw = (
        "Pensa-ho millor. La diferència de taxes no implica causa.\n\n"
        "---CONTROL---\n" + control_json
    )
    llm._call = stub(raw)
    return llm.tutor_turn(PROBLEM, {"step": 1, "prereq": None},
                          list(BASIC_TRANSCRIPT))


# -----------------------------------------------------------------------------
# A) Parser + normalització
# -----------------------------------------------------------------------------
print("\n[A] Parser i normalització del diagnòstic")

# A1 — diagnostic vàlid del catàleg, amb stay → es propaga tal qual.
r = run_turn('{"action": "stay", "diagnostic": "%s"}' % REAL_CODE)
check("A1 codi vàlid + stay → es propaga",
      r["diagnostic"] == REAL_CODE and r["action"] == "stay",
      f"diagnostic={r['diagnostic']!r}")
check("A1 control_parse_ok True", r["control_parse_ok"] is True)

# A2 — diagnostic absent → None, sense marcar parse error.
r = run_turn('{"action": "stay"}')
check("A2 absent → None", r["diagnostic"] is None)
check("A2 absència NO marca parse_error", r["control_parse_ok"] is True)

# A3 — diagnostic null explícit → None.
r = run_turn('{"action": "stay", "diagnostic": null}')
check("A3 null → None", r["diagnostic"] is None,
      f"diagnostic={r['diagnostic']!r}")
check("A3 control_parse_ok True", r["control_parse_ok"] is True)

# A4 — diagnostic de tipus erroni (número) → None, sense petar.
r = run_turn('{"action": "stay", "diagnostic": 42}')
check("A4 tipus erroni → None", r["diagnostic"] is None)
check("A4 control_parse_ok True", r["control_parse_ok"] is True)

# A5 — diagnostic de tipus erroni (llista) → None.
r = run_turn('{"action": "stay", "diagnostic": ["a","b"]}')
check("A5 llista → None", r["diagnostic"] is None)

# A6 — codi desconegut (string fora del catàleg) → GEN_other.
r = run_turn('{"action": "stay", "diagnostic": "%s"}' % UNKNOWN_CODE)
check("A6 codi desconegut → GEN_other",
      r["diagnostic"] == PB.GEN_OTHER,
      f"diagnostic={r['diagnostic']!r}")
check("A6 control_parse_ok True", r["control_parse_ok"] is True)

# A7 — action=advance ignora qualsevol diagnostic (forçat a None).
r = run_turn('{"action": "advance", "diagnostic": "%s"}' % REAL_CODE)
check("A7 advance força diagnostic=None",
      r["diagnostic"] is None and r["action"] == "advance",
      f"diagnostic={r['diagnostic']!r}")

# A8 — JSON malformat → parse error, action stay, diagnostic None.
r = run_turn('{"action": "stay", "diagnostic": ')
check("A8 JSON malformat → stay", r["action"] == "stay")
check("A8 JSON malformat marca parse_error", r["control_parse_ok"] is False)
check("A8 JSON malformat → diagnostic None", r["diagnostic"] is None)

# A9 — diagnostic dins de fences ```json també es parseja.
raw_fenced = (
    "Reflexiona-hi.\n\n---CONTROL---\n"
    "```json\n{\"action\": \"stay\", \"diagnostic\": \"%s\"}\n```" % REAL_CODE
)
llm._call = stub(raw_fenced)
r = llm.tutor_turn(PROBLEM, {"step": 1, "prereq": None}, list(BASIC_TRANSCRIPT))
check("A9 fences ```json → codi propagat", r["diagnostic"] == REAL_CODE)

# A10 — el parser pur exposa diagnostic en cru, sense validar.
ctrl = llm._parse_control_block('{"action":"stay","diagnostic":"%s"}'
                                % UNKNOWN_CODE)
check("A10 parser NO valida (deixa el codi cru)",
      ctrl["diagnostic"] == UNKNOWN_CODE,
      f"parser diagnostic={ctrl['diagnostic']!r}")

# A11 — normalize_diagnostic: contracte directe.
check("A11 normalize None → None",
      PB.normalize_diagnostic(PID, 1, None) is None)
check("A11 normalize '' → None",
      PB.normalize_diagnostic(PID, 1, "") is None)
check("A11 normalize codi real → mateix",
      PB.normalize_diagnostic(PID, 1, REAL_CODE) == REAL_CODE)
check("A11 normalize desconegut → GEN_other",
      PB.normalize_diagnostic(PID, 1, UNKNOWN_CODE) == PB.GEN_OTHER)

# A12 — allowed_diagnostics inclou GEN_other i els codis reals.
opts = PB.allowed_diagnostics(PID, 1)
check("A12 allowed_diagnostics inclou GEN_other", PB.GEN_OTHER in opts)
check("A12 allowed_diagnostics inclou codi real", REAL_CODE in opts)


# -----------------------------------------------------------------------------
# B) Invariància del flux: apply_action ignora el diagnòstic
# -----------------------------------------------------------------------------
print("\n[B] Invariància del flux (apply_action ignora diagnostic)")


def fresh_state():
    return S.new_session(PID)


def transition_signature(state):
    return (state["current_step"], state["active_prereq"],
            state["step_before_prereq"], state["finished"])


# Per cada acció, la transició ha de ser idèntica tant si abans hem
# "registrat" un diagnòstic com si no. apply_action ni tan sols rep el
# diagnòstic — aquest test documenta i blinda aquesta separació.
for action in ("stay", "advance", "retreat_to_prereq"):
    s_no_diag = fresh_state()
    t1 = S.apply_action(s_no_diag, action)
    sig1 = transition_signature(s_no_diag)

    s_with_diag = fresh_state()
    # Simulem que el torn portava un diagnòstic (com faria tutor_turn):
    # l'anotem al rastre, com fa el caller real, abans d'aplicar l'acció.
    s_with_diag["history"].append({"diagnostic": REAL_CODE})
    t2 = S.apply_action(s_with_diag, action)
    sig2 = transition_signature(s_with_diag)

    check(f"B {action}: mateix codi de transició", t1 == t2,
          f"{t1!r} != {t2!r}")
    check(f"B {action}: mateix estat resultant", sig1 == sig2,
          f"{sig1!r} != {sig2!r}")


# -----------------------------------------------------------------------------
# C) quality_signals agrega diagnòstics
# -----------------------------------------------------------------------------
print("\n[C] compute_quality_signals agrega diagnòstics")

st = fresh_state()
# Tres torns sintètics al Pas 1: dos amb CAUS_direct, un amb GEN_other.
st["history"] = [
    {"action": "stay", "diagnostic": "CAUS_direct",
     "position_before": {"step": 1, "prereq": None},
     "control_parse_ok": True, "student_msg": "x"},
    {"action": "stay", "diagnostic": "CAUS_direct",
     "position_before": {"step": 1, "prereq": None},
     "control_parse_ok": True, "student_msg": "y"},
    {"action": "stay", "diagnostic": "GEN_other",
     "position_before": {"step": 1, "prereq": None},
     "control_parse_ok": True, "student_msg": "z"},
    {"action": "advance", "diagnostic": None,
     "position_before": {"step": 1, "prereq": None},
     "control_parse_ok": True, "student_msg": "w"},
]
qs = S.compute_quality_signals(st)
check("C diagnostic_counts compta CAUS_direct=2",
      qs["diagnostic_counts"].get("CAUS_direct") == 2,
      f"counts={qs['diagnostic_counts']}")
check("C diagnostic_counts ignora None",
      None not in qs["diagnostic_counts"])
check("C dominant del Pas 1 és CAUS_direct",
      qs["dominant_diagnostic_per_step"].get(1) == "CAUS_direct",
      f"dominant={qs['dominant_diagnostic_per_step']}")


# -----------------------------------------------------------------------------
# D) Fallback (mode reserva) sempre porta el camp diagnostic
# -----------------------------------------------------------------------------
print("\n[D] Mode de reserva inclou el camp diagnostic")

# Forcem mode reserva temporalment.
_orig = llm.ia_disponible
llm.ia_disponible = lambda: False
try:
    r = llm.tutor_turn(PROBLEM, {"step": 1, "prereq": None},
                       list(BASIC_TRANSCRIPT))
    check("D fallback retorna clau 'diagnostic'", "diagnostic" in r)
    check("D fallback mode == py", r.get("mode") == "py")
    # Resposta clarament errònia → stay → diagnòstic probable del pas (no peta).
    check("D fallback no peta i té action vàlida",
          r["action"] in ("stay", "advance", "retreat_to_prereq"))
finally:
    llm.ia_disponible = _orig


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
