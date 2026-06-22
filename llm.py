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
import unicodedata
from pathlib import Path

try:
    from google import genai
    from google.genai import types as genai_types
    _GENAI_OK = True
except Exception:  # SDK absent (demo sense API, o entorn de test amb stubs)
    genai = None
    genai_types = None
    _GENAI_OK = False

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

# Tokens màxims a la resposta del model. La resposta visible típica
# té 100-300 tokens (text per a l'alumne) + ~30 tokens (control block).
#
# Però Gemini 2.5 Flash inclou els tokens de raonament intern dins
# d'aquest pressupost. Quan el model està confús (per exemple si rep
# un transcript mal alternat) consumeix centenars de tokens pensant
# abans de produir text visible, i la resposta s'acaba truncant a
# meitat de paraula sense arribar al separador `---CONTROL---`. Això
# es manifesta com `control_parse_ok=False` + reply truncada a la
# meitat. 1500 dóna marge generós tant per al pensament com per al
# text final i tanca aquesta classe de fallada.
MAX_OUTPUT_TOKENS = 8000

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


def ia_disponible() -> bool:
    """True si hi ha SDK de Gemini + clau d'API a l'entorn.

    Si retorna False, `tutor_turn` opera en **mode de reserva**: una
    heurística senzilla per paraules clau que permet que el flux complet
    (avançar, pistes, retrocés) sigui demostrable sense IA. Pensat com a
    xarxa de seguretat per a una demo en directe: si l'API cau, l'app no
    peta amb un stack trace, sinó que degrada a un tutor mínim.
    """
    return _GENAI_OK and bool(os.environ.get("GEMINI_API_KEY"))


# -----------------------------------------------------------------------------
# Carrega i parametrització del system prompt
# -----------------------------------------------------------------------------

# Cache del system prompt per problem.id. Es construeix la primera
# vegada que es demana un problema concret i es reutilitza la resta
# del procés. Suport multi-problema: cada problema té el seu fitxer
# de plantilla (tutor_system_<version>_<problem_id>.md) i les seves
# pròpies substitucions de placeholders.
_system_prompt_cache: dict[str, str] = {}


def _load_system_prompt(problem: dict = None) -> str:
    """Carrega el system prompt per al `problem` donat des de
    `prompts/tutor_system_<version>_<problem_id>.md` i substitueix els
    placeholders `{{...}}` amb dades del problema.

    Args:
        problem: bundle d'un problema (com els que conté `PB.PROBLEMS`,
            i.e. el dict que té id/tema/enunciat/passos). Si és None,
            usa `PB.PROBLEM` (el problema per defecte) per back-compat.

    El resultat es cacheja per `problem["id"]`. Un mateix procés pot
    servir múltiples problemes (un per sessió); cada un carrega el seu
    prompt un sol cop.
    """
    if problem is None:
        problem = PB.PROBLEM

    problem_id = problem["id"]
    if problem_id in _system_prompt_cache:
        return _system_prompt_cache[problem_id]

    template_path = PROMPTS_DIR / f"tutor_system_{PROMPT_VERSION}_{problem_id}.md"
    template = template_path.read_text(encoding="utf-8")

    passos = problem["passos"]
    if len(passos) != 3:
        raise RuntimeError(
            f"El system prompt v1 espera exactament 3 passos al "
            f"problema {problem_id}, però n'hi ha {len(passos)}. Cal "
            f"regenerar el prompt o adaptar `_load_system_prompt`."
        )

    # Substitució literal. Sintaxi {{PLACEHOLDER}} triada per no entrar
    # en conflicte amb els fragments JSON literals que conté el prompt
    # (per exemple `{"action": "stay"}` als exemples de format).
    replacements = {
        "{{PROBLEM_ENUNCIAT}}":    problem["enunciat"],
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
            f"Placeholders no resolts al system prompt {problem_id}: "
            f"{unresolved}. Cal afegir-los a la taula de substitucions."
        )

    _system_prompt_cache[problem_id] = template
    return template


# -----------------------------------------------------------------------------
# Crida única al model amb multi-turn contents
# -----------------------------------------------------------------------------

def _is_retriable(err: Exception) -> bool:
    msg = str(err).upper()
    return any(p in msg for p in RETRY_PATTERNS)


def _format_position_marker(current_position: dict,
                            total_steps: int = None,
                            diagnostic_options: list = None) -> str:
    """Construeix la línia de marcador de posició que s'antepondrà al
    darrer missatge user. El system prompt v1.1 documenta aquest
    format i instrueix el model a respectar-lo com a font de veritat
    sobre on és la sessió.

    Format:
      [Posició actual: Pas N de TOTAL]                       — pas normal
      [Posició actual: reforç <PREREQ_ID> activat (tornaràs
                       al Pas N en acabar)]                  — en reforç

    El `<PREREQ_ID>` es prengut directament de `current_position["prereq"]`
    (per exemple "PRE-PARAM" per a IC-001).

    Args:
        current_position: {"step": int|None, "prereq": str|None}.
        total_steps: nombre total de passos del problema actiu. Si és
            None, es deriva de `PB.PROBLEM` (back-compat). En contextos
            multi-problema, el caller (tutor_turn) ha de passar-lo
            explícitament a partir del seu paràmetre `problem`.
        diagnostic_options: codis de diagnòstic vàlids per al pas actual
            (Tasca 4). Si es passa, s'afegeix una segona línia al marcador
            recordant al model els codis que pot posar al camp `diagnostic`
            del control block. És infraestructura del sistema, invisible per
            a l'alumne, igual que la línia de posició.

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
            base = (f"[Posició actual: reforç {prereq} activat "
                    f"(tornaràs al Pas {step} en acabar)]")
        else:
            base = f"[Posició actual: reforç {prereq} activat]"
    elif step is not None:
        if total_steps is None:
            total_steps = len(PB.PROBLEM["passos"])
        base = f"[Posició actual: Pas {step} de {total_steps}]"
    else:
        return ""

    if diagnostic_options:
        codes = ", ".join(diagnostic_options)
        base += (f"\n[Codis de diagnòstic vàlids ara: {codes}. "
                 f"Posa'n un al camp \"diagnostic\" del control block si "
                 f"fas stay/retreat; posa null si avances.]")
    return base


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
    `action`, `objectives_met` i `diagnostic` ben formats, recorrent a
    "stay" per defecte si el JSON falla o té camps inesperats. El camp
    `_parse_error` indica si hi va haver fallback.

    El parser és deliberadament ximple respecte al `diagnostic`: només el
    llegeix com a string (o None) i NO el valida contra cap catàleg. La
    validació/normalització del codi contra el catàleg del pas la fa el
    caller (tutor_turn → PB.normalize_diagnostic), que és qui coneix el
    problema i el pas actuals. Un `diagnostic` absent o mal format NO és un
    error de parse: és opcional. Només JSON malformat o `action` absent
    disparen el fallback-a-stay (i marquen `_parse_error`).
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
            "diagnostic": None,
            "_parse_error": True,
        }

    action = data.get("action", "stay")
    if action not in VALID_ACTIONS:
        action = "stay"

    objectives = data.get("objectives_met", [])
    if not isinstance(objectives, list):
        objectives = []

    # `diagnostic`: només acceptem string en cru aquí. Qualsevol altra cosa
    # (absent, null, número, llista...) es coerciona a None. La normalització
    # contra el catàleg del pas la fa el caller.
    diagnostic = data.get("diagnostic")
    if not isinstance(diagnostic, str):
        diagnostic = None

    return {
        "action": action,
        "objectives_met": objectives,
        "diagnostic": diagnostic,
        "_parse_error": False,
    }


# -----------------------------------------------------------------------------
# Mode de reserva (sense IA) — xarxa de seguretat per a la demo
# -----------------------------------------------------------------------------

def _normalitza(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _fallback_turn(problem: dict, current_position: dict,
                   transcript: list) -> dict:
    """Torn sense IA: heurística per paraules clau perquè el flux es pugui
    provar (o salvar una demo) sense clau d'API.

    No és pedagògicament intel·ligent: detecta si l'última resposta de
    l'alumne conté prou keywords del concepte clau del pas i, si és així,
    avança; si no, ofereix una pista pre-escrita. La pregunta canònica del
    pas següent NO la posa aquí — la injecta la màquina d'estats
    (simulator.enrich_after_transition), igual que en mode IA.
    """
    step = current_position.get("step")
    prereq = current_position.get("prereq")
    pid = problem["id"]

    ultim_student = next(
        (t["content"] for t in reversed(transcript)
         if t["role"] == "student"),
        "",
    )
    demana_pista = "(L'alumne demana una pista)" in ultim_student

    # Dins del reforç: avaluem contra els keywords del prerequisit.
    if prereq:
        bundle = PB.PROBLEMS[pid]
        pre = bundle["prerequisites"][bundle["prereq_id"]]
        claus = [_normalitza(k) for k in pre.get("keywords_required", [])]
        resp = _normalitza(ultim_student)
        encerts = sum(1 for k in claus if k and k in resp)
        if not demana_pista and encerts >= 2:
            return _fb_result("Molt bé, aquesta és la distinció clau. "
                              "Tornem on érem.", "advance")
        return _fb_result(
            "Pensa-ho així: una de les dues quantitats és un nombre fix "
            "(encara que no el coneguem) i l'altra canvia cada cop que "
            "agafem una mostra nova. Quina és quina?", "stay")

    # Pas normal: keywords de les dependències del pas.
    paso = problem["passos"][step - 1] if step else problem["passos"][0]
    dep_keys = paso.get("key_concepts", [])
    deps = PB.PROBLEMS[pid]["dependencies"]
    claus = []
    for dk in dep_keys:
        claus += [_normalitza(k) for k in deps.get(dk, {}).get("keywords", [])]
    resp = _normalitza(ultim_student)
    encerts = sum(1 for k in claus if k and k in resp)

    pistes = PB.step_hints(pid, step) if step else []
    # Codi probable d'aquest pas (per anotar el diagnòstic en els stays del
    # mode reserva). El fallback no "entén", però el typical_error_label del
    # pas és l'aposta determinista raonable i evita un panell buit.
    likely = PB.likely_diagnostic_for_step(pid, step) if step else None

    if demana_pista:
        pista = pistes[0] if pistes else (
            "Comença pel càlcul concret que demana l'enunciat i mira què "
            "en surt.")
        return _fb_result(f"Pista: {pista}", "stay", diagnostic=likely)

    # Llindar deliberadament permissiu (el fallback ha de deixar avançar
    # la demo, no fer de porter estricte).
    if encerts >= 2 or (encerts >= 1 and len(resp) > 80):
        return _fb_result("Molt bé, ho has argumentat correctament. "
                          "Avancem.", "advance")

    # Stay per error conceptual: si el pas té una pista mapejada al codi
    # probable, fem-la servir; si no, la primera pista pre-escrita.
    pista = PB.hint_for_diagnostic(pid, step, likely) if step else None
    if not pista:
        pista = pistes[0] if pistes else (
            "Repassa el concepte clau del pas i justifica la teva "
            "resposta amb les teves paraules.")
    return _fb_result(f"Encara no del tot. Pista: {pista}", "stay",
                      diagnostic=likely)


def _fb_result(reply: str, action: str, diagnostic: str = None) -> dict:
    return {
        "reply": reply,
        "action": action,
        "objectives_met": [],
        "diagnostic": diagnostic,
        "n_api_calls": 0,
        "mode": "py",
        "raw_output": "",
        "control_parse_ok": True,
    }


# -----------------------------------------------------------------------------
# Funció pública: tutor_turn
# -----------------------------------------------------------------------------

def tutor_turn(problem: dict, current_position: dict,
               transcript: list) -> dict:
    """
    Una crida al model per al pròxim torn del tutor.

    Args:
        problem: bundle d'un problema (com els que retorna
            `PB.get(problem_id)["problem"]`, i.e. el dict que té
            id/tema/enunciat/passos). En entorns multi-problema, el
            caller ha de triar quin problema treballar per a la
            sessió i passar-ne el bundle aquí; el system prompt i el
            marcador de posició se'n deriven.
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
            "diagnostic": str|None,    # codi de malentesa del catàleg del pas
                                       #   (Tasca 4); None si avança o no en té.
                                       #   NO influeix mai en apply_action.
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
    # El transcript ha d'alternar tutor/student sense repeticions
    # consecutives. Gemini espera alternança user/model a `contents`;
    # missatges consecutius del mateix rol fan que el model entri en
    # un mode de pensament llarg intentant reconciliar l'estructura,
    # consumint tokens del pressupost de sortida i truncant la resposta
    # visible. Aquesta validació atrapa bugs del caller (p.ex. oblidar
    # d'afegir la resposta del tutor al transcript entre torns) en
    # comptes de deixar-los degradar silenciosament.
    for i in range(1, len(transcript)):
        if transcript[i]["role"] == transcript[i - 1]["role"]:
            raise ValueError(
                f"tutor_turn requereix un transcript que alterni "
                f"tutor/student sense repeticions consecutives, però "
                f"als índexs {i-1} i {i} hi ha dos torns "
                f"'{transcript[i]['role']}' seguits. "
                f"Possible causa: el caller no afegeix la resposta del "
                f"tutor al transcript després de cada crida."
            )

    # Mode de reserva: sense SDK/clau, no cridem l'API. Xarxa de seguretat
    # perquè una demo en directe no caigui si la connexió falla.
    if not ia_disponible():
        return _fallback_turn(problem, current_position, transcript)

    system_instruction = _load_system_prompt(problem)

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
    position_marker = _format_position_marker(
        current_position,
        total_steps=len(problem["passos"]),
        diagnostic_options=PB.allowed_diagnostics(
            problem["id"], current_position.get("step")
        ),
    )
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
        control = {"action": "stay", "objectives_met": [], "diagnostic": None}
        parse_ok = False

    # Normalització del diagnòstic contra el catàleg del pas actual. Punt
    # únic de validació (el parser no toca el catàleg). Codi desconegut →
    # GEN_other; absent/mal format → None. Quan l'acció és "advance" el
    # diagnòstic no té sentit (l'alumne ha encertat): el forcem a None per
    # mantenir la semàntica "diagnostic = malentesa en curs".
    raw_diag = control.get("diagnostic")
    if control["action"] == "advance":
        diagnostic = None
    else:
        diagnostic = PB.normalize_diagnostic(
            problem["id"], current_position.get("step"), raw_diag
        )

    return {
        "reply": reply,
        "action": control["action"],
        "objectives_met": control["objectives_met"],
        "diagnostic": diagnostic,
        "n_api_calls": 1,
        "mode": "ai",
        "raw_output": raw_output,
        "control_parse_ok": parse_ok,
    }
