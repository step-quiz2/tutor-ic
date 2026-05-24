"""
llm.py — interfície Gemini per al tutor d'IC (arquitectura Nivell 1).

Aquest mòdul exposa una sola funció pública:

    tutor_turn(problem, current_position, transcript) -> dict

que fa UNA crida a Gemini per cada torn de conversa amb l'alumne i
retorna la resposta del tutor més una decisió d'acció de control
(stay / advance / retreat_to_prereq).

Aquest fitxer substitueix l'arquitectura anterior basada en tres
classificadors apàtrides (`judge_step`, `judge_prereq`, `generate_*_hint`),
que vivia a `llm.py` abans del Pas 2 d'aquest redisseny. La versió
antiga queda arxivada a `archive/pre-conversational/llm.py`.

Variables d'entorn:
  GEMINI_API_KEY  — obligatòria
  GEMINI_MODEL    — opcional, default "gemini-2.5-flash"
"""

import json
import os
import re
import time
from pathlib import Path

from google import genai
from google.genai import types as genai_types

import problem as PB


# -----------------------------------------------------------------------------
# Configuració
# -----------------------------------------------------------------------------

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_VERSION = "v1.2"

# Reintents per a errors transitoris de l'API.
MAX_ATTEMPTS = 3
RETRY_PATTERNS = ("503", "UNAVAILABLE", "RESOURCE_EXHAUSTED",
                  "DEADLINE_EXCEEDED")

# Tokens màxims a la resposta del model. La resposta típica del tutor
# té 100-300 tokens (text per a l'alumne) + ~30 tokens (control block).
# 800 dóna marge per casos llargs (explicació canònica del reforç,
# missatge final de tancament, transició entre passos amb metàfora).
MAX_OUTPUT_TOKENS = 800

# Temperatura: la conversa pedagògica necessita una mica de
# variabilitat per no sonar robotitzada. 0.4 és el mateix valor que
# feia servir el `generate_hint` de l'arquitectura anterior on
# funcionava bé per a textos naturals breus.
TEMPERATURE = 0.4

# Separador del control block. ÉS LITERAL: ha de coincidir amb el que
# el system prompt v1 demana al model.
CONTROL_SEPARATOR = "---CONTROL---"

# Accions reconegudes pel sistema. Qualsevol altre valor (inclòs cap)
# es coerceix a "stay" — defensa contra al·lucinacions o respostes
# incompletes del model.
VALID_ACTIONS = ("stay", "advance", "retreat_to_prereq")


# -----------------------------------------------------------------------------
# Client Gemini — lazy, una sola vegada per procés
# -----------------------------------------------------------------------------

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY no està definida a l'entorn. Configura-la "
                "abans d'iniciar l'aplicació."
            )
        _client = genai.Client(api_key=api_key)
    return _client


# -----------------------------------------------------------------------------
# Carrega i parametrització del system prompt
# -----------------------------------------------------------------------------

_system_prompt_cache = None


def _load_system_prompt() -> str:
    """Carrega el system prompt per al problema actual des de
    `prompts/tutor_system_<version>.md` i substitueix els placeholders
    `{{...}}` amb dades de `problem.py`.

    El resultat es cacheja a nivell de mòdul perquè el prompt és estable
    durant tota una execució del procés (les dades del problema no
    canvien en runtime). Si en el futur volem suport multi-problema,
    aquesta cache haurà de ser per problem.id.
    """
    global _system_prompt_cache
    if _system_prompt_cache is not None:
        return _system_prompt_cache

    template_path = PROMPTS_DIR / f"tutor_system_{PROMPT_VERSION}.md"
    template = template_path.read_text(encoding="utf-8")

    p = PB.PROBLEM
    passos = p["passos"]
    if len(passos) != 3:
        raise RuntimeError(
            f"El system prompt v1 espera exactament 3 passos al "
            f"problema, però n'hi ha {len(passos)}. Cal regenerar el "
            f"prompt o adaptar `_load_system_prompt`."
        )

    # Substitució literal. Sintaxi {{PLACEHOLDER}} triada per no entrar
    # en conflicte amb els fragments JSON literals que conté el prompt
    # (per exemple `{"action": "stay"}` als exemples de format).
    replacements = {
        "{{PROBLEM_ENUNCIAT}}":    p["enunciat"],
        "{{STEP1_TEXT}}":          passos[0]["text"],
        "{{STEP1_EXPECTED}}":      passos[0]["expected_summary"],
        "{{STEP1_TYPICAL_ERROR}}": passos[0]["typical_error"],
        "{{STEP2_TEXT}}":          passos[1]["text"],
        "{{STEP2_EXPECTED}}":      passos[1]["expected_summary"],
        "{{STEP2_TYPICAL_ERROR}}": passos[1]["typical_error"],
        "{{STEP3_TEXT}}":          passos[2]["text"],
        "{{STEP3_EXPECTED}}":      passos[2]["expected_summary"],
        "{{STEP3_TYPICAL_ERROR}}": passos[2]["typical_error"],
    }

    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)

    # Verificació defensiva: cap placeholder ha quedat sense substituir.
    unresolved = re.findall(r"\{\{[A-Z_0-9]+\}\}", template)
    if unresolved:
        raise RuntimeError(
            f"Placeholders no resolts al system prompt: {unresolved}. "
            f"Cal afegir-los a la taula de substitucions."
        )

    _system_prompt_cache = template
    return template


# -----------------------------------------------------------------------------
# Crida única al model amb multi-turn contents
# -----------------------------------------------------------------------------

def _is_retriable(err: Exception) -> bool:
    msg = str(err).upper()
    return any(p in msg for p in RETRY_PATTERNS)


def _format_position_marker(current_position: dict) -> str:
    """Construeix la línia de marcador de posició que s'antepondrà al
    darrer missatge user. El system prompt v1.2 documenta aquest
    format i instrueix el model a respectar-lo com a font de veritat
    sobre on és la sessió.

    Format v1.2 (més directiu que v1.1 — afegit després de constatar
    que el marcador "Posició actual: Pas N de 3" sense més no
    impedia que el model interpretés el marker com "el pas al qual
    vas" en comptes de "el pas en discussió"):

      [Pas N de TOTAL. L'alumne respon a la teva pregunta del Pas N.
       Jutja: tanca (advance) o continua (stay).]              — pas normal

      [Reforç PRE-PARAM activat (tornarà al Pas N). L'alumne respon
       a la pregunta del reforç. Jutja: tanca (advance) o continua
       (stay).]                                                 — en reforç

    Si no podem determinar la posició (current_position buit o sense
    camps reconeixibles), retornem cadena buida — el model continua
    sense marcador, igual que en v1.
    """
    if not current_position:
        return ""

    prereq = current_position.get("prereq")
    step = current_position.get("step")

    if prereq:
        if step is not None:
            return (f"[Reforç {prereq} activat (tornarà al Pas {step}). "
                    f"L'alumne respon a la pregunta del reforç. "
                    f"Jutja: tanca (advance) o continua (stay).]")
        return (f"[Reforç {prereq} activat. "
                f"L'alumne respon a la pregunta del reforç. "
                f"Jutja: tanca (advance) o continua (stay).]")

    if step is not None:
        total = len(PB.PROBLEM["passos"])
        return (f"[Pas {step} de {total}. "
                f"L'alumne respon a la teva pregunta del Pas {step}. "
                f"Jutja: tanca (advance) o continua (stay).]")

    return ""


def _call(system_instruction: str, contents: list) -> str:
    """Crida única a Gemini amb un multi-turn `contents`. Retorna el
    text brut de la resposta.

    Implementa reintents amb backoff exponencial per a errors
    transitoris de l'API. Els errors no transitoris es propaguen
    immediatament a l'invocador.
    """
    client = _get_client()
    last_err = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=MAX_OUTPUT_TOKENS,
                    temperature=TEMPERATURE,
                ),
            )
            return response.text or ""
        except Exception as e:
            last_err = e
            if not _is_retriable(e) or attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(0.5 * (2 ** attempt))  # 0.5s, 1s, 2s
    if last_err:
        raise last_err
    raise RuntimeError("Crida a Gemini fallida sense raó coneguda")


# -----------------------------------------------------------------------------
# Helpers de parseig de la resposta
# -----------------------------------------------------------------------------

def _split_reply_and_control(raw_output: str):
    """Separa el text natural del control block.

    Retorna `(reply, control_text, separator_found)`:
      - reply: text per a l'alumne (str, sense el control).
      - control_text: text del control block, o None si no s'ha trobat.
      - separator_found: True si el separador era al raw_output.
    """
    if CONTROL_SEPARATOR not in raw_output:
        return (raw_output.strip(), None, False)
    parts = raw_output.split(CONTROL_SEPARATOR, 1)
    reply = parts[0].strip()
    control_text = parts[1].strip()
    return (reply, control_text, True)


def _parse_control_block(text: str) -> dict:
    """Parseja el JSON del control block. Retorna sempre un dict amb
    `action` i `objectives_met` ben formats, recorrent a "stay" per
    defecte si el JSON falla o té camps inesperats. El camp
    `_parse_error` indica si hi va haver fallback.
    """
    text = text.strip()
    # Tolerar fences ```json ... ``` per si el model les afegeix.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("JSON top-level no és object")
    except (json.JSONDecodeError, ValueError):
        return {
            "action": "stay",
            "objectives_met": [],
            "_parse_error": True,
        }

    action = data.get("action", "stay")
    if action not in VALID_ACTIONS:
        action = "stay"

    objectives = data.get("objectives_met", [])
    if not isinstance(objectives, list):
        objectives = []

    return {
        "action": action,
        "objectives_met": objectives,
        "_parse_error": False,
    }


# -----------------------------------------------------------------------------
# Funció pública: tutor_turn
# -----------------------------------------------------------------------------

def tutor_turn(problem: dict, current_position: dict,
               transcript: list) -> dict:
    """
    Una crida al model per al pròxim torn del tutor.

    Args:
        problem: PB.PROBLEM. Es passa explícitament per facilitar tests
            i una eventual extensió multi-problema.
        current_position: {"step": int|None, "prereq": str|None}. En
            aquesta versió no es renderitza explícitament al prompt
            (el model dedueix la posició de la conversa). Es manté com a
            paràmetre per a una eventual extensió futura amb checkpoints
            de posició.
        transcript: llista de torns, format
            [{"role": "tutor"|"student", "content": str}, ...].
            Ha d'acabar en un torn "student".

    Returns:
        {
            "reply": str,              # text per a l'alumne (markdown)
            "action": str,             # "stay" | "advance" | "retreat_to_prereq"
            "objectives_met": list,    # objectius assolits ([] per defecte)
            "n_api_calls": int,        # sempre 1 en aquesta versió
            "raw_output": str,         # text brut del model per al rastre
            "control_parse_ok": bool,  # False si el control va caure a default
        }

    Raises:
        ValueError: si el transcript està buit o no acaba en torn 'student'.
        RuntimeError: si GEMINI_API_KEY no està configurada.
        Exception (google.api_core.*): si l'API falla persistentment.
        L'invocador (app.py) ha de capturar excepcions de l'API i
        tractar-les com a incident tècnic — NO com a error de l'alumne.
    """
    # Invariants del transcript.
    if not transcript:
        raise ValueError(
            "tutor_turn requereix un transcript no buit. "
            "L'opening del tutor el genera l'aplicació (app.py), no el model."
        )
    if transcript[-1]["role"] != "student":
        raise ValueError(
            f"tutor_turn espera que el transcript acabi en torn 'student', "
            f"però acaba en '{transcript[-1]['role']}'."
        )

    system_instruction = _load_system_prompt()

    # Construïm el multi-turn contents: cada torn del transcript és un
    # missatge propi. Els torns "tutor" són role="model" (passem només
    # el contingut net, sense control block — el control és metadades
    # del sistema, no part de la conversa que el model va veure). Els
    # torns "student" són role="user".
    #
    # A v1.1 (Proposta de Pas 3a-bis), prependim un marcador de posició
    # al DARRER missatge user. El marcador li diu al model en quin pas
    # estem ara mateix i actua com a font de veritat — sense això, el
    # model perd la pista de l'estructura del currículum a mesura que
    # la conversa avança (bug observat a les sessions Alumne 1, 2 amb
    # el prompt v1).
    position_marker = _format_position_marker(current_position)
    last_user_idx = len(transcript) - 1  # garantit > 0 per invariants

    contents = []
    for i, turn in enumerate(transcript):
        role = "model" if turn["role"] == "tutor" else "user"
        text = turn["content"]
        if i == last_user_idx and role == "user" and position_marker:
            text = f"{position_marker}\n\n{text}"
        contents.append({
            "role": role,
            "parts": [{"text": text}],
        })

    raw_output = _call(system_instruction, contents)

    reply, control_text, sep_found = _split_reply_and_control(raw_output)

    if sep_found and control_text:
        control = _parse_control_block(control_text)
        parse_ok = not control.get("_parse_error", False)
    else:
        control = {"action": "stay", "objectives_met": []}
        parse_ok = False

    return {
        "reply": reply,
        "action": control["action"],
        "objectives_met": control["objectives_met"],
        "n_api_calls": 1,
        "raw_output": raw_output,
        "control_parse_ok": parse_ok,
    }
