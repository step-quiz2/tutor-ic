"""
test_diagnostic.py — Tasca 4 (div): el control block retorna un diagnòstic.

Verifica les dues garanties crítiques (improve.MD, Task 4):

  A) Tolerància del parser + normalització al caller.
  B) Invariància del flux: tutor.apply_action ignora el diagnòstic.
  C) El mode de reserva sempre porta el camp diagnostic.

No requereix clau d'API. Executar des del directori del projecte:
    python3 test_diagnostic.py
"""

import os

os.environ.pop("GEMINI_API_KEY", None)  # forcem mode de reserva on calgui

import llm
import problems as P
import tutor


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


CAP1 = P.get_capitol(1)
REAL_CODE = "MUL_div_inexacta"      # codi real del catàleg del capítol 1
UNKNOWN_CODE = "ZZZ_not_a_code"

BASIC_TRANSCRIPT = [
    {"role": "tutor", "content": "Quant fa 12 ÷ 3?"},
    {"role": "student", "content": "ui no ho sé"},
]


def run_turn(control_json, force_ai=True):
    """tutor_turn amb _call stubejat, en posició Capítol 1 · Pas 1.
    Forcem mode IA perquè el camí de parse s'exerceixi."""
    raw = "Provem-ho amb calma.\n\n---CONTROL---\n" + control_json
    llm._call = stub(raw)
    if force_ai:
        llm.ia_disponible = lambda: True
        # _get_client no s'invoca perquè _call està stubejat.
    return llm.tutor_turn(
        CAP1, {"capitol": 1, "pas": 1}, list(BASIC_TRANSCRIPT), cap_total=4
    )


# -----------------------------------------------------------------------------
print("\n[A] Parser i normalització del diagnòstic")

_orig_disp = llm.ia_disponible

r = run_turn('{"action": "stay", "diagnostic": "%s"}' % REAL_CODE)
check("A1 codi vàlid + stay → es propaga",
      r["diagnostic"] == REAL_CODE and r["action"] == "stay",
      f"diagnostic={r['diagnostic']!r}")
check("A1 control_parse_ok True", r["control_parse_ok"] is True)

r = run_turn('{"action": "stay"}')
check("A2 absent → None", r["diagnostic"] is None)
check("A2 absència NO marca parse_error", r["control_parse_ok"] is True)

r = run_turn('{"action": "stay", "diagnostic": null}')
check("A3 null → None", r["diagnostic"] is None)

r = run_turn('{"action": "stay", "diagnostic": 42}')
check("A4 tipus erroni → None", r["diagnostic"] is None)
check("A4 control_parse_ok True", r["control_parse_ok"] is True)

r = run_turn('{"action": "stay", "diagnostic": "%s"}' % UNKNOWN_CODE)
check("A5 codi desconegut → GEN_other", r["diagnostic"] == P.GEN_OTHER,
      f"diagnostic={r['diagnostic']!r}")

r = run_turn('{"action": "advance", "diagnostic": "%s"}' % REAL_CODE)
check("A6 advance força diagnostic=None",
      r["diagnostic"] is None and r["action"] == "advance")

r = run_turn('{"action": "stay", "diagnostic": ')
check("A7 JSON malformat → stay", r["action"] == "stay")
check("A7 JSON malformat marca parse_error", r["control_parse_ok"] is False)
check("A7 JSON malformat → diagnostic None", r["diagnostic"] is None)

# Parser pur: deixa el codi cru, sense validar.
ctrl = llm._parse_control_block('{"action":"stay","diagnostic":"%s"}'
                                % UNKNOWN_CODE)
check("A8 parser NO valida (codi cru)", ctrl["diagnostic"] == UNKNOWN_CODE)

# normalize_diagnostic — contracte directe.
check("A9 normalize None → None", P.normalize_diagnostic(CAP1, None) is None)
check("A9 normalize codi real → mateix",
      P.normalize_diagnostic(CAP1, REAL_CODE) == REAL_CODE)
check("A9 normalize desconegut → GEN_other",
      P.normalize_diagnostic(CAP1, UNKNOWN_CODE) == P.GEN_OTHER)

# allowed_diagnostics — GEN_other al final, inclou codi real.
opts = P.allowed_diagnostics(CAP1)
check("A10 allowed inclou GEN_other (al final)", opts[-1] == P.GEN_OTHER)
check("A10 allowed inclou codi real", REAL_CODE in opts)

llm.ia_disponible = _orig_disp


# -----------------------------------------------------------------------------
print("\n[B] Invariància del flux (apply_action ignora diagnostic)")


def transition_signature(state):
    return (state["cap_idx"], state["pas_idx"], state["finished"])


for action in ("stay", "advance"):
    s1 = tutor.new_session()
    t1 = tutor.apply_action(s1, action)
    sig1 = transition_signature(s1)

    s2 = tutor.new_session()
    # Simulem un diagnòstic anotat al rastre (com fa el caller real) abans
    # d'aplicar l'acció. apply_action ni el rep.
    s2["history"].append({"diagnostic": REAL_CODE})
    t2 = tutor.apply_action(s2, action)
    sig2 = transition_signature(s2)

    check(f"B {action}: mateix codi de transició", t1 == t2,
          f"{t1!r} != {t2!r}")
    check(f"B {action}: mateix estat resultant", sig1 == sig2,
          f"{sig1!r} != {sig2!r}")


# -----------------------------------------------------------------------------
print("\n[C] Mode de reserva inclou el camp diagnostic")

# Sense clau (ja l'hem tret) → fallback de debò.
llm.ia_disponible = _orig_disp
r = llm.tutor_turn(CAP1, {"capitol": 1, "pas": 1},
                   list(BASIC_TRANSCRIPT), cap_total=4)
check("C fallback retorna clau 'diagnostic'", "diagnostic" in r)
check("C fallback mode == py", r.get("mode") == "py")
# Resposta clarament dolenta → stay → diagnòstic probable del pas (no None).
check("C fallback stay porta el codi probable del pas",
      r["action"] == "stay"
      and r["diagnostic"] == P.likely_diagnostic_for_step(CAP1["passos"][0]),
      f"action={r['action']} diagnostic={r['diagnostic']!r}")

# Avenç en fallback → diagnostic None.
good_transcript = [
    {"role": "tutor", "content": "Quant fa 12 ÷ 3?"},
    {"role": "student", "content": "fa 4, és exacta"},
]
r2 = llm.tutor_turn(CAP1, {"capitol": 1, "pas": 1}, good_transcript,
                    cap_total=4)
check("C fallback advance → diagnostic None",
      r2["action"] == "advance" and r2["diagnostic"] is None,
      f"action={r2['action']} diagnostic={r2['diagnostic']!r}")


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
import sys
sys.exit(0 if FAILED == 0 else 1)
