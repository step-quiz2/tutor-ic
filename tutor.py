"""
tutor.py · Màquina d'estats del Tutor de Divisibilitat (arquitectura v2).

No depèn de Streamlit. El model (llm.tutor_turn) retorna una acció
("stay" o "advance"); aquí mantenim l'estat (capítol, pas, transcript del
capítol, finished) i apliquem les transicions.

Cada CAPÍTOL és una unitat conversacional pròpia: el seu system prompt i
el seu transcript es construeixen per separat. Quan s'avança més enllà de
l'últim pas d'un capítol, Python tanca el capítol i obre el següent (no ho
fa el model).
"""

from __future__ import annotations

import time

import problems

PISTA_MARKER = "(L'alumne demana una pista)"


# ───────────────────────────── sessió ─────────────────────────────────── #

def new_session() -> dict:
    """Estat inicial. El tutor obre amb la presentació del Capítol 1 +
    la primera pregunta (generat per Python, sense crida a l'IA)."""
    cap = problems.CAPITOLS[0]
    obertura = missatge_obertura_capitol(cap)
    return {
        "started_at": time.time(),
        "cap_idx": 0,                 # índex del capítol actual (0-based)
        "pas_idx": 0,                 # índex del pas dins del capítol (0-based)
        "finished": False,
        # transcript del CAPÍTOL actual (es reinicia en canviar de capítol)
        "transcript": [{"role": "tutor", "content": obertura}],
        # historial complet per mostrar a la UI (tots els capítols).
        # source: "py" = mode determinista (Python) · "ai" = mode heurístic (IA)
        "display": [{"role": "tutor", "content": obertura, "source": "py"}],
        "turn_count": 0,
        "history": [],                # rastre per torn (per al professor)
        "last_raw_output": None,
    }


def capitol_actual(state: dict) -> dict:
    return problems.CAPITOLS[state["cap_idx"]]


def pas_actual(state: dict) -> dict:
    return capitol_actual(state)["passos"][state["pas_idx"]]


def position_dict(state: dict) -> dict:
    """Posició 1-based per al marcador que rep llm.tutor_turn."""
    return {"capitol": state["cap_idx"] + 1, "pas": state["pas_idx"] + 1}


def total_capitols() -> int:
    return len(problems.CAPITOLS)


# ───────────────────────── transicions d'estat ───────────────────────── #

def apply_action(state: dict, action: str) -> str:
    """
    Aplica l'acció del control block. Retorna un codi del que ha passat:
        "stay"             → ens quedem al mateix pas
        "seguent_pas"      → avancem a un pas dins del mateix capítol
        "seguent_capitol"  → comencem un capítol nou (Python l'obre)
        "fi"               → s'han completat tots els capítols

    Quan s'inicia un capítol nou, aquesta funció ja afegeix el missatge
    d'obertura tant al transcript (nou) com al display, perquè el següent
    torn del model rebi un transcript que comença pel tutor.
    """
    if action != "advance":
        return "stay"

    cap = capitol_actual(state)
    if state["pas_idx"] + 1 < len(cap["passos"]):
        state["pas_idx"] += 1
        return "seguent_pas"

    # Final del capítol.
    if state["cap_idx"] + 1 < total_capitols():
        state["cap_idx"] += 1
        state["pas_idx"] = 0
        nou_cap = capitol_actual(state)
        obertura = missatge_obertura_capitol(nou_cap)
        # Nou context conversacional per al capítol nou.
        state["transcript"] = [{"role": "tutor", "content": obertura}]
        state["display"].append({"role": "tutor", "content": obertura, "source": "py"})
        return "seguent_capitol"

    state["finished"] = True
    return "fi"


def add_student(state: dict, text: str) -> None:
    state["transcript"].append({"role": "student", "content": text})
    state["display"].append({"role": "student", "content": text, "source": "student"})


def add_tutor(state: dict, text: str, source: str = "ai") -> None:
    """Afegeix un torn del tutor.

    source = "ai" → resposta heurística generada per la IA.
    source = "py" → text determinista generat per Python (obertures,
                    preguntes canòniques, missatge final, mode de reserva).
    """
    state["transcript"].append({"role": "tutor", "content": text})
    state["display"].append({"role": "tutor", "content": text, "source": source})


def enrich_last_tutor(state: dict, extra: str) -> None:
    """Posa la pregunta canònica del pas nou quan el model avança.

    - Al **transcript** del capítol: l'enganxem al darrer torn del tutor,
      perquè el model vegi en el seu context la pregunta que toca respondre
      (i no es trenqui l'alternança tutor/student).
    - Al **display**: la posem com a bombolla pròpia i **determinista** (py),
      perquè quedi clar que l'enunciat el posa Python, no la IA. Així la
      felicitació (heurística) i la pregunta (determinista) es veuen amb
      colors diferents.
    """
    # Transcript: enganxa al darrer tutor (manté l'alternança).
    for m in reversed(state["transcript"]):
        if m["role"] == "tutor":
            m["content"] += f"\n\n{extra}"
            break
    # Display: bombolla determinista separada.
    state["display"].append({"role": "tutor", "content": extra, "source": "py"})


def pop_last_student(state: dict) -> None:
    """Treu l'últim torn d'alumne (s'usa si la crida a l'IA falla, per
    no trencar l'alternança del transcript en el reintent)."""
    if state["transcript"] and state["transcript"][-1]["role"] == "student":
        state["transcript"].pop()
    if state["display"] and state["display"][-1]["role"] == "student":
        state["display"].pop()


# ───────────────────────── generació de textos ────────────────────────── #

def missatge_obertura_capitol(cap: dict) -> str:
    """Presentació curta d'un capítol + primera pregunta (la genera Python)."""
    primer = cap["passos"][0]
    return (
        f"## {cap['emoji']} Capítol {cap['id']} · {cap['titol']}\n\n"
        f"{cap['introduccio']}\n\n"
        f"**PREGUNTA.** {primer['pregunta']}"
    )


MISSATGE_BENVINGUDA = (
    "Hola, Aran! 👋 Sóc en **Pitàgores**.\n\n"
    "Avui aprendrem **múltiples, divisors i primers**.\n\n"
    "Anirem a poc a poc. Si t'equivoques, no passa res!\n\n"
    "Prem **Comença** quan vulguis. 🚀"
)

MISSATGE_FINAL = (
    "🎉 **Molt bé, Aran!** Ho has aconseguit.\n\n"
    "Ja saps què és un **múltiple**, un **divisor** i un **primer**.\n\n"
    "Bona feina! 🌟"
)
