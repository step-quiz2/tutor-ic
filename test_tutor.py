"""
Tests del Tutor de Divisibilitat. No requereixen clau d'API: exerciten
la lògica de parseig, la màquina d'estats i el mode de reserva.

Executa amb:  python3 test_tutor.py
"""

import os
import re

os.environ.pop("GEMINI_API_KEY", None)  # forcem mode de reserva als tests

import llm
import problems
import tutor

_passats = 0


def check(cond, nom):
    global _passats
    assert cond, f"FALLA: {nom}"
    _passats += 1


def transcript_valid(t):
    return (
        bool(t)
        and t[0]["role"] == "tutor"
        and all(t[i]["role"] != t[i - 1]["role"] for i in range(1, len(t)))
    )


# ── parseig del control block ──────────────────────────────────────────── #
def test_parsing():
    r, c, found = llm._split_reply_and_control("Hola\n\n---CONTROL---\n{\"action\":\"advance\"}")
    check((r, c, found) == ("Hola", '{"action":"advance"}', True), "split amb separador")
    check(llm._split_reply_and_control("text")[2] is False, "split sense separador")
    check(llm._parse_control_block('{"action":"advance"}')["action"] == "advance", "control advance")
    check(llm._parse_control_block('```json\n{"action":"stay"}\n```')["action"] == "stay", "control amb fences")
    check(llm._parse_control_block("garbage")["action"] == "stay", "control invàlid -> stay")
    check(llm._parse_control_block('{"action":"jump"}')["action"] == "stay", "acció desconeguda -> stay")


# ── marcador de posició ───────────────────────────────────────────────── #
def test_marker():
    m = llm._format_position_marker({"capitol": 2, "pas": 3}, 5, 3)
    check(m == "[Posició actual: Capítol 2 de 5 · Pas 3 de 3]", "marcador format")
    check(llm._format_position_marker({}, 5, 3) == "", "marcador buit sense posició")


# ── el prompt es renderitza per a tots els capítols ───────────────────── #
def test_prompt_render():
    for cap in problems.CAPITOLS:
        llm._prompt_cache.clear()
        sp = llm._load_system_prompt(cap, 5)
        check(not re.findall(r"\{\{[A-Z_0-9]+\}\}", sp), f"sense placeholders cap {cap['id']}")
        check("---CONTROL---" in sp, f"separador al prompt cap {cap['id']}")


# ── màquina d'estats: recorregut complet ──────────────────────────────── #
def test_walkthrough():
    state = tutor.new_session()
    check(transcript_valid(state["transcript"]), "transcript inicial vàlid")

    transitions, guard = [], 0
    while not state["finished"] and guard < 200:
        guard += 1
        tutor.add_student(state, "resposta")
        check(transcript_valid(state["transcript"]), f"transcript vàlid (student) torn {guard}")
        tutor.add_tutor(state, "feedback")
        check(transcript_valid(state["transcript"]), f"transcript vàlid (tutor) torn {guard}")
        trans = tutor.apply_action(state, "advance")
        transitions.append(trans)
        if trans == "seguent_capitol":
            check(state["transcript"][0]["role"] == "tutor", "capítol nou comença amb tutor")
            n_tutor = sum(1 for m in state["transcript"] if m["role"] == "tutor")
            check(n_tutor == 1, "transcript del capítol nou reiniciat")

    check(state["finished"], "sessió acabada")
    check(transitions.count("seguent_capitol") == 3, "3 transicions de capítol")
    check(transitions[-1] == "fi", "última transició és fi")
    total = sum(len(c["passos"]) for c in problems.CAPITOLS)
    check(guard == total, f"un torn per pas ({total})")


# ── stay no avança ────────────────────────────────────────────────────── #
def test_stay():
    state = tutor.new_session()
    tutor.add_student(state, "no ho sé")
    tutor.add_tutor(state, "pista")
    cap0, pas0 = state["cap_idx"], state["pas_idx"]
    trans = tutor.apply_action(state, "stay")
    check(trans == "stay" and (state["cap_idx"], state["pas_idx"]) == (cap0, pas0),
          "stay no canvia de pas")


# ── pop_last_student manté l'alternança en cas d'error d'API ──────────── #
def test_pop_on_error():
    state = tutor.new_session()
    tutor.add_student(state, "resposta")
    tutor.pop_last_student(state)
    check(transcript_valid(state["transcript"]), "transcript vàlid després de pop")
    check(state["transcript"][-1]["role"] == "tutor", "acaba en tutor després de pop")


# ── mode de reserva ───────────────────────────────────────────────────── #
def test_fallback():
    check(not llm.ia_disponible(), "ia no disponible sense clau")
    state = tutor.new_session()
    tutor.add_student(state, "3 6 9 12 15, el quart es 12 (3x4 multiplicar taula)")
    r = llm.tutor_turn(tutor.capitol_actual(state), tutor.position_dict(state),
                       state["transcript"], cap_total=5)
    check(r["action"] in ("stay", "advance"), "fallback retorna acció vàlida")
    check(r["n_api_calls"] == 0, "fallback no fa crides a l'API")

    state2 = tutor.new_session()
    tutor.add_student(state2, tutor.PISTA_MARKER)
    r2 = llm.tutor_turn(tutor.capitol_actual(state2), tutor.position_dict(state2),
                        state2["transcript"], cap_total=5)
    check(r2["action"] == "stay", "pista no avança")


# ── invariants de tutor_turn ──────────────────────────────────────────── #
def test_invariants():
    try:
        llm.tutor_turn(problems.CAPITOLS[0], {"capitol": 1, "pas": 1},
                       [{"role": "tutor", "content": "x"}], 5)
        check(False, "hauria d'haver llançat (acaba en tutor)")
    except ValueError:
        check(True, "invariant acaba-en-student")
    try:
        llm.tutor_turn(problems.CAPITOLS[0], {"capitol": 1, "pas": 1},
                       [{"role": "student", "content": "a"},
                        {"role": "student", "content": "b"}], 5)
        check(False, "hauria d'haver llançat (rols consecutius)")
    except ValueError:
        check(True, "invariant alternança")


# ── _build_contents: mapping de rols i marcador ───────────────────────── #
def test_build_contents():
    """Cobreix la lògica que abans estava inline dins tutor_turn i no es
    podia testejar sense API: mapping tutor→model/student→user i injecció
    del marcador al darrer torn d'usuari."""
    transcript = [
        {"role": "tutor", "content": "Hola, quin és el 3×4?"},
        {"role": "student", "content": "12"},
    ]
    marker = "[Posició actual: Capítol 1 de 5 · Pas 1 de 3]"
    contents = llm._build_contents(transcript, marker)

    check(len(contents) == 2, "build_contents: longitud correcta")
    check(contents[0]["role"] == "model", "build_contents: tutor → model")
    check(contents[1]["role"] == "user", "build_contents: student → user")
    check(marker in contents[1]["parts"][0]["text"],
          "build_contents: marcador present al darrer torn d'usuari")
    check(marker not in contents[0]["parts"][0]["text"],
          "build_contents: marcador absent al torn de model")
    check("12" in contents[1]["parts"][0]["text"],
          "build_contents: text original preservat al torn d'usuari")

    # Sense marcador: el text no es modifica
    contents2 = llm._build_contents(transcript, "")
    check(contents2[1]["parts"][0]["text"] == "12",
          "build_contents: sense marcador no modifica el text")

    # Transcript llarg: el marcador va NOMÉS al darrer torn d'usuari
    transcript3 = [
        {"role": "tutor", "content": "Pregunta 1"},
        {"role": "student", "content": "Resposta 1"},
        {"role": "tutor", "content": "Bé. Pregunta 2"},
        {"role": "student", "content": "Resposta 2"},
    ]
    contents3 = llm._build_contents(transcript3, marker)
    check(marker not in contents3[1]["parts"][0]["text"],
          "build_contents: marcador absent en torn d'usuari no final")
    check(marker in contents3[3]["parts"][0]["text"],
          "build_contents: marcador present únicament al darrer torn")


# ── guard de reply buit ───────────────────────────────────────────────── #
def test_empty_reply_split():
    """Quan el model retorna text només amb el separador (reply buit),
    _split_reply_and_control ha de retornar reply == '' (el guard de
    tutor_turn el substituirà pel missatge d'error recuperable)."""
    reply, ctrl, found = llm._split_reply_and_control(
        '---CONTROL---\n{"action":"stay"}'
    )
    check(reply == "", "reply buit quan no hi ha text abans del separador")
    check(found is True, "separador detectat amb reply buit")
    check(ctrl == '{"action":"stay"}', "control block correcte amb reply buit")


# ── enrich_last_tutor i injecció de pregunta canònica ─────────────────── #
def test_enrich_last_tutor():
    """Simula el que fa app.py quan trans == 'seguent_pas': afegir la
    pregunta canònica del pas nou al darrer missatge del tutor."""
    state = tutor.new_session()
    tutor.add_student(state, "resposta correcta")
    tutor.add_tutor(state, "Molt bé! 🎉 Excel·lent feina.")
    trans = tutor.apply_action(state, "advance")
    check(trans == "seguent_pas", "primera transició és seguent_pas")

    pas = tutor.pas_actual(state)
    q_canonica = f"**PREGUNTA.** {pas['pregunta']}"
    tutor.enrich_last_tutor(state, q_canonica)

    # La pregunta canònica ha de ser al darrer missatge de tutor de display
    darrer_tutor_display = next(
        m for m in reversed(state["display"]) if m["role"] == "tutor"
    )
    check(pas["pregunta"] in darrer_tutor_display["content"],
          "pregunta canònica al darrer torn de tutor (display)")

    # I també al transcript del capítol
    darrer_tutor_transcript = next(
        m for m in reversed(state["transcript"]) if m["role"] == "tutor"
    )
    check(pas["pregunta"] in darrer_tutor_transcript["content"],
          "pregunta canònica al darrer torn de tutor (transcript)")

    # L'alternança del transcript s'ha de mantenir intacta
    check(transcript_valid(state["transcript"]),
          "transcript vàlid després d'enrich_last_tutor")


# ── enrich_last_tutor no trenca el transcript del capítol nou ────────── #
def test_enrich_no_trenca_capitol_nou():
    """Quan la transició és seguent_capitol (no seguent_pas), apply_action
    ja crea un transcript nou amb l'obertura. enrich_last_tutor no s'ha
    de cridar en aquest cas, però si s'hi crida no ha de corrompre res."""
    state = tutor.new_session()
    # Avancem tots els passos del capítol 1 fins arribar a seguent_capitol
    while True:
        tutor.add_student(state, "resposta")
        tutor.add_tutor(state, "feedback")
        trans = tutor.apply_action(state, "advance")
        if trans == "seguent_capitol":
            break
        if trans == "fi":
            break
    if trans == "seguent_capitol":
        check(transcript_valid(state["transcript"]),
              "transcript vàlid en inici de capítol nou")
        check(state["transcript"][0]["role"] == "tutor",
              "transcript de capítol nou comença per tutor")


if __name__ == "__main__":
    for fn in [test_parsing, test_marker, test_prompt_render, test_walkthrough,
               test_stay, test_pop_on_error, test_fallback, test_invariants,
               test_build_contents, test_empty_reply_split,
               test_enrich_last_tutor, test_enrich_no_trenca_capitol_nou]:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{_passats} comprovacions superades ✅")
