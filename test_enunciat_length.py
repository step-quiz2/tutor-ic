"""
test_enunciat_length.py — guarda-raïls de longitud dels enunciats.

Motivació (suggeriment de millora #1): les preguntes que Python injecta com
a bombolla pròpia s'havien de retallar a mà cada cop que en sortia una de
massa llarga (vegeu la idea 8 del cicle de millores: el pas 1 d'IC-001 tenia
un paràgraf de 5 línies que molts alumnes no llegien). Aquest test fa que el
límit el faci complir la suite, no l'ull de qui revisa: si algú torna a
allargar un enunciat, el test falla abans de la demo.

Què es comprova i què no:
  - `canonical_question` és la pregunta destil·lada que VEU l'alumne quan
    Python obre un pas. HA de ser curta. → Sí que es limita.
  - `text` pot contenir context llarg (dades, fonts); l'app el PAGINA en
    subpantalles, així que la seva llargada
    no és un problema d'UX directe. → NO es limita aquí (només es comprova
    que existeix i no és buit).

Llindars (deliberadament generosos sobre el màxim real actual, ~297 car):
"""

import problem


# La pregunta que veu l'alumne no hauria de passar d'aquí. 300 car ≈ 4-5
# frases curtes; per sobre, l'alumne deixa de llegir-la (esp. en mòbil).
MAX_CANONICAL_CHARS = 300
MAX_CANONICAL_LINES = 4


def _iter_passos():
    """Genera (problem_id, pas) per a tots els passos de tots els problemes."""
    for pid, _human in problem.list_ids():
        bundle = problem.get(pid)
        for pas in bundle["problem"]["passos"]:
            yield pid, pas


def test_canonical_question_present():
    """Tot pas ha de tenir una canonical_question no buida."""
    fails = []
    for pid, pas in _iter_passos():
        cq = pas.get("canonical_question", "")
        if not isinstance(cq, str) or not cq.strip():
            fails.append(f"{pid} pas {pas.get('id')}: canonical_question buida")
    assert not fails, "Enunciats sense pregunta canònica:\n" + "\n".join(fails)


def test_canonical_question_not_too_long():
    """La pregunta visible no supera els llindars de car/línies."""
    fails = []
    for pid, pas in _iter_passos():
        cq = pas.get("canonical_question", "") or ""
        n_chars = len(cq)
        n_lines = cq.count("\n") + 1
        if n_chars > MAX_CANONICAL_CHARS:
            fails.append(
                f"{pid} pas {pas.get('id')}: {n_chars} car "
                f"(> {MAX_CANONICAL_CHARS})"
            )
        if n_lines > MAX_CANONICAL_LINES:
            fails.append(
                f"{pid} pas {pas.get('id')}: {n_lines} línies "
                f"(> {MAX_CANONICAL_LINES})"
            )
    assert not fails, (
        "Enunciats massa llargs (retalla'ls o mou el context al `text`, "
        "que es pagina):\n" + "\n".join(fails)
    )


def test_text_present():
    """El `text` del pas existeix i no és buit (pot ser llarg: es pagina)."""
    fails = []
    for pid, pas in _iter_passos():
        t = pas.get("text", "")
        if not isinstance(t, str) or not t.strip():
            fails.append(f"{pid} pas {pas.get('id')}: text buit")
    assert not fails, "Passos sense text:\n" + "\n".join(fails)


# ----------------------------------------------------------------------- #
# Runner mínim sense pytest (coherent amb la resta de suites del projecte)
# ----------------------------------------------------------------------- #
if __name__ == "__main__":
    tests = [
        test_canonical_question_present,
        test_canonical_question_not_too_long,
        test_text_present,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {t.__name__}\n    {e}")
            failed += 1
    print("=" * 60)
    print(f"Tests passats: {passed}")
    print(f"Tests fallits: {failed}")
    print("=" * 60)
    raise SystemExit(1 if failed else 0)
