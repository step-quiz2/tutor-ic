"""
Eval runner per al tutor-ic.

Executa tots els casos de `eval_cases.py` contra el classificador real
`llm.judge_step` i compara amb les prediccions a priori. Reporta:

- Línia per cas (pass / fail + detall si falla)
- Taxa global d'acord
- Acord estratificat per veredicte esperat i per pas
- Matriu de confusió (esperat × obtingut)
- Anàlisi de falsos positius i falsos negatius
- JSON detallat amb totes les respostes per a anàlisi posterior

Ús bàsic:
    export GEMINI_API_KEY=...
    python eval_runner.py

Opcions:
    --filter PREFIX       Només casos amb id que comenci per PREFIX
                          (p.ex. S1 per a Pas 1, S2-TYP per a errors de Pas 2)
    --repeat N            Repeteix cada cas N vegades (mesura variància)
                          Default: 1
    --output FILE         Fitxer JSON de sortida.
                          Default: eval_results_{timestamp}.json
    --check-labels        També verifica `expected_error_label` quan està
                          declarada (default: només verdict)

El JSON de sortida inclou per a cada cas: input, veredicte esperat,
totes les repeticions amb (veredicte obtingut, raó IA, etiqueta, temps).
Útil per a auditar manualment les discrepàncies o per generar gràfiques
amb pandas posteriorment.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime

import problem as PB
import llm as L
from eval_cases import CASES


VERDICT_TYPES = ("correct", "typical_error", "conceptual_gap")


def get_step(step_id):
    for s in PB.PROBLEM["passos"]:
        if s["id"] == step_id:
            return s
    raise ValueError(f"Pas {step_id} no existeix a problem.py")


def run_one(case, check_labels=False):
    """Executa una crida i compara amb les expectatives. Retorna un dict."""
    step = get_step(case["step_id"])
    t0 = time.time()
    try:
        result = L.judge_step(step, case["input"])
        elapsed = time.time() - t0
        verdict = result["verdict"]
        label = result.get("error_label")
        reason = result.get("reason", "")

        verdict_match = verdict == case["expected_verdict"]
        label_match = True
        if check_labels and case.get("expected_error_label") is not None:
            label_match = (label == case["expected_error_label"])

        return {
            "ok": True,
            "verdict": verdict,
            "error_label": label,
            "reason": reason,
            "elapsed_s": round(elapsed, 2),
            "verdict_match": verdict_match,
            "label_match": label_match,
            "pass": verdict_match and label_match,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "elapsed_s": round(time.time() - t0, 2),
            "pass": False,
        }


def run_case(case, n_repeats, check_labels):
    """Executa el cas n_repeats vegades."""
    return [run_one(case, check_labels) for _ in range(n_repeats)]


def print_case_line(idx, total, case, runs):
    """Una línia per cas a consola."""
    all_pass = all(r.get("pass", False) for r in runs)
    n_pass = sum(1 for r in runs if r.get("pass", False))
    n = len(runs)

    if n == 1:
        marker = "✓" if all_pass else "✗"
        rate = ""
    else:
        marker = "✓" if all_pass else ("△" if n_pass > 0 else "✗")
        rate = f" [{n_pass}/{n}]"

    print(f"[{idx:2d}/{total}] {case['id']:14s} ({case['expected_verdict']:14s}) {marker}{rate}")

    if not all_pass:
        # Detall de les fallades
        for j, r in enumerate(runs):
            if r.get("pass"):
                continue
            if not r.get("ok"):
                print(f"            └─ rep {j+1}: ERROR — {r.get('error', '?')}")
            else:
                got = f"{r['verdict']}/{r['error_label']}"
                exp = f"{case['expected_verdict']}/{case.get('expected_error_label')}"
                print(f"            └─ rep {j+1}: esperava {exp}, obtingut {got}")
                if r.get("reason"):
                    reason_truncated = r["reason"][:120]
                    print(f"               raó IA: «{reason_truncated}»")


def build_confusion_matrix(all_results):
    """{esperat: {obtingut: count}}"""
    matrix = defaultdict(lambda: defaultdict(int))
    for r in all_results:
        exp = r["case"]["expected_verdict"]
        for run in r["runs"]:
            if run.get("ok"):
                matrix[exp][run["verdict"]] += 1
            else:
                matrix[exp]["__error__"] += 1
    return {k: dict(v) for k, v in matrix.items()}


def print_confusion_matrix(matrix):
    """Imprimeix la matriu esperat × obtingut."""
    print("\nMatriu de confusió (files = esperat, columnes = obtingut):")
    print(f"  {'':18s} " + " ".join(f"{v:>15s}" for v in VERDICT_TYPES))
    for exp in VERDICT_TYPES:
        row = matrix.get(exp, {})
        cells = " ".join(f"{row.get(v, 0):>15d}" for v in VERDICT_TYPES)
        total = sum(row.values())
        print(f"  {exp:18s} {cells}  (total: {total})")


def summarize(all_results, check_labels):
    total_cases = len(all_results)
    total_runs = sum(len(r["runs"]) for r in all_results)

    # Cas: passa només si TOTES les seves repeticions passen
    cases_passed = sum(1 for r in all_results if all(run.get("pass", False) for run in r["runs"]))

    # Runs individuals
    runs_passed = sum(1 for r in all_results for run in r["runs"] if run.get("pass", False))

    # Estratificat per veredicte esperat
    by_exp = defaultdict(lambda: {"runs_total": 0, "runs_pass": 0})
    for r in all_results:
        exp = r["case"]["expected_verdict"]
        for run in r["runs"]:
            by_exp[exp]["runs_total"] += 1
            if run.get("pass"):
                by_exp[exp]["runs_pass"] += 1

    # Estratificat per pas
    by_step = defaultdict(lambda: {"runs_total": 0, "runs_pass": 0})
    for r in all_results:
        step = r["case"]["step_id"]
        for run in r["runs"]:
            by_step[step]["runs_total"] += 1
            if run.get("pass"):
                by_step[step]["runs_pass"] += 1

    # Errors crítics (segons criteris pedagògics)
    #   FALS POSITIU: el sistema diu "correct" quan en realitat l'esperat
    #   era typical_error o conceptual_gap. És l'error PEDAGÒGICAMENT
    #   INACCEPTABLE: l'alumne avança amb un error no detectat.
    #
    #   FALS NEGATIU: el sistema diu "typical_error" o "conceptual_gap"
    #   quan l'esperat era "correct". Pedagògicament és menys greu —
    #   bloqueja l'alumne però existeix el mecanisme `!text` per resoldre.
    false_positives = []
    false_negatives = []
    for r in all_results:
        exp = r["case"]["expected_verdict"]
        for run in r["runs"]:
            if not run.get("ok"):
                continue
            got = run["verdict"]
            if exp in ("typical_error", "conceptual_gap") and got == "correct":
                false_positives.append((r["case"]["id"], exp, got))
            elif exp == "correct" and got in ("typical_error", "conceptual_gap"):
                false_negatives.append((r["case"]["id"], exp, got))

    print("\n" + "=" * 70)
    print("RESUM")
    print("=" * 70)
    print(f"Casos:       {cases_passed}/{total_cases} ({100*cases_passed/total_cases:.1f}%)")
    print(f"Crides:      {runs_passed}/{total_runs} ({100*runs_passed/total_runs:.1f}%)")
    print(f"Mode:        {'verdict + label' if check_labels else 'només verdict'}")

    print("\nPer veredicte esperat (crides individuals):")
    for v in VERDICT_TYPES:
        s = by_exp.get(v, {"runs_total": 0, "runs_pass": 0})
        if s["runs_total"] == 0:
            continue
        pct = 100 * s["runs_pass"] / s["runs_total"]
        print(f"  {v:18s}: {s['runs_pass']:3d}/{s['runs_total']:3d}  ({pct:5.1f}%)")

    print("\nPer pas (crides individuals):")
    for step in sorted(by_step.keys()):
        s = by_step[step]
        pct = 100 * s["runs_pass"] / s["runs_total"]
        print(f"  Pas {step}             : {s['runs_pass']:3d}/{s['runs_total']:3d}  ({pct:5.1f}%)")

    print(f"\nFalsos positius (PEDAGÒGICAMENT GREUS): {len(false_positives)}")
    for case_id, exp, got in false_positives:
        print(f"  ⚠ {case_id}: esperava {exp}, va dir {got}")
    print(f"\nFalsos negatius (menys greus, recuperables amb !text): {len(false_negatives)}")
    for case_id, exp, got in false_negatives:
        print(f"  · {case_id}: esperava {exp}, va dir {got}")

    print_confusion_matrix(build_confusion_matrix(all_results))


def main():
    parser = argparse.ArgumentParser(
        description="Eval runner per al tutor-ic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--filter", default=None,
                        help="Només casos amb id que comenci per aquest prefix")
    parser.add_argument("--repeat", type=int, default=1,
                        help="Repeticions per cas (default: 1)")
    parser.add_argument("--output", default=None,
                        help="Fitxer JSON de sortida (default: eval_results_<timestamp>.json)")
    parser.add_argument("--check-labels", action="store_true",
                        help="També verifica error_label quan està declarada")
    args = parser.parse_args()

    cases = CASES
    if args.filter:
        cases = [c for c in cases if c["id"].startswith(args.filter)]
        if not cases:
            print(f"Cap cas coincideix amb el filtre '{args.filter}'", file=sys.stderr)
            sys.exit(1)

    total = len(cases)
    n_runs = total * args.repeat
    print(f"Executant {total} casos × {args.repeat} repeticions = {n_runs} crides a la IA")
    print(f"Model: {L.MODEL}")
    print(f"Mode: {'verdict + label' if args.check_labels else 'només verdict'}")
    print()

    t_start = time.time()
    all_results = []
    for i, case in enumerate(cases, start=1):
        runs = run_case(case, args.repeat, args.check_labels)
        all_results.append({"case": case, "runs": runs})
        print_case_line(i, total, case, runs)

    elapsed = time.time() - t_start
    print(f"\nTemps total: {elapsed:.1f}s")

    summarize(all_results, args.check_labels)

    # Desem JSON detallat
    output = args.output
    if output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"eval_results_{ts}.json"

    summary_payload = {
        "model": L.MODEL,
        "n_cases": total,
        "n_repeats": args.repeat,
        "check_labels": args.check_labels,
        "elapsed_s": round(elapsed, 1),
        "ran_at": datetime.now().isoformat(),
        "results": all_results,
    }
    with open(output, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, ensure_ascii=False, indent=2)
    print(f"\nResultats detallats desats a: {output}")


if __name__ == "__main__":
    main()
