"""
Crides a Gemini per al tutor d'IC.

Quatre funcions públiques:
  - judge_step(step, student_answer, context=None, allow_resample=True)
        → veredicte + raó + etiqueta + metadades de self-consistency
  - judge_prereq(prereq, student_answer, allow_resample=True)
        → veredicte (correct|keyword_only|incorrect) + raó + metadades
  - generate_hint(step, dep_id, student_answer, judge_reason,
                  error_label, prior_hints)
        → pista socràtica dirigida al pas
  - generate_prereq_hint(prereq, student_answer, judge_reason,
                          prior_hints)
        → pista socràtica dirigida al reforç

Variables d'entorn:
  GEMINI_API_KEY (obligatòria)
  GEMINI_MODEL   (opcional, default "gemini-2.5-flash")
"""

import json
import os
import re
import time

from google import genai
from google.genai import types as genai_types

import problem as PB

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Reintents per a errors transitoris (503 UNAVAILABLE típicament).
# Tres intents amb backoff lineal són suficients per a una demo.
MAX_ATTEMPTS = 3
RETRY_PATTERNS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
                  "500", "INTERNAL", "DEADLINE_EXCEEDED")

_client = None


def _get_client():
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY no està definida. "
                "Fes 'export GEMINI_API_KEY=...' abans d'executar."
            )
        _client = genai.Client(api_key=key)
    return _client


def _is_retriable(err: Exception) -> bool:
    s = str(err)
    return any(pat in s for pat in RETRY_PATTERNS)


def _call(system: str, user: str, json_mode: bool = True,
          max_tokens: int = 400, temperature: float = 0.2) -> str:
    """Crida a Gemini amb reintents per a errors transitoris.
    Llança l'última excepció si tots els intents fallen, o si l'error
    és no-retriable (4xx d'autenticació, etc.)."""
    client = _get_client()
    cfg_kwargs = {
        "system_instruction": system,
        "max_output_tokens": max_tokens,
        "temperature": temperature,
        # Models "flash" no fan thinking; desactivem-ho explícitament per
        # estalviar latència.
        "thinking_config": genai_types.ThinkingConfig(thinking_budget=0),
    }
    if json_mode:
        cfg_kwargs["response_mime_type"] = "application/json"
    cfg = genai_types.GenerateContentConfig(**cfg_kwargs)

    last_err = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = client.models.generate_content(
                model=MODEL, contents=user, config=cfg,
            )
            text = (resp.text or "").strip()
            if not text:
                raise RuntimeError(f"Resposta buida de {MODEL}")
            return text
        except Exception as e:
            last_err = e
            if not _is_retriable(e) or attempt == MAX_ATTEMPTS - 1:
                raise
            # Backoff: 1.5s, 3s, 6s
            time.sleep(1.5 * (2 ** attempt))
    raise last_err


def _parse_json(text: str) -> dict:
    """Parseja JSON tolerant: treu fences ```json, busca primer { vàlid."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    # Fallback: troba la primera clau equilibrada.
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start: i + 1])
                except Exception:
                    return {}
    return {}


# ============================================================
# System prompts
# ============================================================
_SYSTEM_JUDGE = """
Ets un examinador estricte però just d'estadística introductòria.
Avalues respostes d'estudiants sobre la INTERPRETACIÓ d'un interval
de confiança freqüentista.

L'error clàssic d'aquest tema és atribuir probabilitat al paràmetre
poblacional. Frases com "hi ha un 95% de probabilitat que μ estigui
entre A i B", o "μ té un 95% de probabilitat d'estar a l'interval",
o qualsevol formulació equivalent, són INCORRECTES en el marc
freqüentista. El 95% és una propietat del procediment de construcció
d'intervals (la cobertura a llarg termini), no una probabilitat sobre
el paràmetre μ.

REGLA IMPORTANT: si la resposta de l'alumne conté l'error clàssic
—encara que la resta sigui correcta— classifica-la com a
"typical_error" amb error_label "INT_prob_param". No felicitis el
60% bé si el 40% conté l'error clàssic.

Classifica la resposta en exactament una de:

  "correct"         — interpretació freqüentista correcta i
                      AUTO-SUFICIENT. Una resposta auto-suficient
                      conté tant (a) el concepte clau pertinent al
                      pas (μ fix/constant, repetició de mostres,
                      confiança vs. probabilitat...) com (b) la seva
                      APLICACIÓ explícita a la pregunta del pas
                      (què vol dir el concepte aquí, o com respon
                      la pregunta). Pot ser concisa o informal, però
                      els dos elements (concepte + aplicació) han de
                      ser-hi sense que l'examinador hagi d'afegir-los.

  "typical_error"   — l'alumne fa un intent de raonament però és
                      incorrecte. Inclou:
                       (a) l'error clàssic (atribuir probabilitat al
                           paràmetre μ) o qualsevol variant
                           reconeixible
                       (b) definicions alternatives inventades amb
                           aparença sofisticada (p.ex. "l'IC és la
                           unió de tots els intervals que contenen el
                           paràmetre", "és la mitjana de mitjanes")
                       (c) confondre l'IC amb una predicció sobre
                           mostres o observacions futures
                       (d) RESPOSTA-KEYWORD: conté un mot o sintagma
                           pertinent (constant, fix, paràmetre,
                           confiança, repetició, procediment...)
                           però NO el justifica ni l'aplica a la
                           pregunta concreta. Etiqueta: KEY_only.

  "conceptual_gap"  — l'alumne demostra que NO té els conceptes
                      bàsics: no sap què és μ vs x̄, tracta la mostra
                      com si fos la població, o respon amb evident
                      desorientació respecte al tema ("no entenc",
                      "què és això", etc.)

CONTRAEXEMPLES (cap d'aquests és "correct"; tots són typical_error
amb error_label KEY_only):
  Pas 1 ("Probabilitat sobre què?") → "si repetim el mostreig
    moltes vegades" (té el concepte de repetició però no diu què
    passa amb la repetició)
  Pas 2 ("Per què és incorrecta?") → "mu és constant" (té el
    concepte μ-fix però no explica per què fa la frase incorrecta)
  Pas 3 ("Dona una interpretació") → "tinc una confiança del 95%"
    (repeteix el terme del pas sense aplicar-lo: confiança sobre
    què? sobre quin interval? sobre μ?)

REGLA DE DESEMPAT 1 (auto-suficiència): abans de marcar "correct",
llegeix la resposta sense afegir-hi cap context. Si per fer-la
"sonar correcta" hauries d'introduir tu mateix la justificació o la
conclusió al camp "reason", NO és "correct" — és typical_error amb
error_label KEY_only.

REGLA DE DESEMPAT 2 (raonament estructurat vs. buit): si hi ha un
raonament identificable encara que erroni, prefereix "typical_error"
abans que "conceptual_gap". Reserva "conceptual_gap" per a casos
clars de manca de fonament conceptual.

REGLA DE DESEMPAT 3 (patró de la sessió, només si t'arriba context):
si el missatge inclou una secció "PATRÓ DE LA SESSIÓ", aplica
aquestes regles ABANS de fixar el verdict. Si el missatge NO inclou
aquesta secció, ignora aquesta regla i classifica únicament sobre la
resposta puntual.

  P3a — Si "prereq.final_verdict" és "correct" (l'alumne acaba de
        demostrar la distinció μ vs x̄ explícitament al reforç),
        una resposta ambigua entre typical_error i conceptual_gap
        sobre el pas actual ha de preferir "typical_error". El
        concepte hi és; la fallada més probable és aplicació.

  P3b — Si "recent_steps" conté algun verdict "correct" en passos
        anteriors d'aquest mateix problema, l'alumne ha demostrat
        capacitat de raonament estructurat. Davant d'ambigüitat
        typical_error vs conceptual_gap, prefereix "typical_error".

  P3c — Contrabalanç: si "concept_failure_streak" és 2 o més (dos o
        més veredictes no-correct consecutius prèviament en aquesta
        sessió — el comptador NO distingeix typical_error de
        conceptual_gap), el patró ja indica dificultat persistent.
        En aquest cas P3a i P3b queden suspeses: classifica únicament
        sobre la resposta puntual.

Aquestes regles són ADDICIONALS, no substitueixen les anteriors.
Si la resposta és clarament "correct" (compleix auto-suficiència) o
clarament "conceptual_gap" (manca de fonament evident), el patró no
canvia el verdict.

AUTO-AVALUACIÓ DE CONFIANÇA (camp "confidence" al JSON de sortida):
indica la teva pròpia confiança en el verdict. NO és visible a
l'alumne; només la fem servir per decidir si val la pena re-classificar
amb un mostreig determinístic.

  "high"   — el verdict és inequívoc, cap signe d'ambigüitat. La
             majoria de respostes haurien de caure aquí. La resposta
             és clarament correct, clarament typical_error amb una
             etiqueta evident, o clarament conceptual_gap.

  "medium" — hi ha un dubte raonable entre dos verdicts. Casos
             típics: KEY_only vs conceptual_gap (té un mot pertinent
             però quasi cap raonament); typical_error amb etiqueta
             no òbvia (no INT_prob_param ni KEY_only, però sí algun
             raonament errat); correct però l'auto-suficiència
             frega el límit.

  "low"    — molt poc material per decidir: resposta extremament
             curta, ambigua o críptica fins al punt que qualsevol
             verdict requereix interpretació.

Sigues honest amb aquesta auto-avaluació. No marquis "high" per
defecte: si dubtes, marca "medium" o "low". Aquesta calibració és el
que ens permet decidir quan re-mostrejar.

Respon ÚNICAMENT amb JSON vàlid, sense markdown ni preàmbul:
{"verdict": "...", "reason": "una frase breu en català dirigida a
l'alumne", "error_label": "etiqueta o null", "confidence": "high|medium|low"}
""".strip()


_SYSTEM_HINT = """
Ets un tutor socràtic d'estadística. La teva feina és donar UNA pista
mínima que orienti l'alumne cap a la resposta sense revelar-la mai.

REGLES INVIOLABLES:
- No diguis mai la resposta literal del pas. Pregunta o reformula.
- Si l'alumne ha dit una cosa concreta (correcta o errònia), agafa
  aquell tros i fes-lo evolucionar amb UNA pregunta dirigida. La pista
  ha de partir d'allò que ha dit, no començar de zero.
- Si NO t'han passat resposta de l'alumne, fes una pregunta genèrica
  però dirigida al concepte clau del pas.
- Si t'han passat pistes anteriors, NO les repeteixis ni les
  parafrasejis — prova un angle diferent.
- Màxim 2 frases. En català. Sense LaTeX ni fórmules complicades.

EXEMPLES per al pas «el 95% és una probabilitat sobre què, exactament?»:

  Cas A — resposta de l'alumne: «si repetim el mostreig moltes vegades»
          (keyword_only: té el concepte de repetició però no diu què
          passa amb la repetició).

    ❌ PISTA DOLENTA — revela la resposta:
       «Exacte: si repetim el mostreig 100 vegades, 95 dels intervals
       construïts contindran μ.»

    ✓ PISTA BONA — pregunta sobre el tros que ha dit:
       «Has dit "repetim el mostreig moltes vegades" — d'acord. I
       d'aquestes repeticions, què en mires? Què compta el 95%?»

  Cas B — l'alumne acaba d'arribar al pas i prem `?` sense respondre.

    ❌ PISTA DOLENTA — repeteix la pregunta sense ajudar:
       «Pensa bé sobre què mesura el 95%.»

    ✓ PISTA BONA — orienta sense revelar:
       «El 95% no descriu μ directament. A què passes el 95%, doncs:
       a la mostra, al càlcul, a l'interval... a què?»

  Cas C — resposta de l'alumne: «hi ha un 95% de probabilitat que
          μ estigui entre 3,2 i 4,8» (INT_prob_param: l'error clàssic).

    ❌ PISTA DOLENTA — explica per què es equivoca:
       «μ és un paràmetre fix, no té probabilitat associada.»

    ✓ PISTA BONA — qüestiona el supòsit ocult:
       «Has dit que μ té un 95% de probabilitat — què hauria de ser
       cert sobre μ perquè aquesta frase tingués sentit?»

Genera UNA pista del segon tipus (la BONA) per a la situació següent.
""".strip()


# System prompt per al judge del prerequisit PRE-PARAM.
# Substitueix la validació deterministica per keyword matching: aquesta
# era exactament el mateix patró de fallada (KEY_only) que el judge
# principal va patir al Phase 2 del project log. La validació per
# keyword permetia que respostes com "μ és fix" passessin sense que
# l'alumne hagués mencionat x̄ ni l'aleatorietat — i, inversament,
# rebutjava respostes correctes que no usaven el vocabulari reservat.
#
# Aquest prompt aplica la mateixa lògica d'auto-suficiència del
# _SYSTEM_JUDGE principal, però adaptada al fet que la pregunta del
# prereq té DUES afirmacions a expressar (una sobre μ, una sobre x̄)
# que han de ser-hi totes dues per ser correct.
_SYSTEM_JUDGE_PREREQ = """
Estàs avaluant la resposta d'un alumne a un exercici de reforç sobre
la distinció paràmetre poblacional vs. estadístic mostral. L'exercici
és prerequisit per poder seguir un problema d'interpretació d'intervals
de confiança.

La pregunta és:
  «Quina diferència hi ha entre μ (la mitjana poblacional) i x̄ (la
  mitjana d'una mostra concreta)? Quina de les dues és aleatòria i
  quina és fixa?»

Una resposta CORRECTA ha d'expressar AUTO-SUFICIENTMENT que:
  (A) μ és fix, constant, no aleatori — un nombre poblacional
      desconegut però determinat.
  (B) x̄ varia segons la mostra, és aleatori.

Les DUES afirmacions han de ser-hi explícitament. No has d'introduir-les
tu mentalment per fer-les "sonar correctes". Si has d'afegir tu (A) o
(B) al teu propi raonament per fer la resposta acceptable, la resposta
és keyword_only, no correct.

CATEGORIES:

  "correct"      — (A) i (B) són clares i s'apliquen al símbol que
                   pertoca. Pot ser informal, concisa, o usar
                   sinònims ("la mitjana real", "la mitjana de la
                   mostra"); el que importa és que es vegi quin dels
                   dos és fix i quin és aleatori, sense ambigüitat.

  "keyword_only" — Conté mots pertinents (fix, constant, paràmetre,
                   aleatori, varia, no aleatori...) però NO completa
                   la distinció. Exemples concrets de keyword_only:
                     · "μ és fix" (no diu res de x̄)
                     · "x̄ és aleatòria" (no diu res de μ)
                     · "una és fixa i l'altra varia" (no especifica
                       QUINA és QUINA)
                     · "els paràmetres són constants i els estadístics
                       varien" (parla en abstracte sense aplicar a μ i x̄)

  "incorrect"    — Resposta clarament errònia. Inclou:
                     · Atribueix aleatorietat a μ ("μ varia segons la
                       mostra") o constància a x̄ ("x̄ és fixa")
                     · Inverteix els dos rols
                     · Confessa no saber-ho ("no entenc", "què és μ?")
                     · Resposta sense fonament conceptual del problema

REGLA DE DESEMPAT (auto-suficiència): llegeix la resposta sense afegir
res. Si per qualificar-la de "correct" hauries d'afegir tu la part
sobre μ, o sobre x̄, o sobre quin és aleatori i quin no, NO és correct
— és keyword_only.

AUTO-AVALUACIÓ DE CONFIANÇA (camp "confidence" al JSON):
  "high"   — verdict inequívoc.
  "medium" — dubte raonable entre keyword_only i incorrect, o entre
             correct i keyword_only.
  "low"    — resposta massa curta o ambigua per decidir amb seguretat.

No marquis "high" per defecte. Si dubtes, marca medium o low — així
podem re-classificar amb un mostreig determinístic.

Respon ÚNICAMENT amb JSON vàlid, sense markdown ni preàmbul:
{"verdict": "...", "reason": "una frase curta en català dirigida a
l'alumne. Si és keyword_only, indica què li falta SENSE revelar la
distinció completa. Si és incorrect, pots ser més explicatiu.",
"confidence": "high|medium|low"}
""".strip()


# System prompt per al generador de pistes del reforç. La pregunta
# del prereq té estructura específica (dues afirmacions a expressar
# alhora: una sobre μ, una sobre x̄), i les pistes adequades hi tenen
# una estructura diferent de les pistes del problema principal: ataquen
# l'afirmació que falta sense revelar-la. Per això es manté separat
# de _SYSTEM_HINT.
_SYSTEM_HINT_PREREQ = """
Ets un tutor socràtic. La teva feina és donar UNA pista mínima que
orienti l'alumne a completar la distinció μ vs x̄ (paràmetre poblacional
fix vs estadístic mostral aleatori), sense revelar-la mai.

REGLES INVIOLABLES:
- No diguis mai literalment ni «μ és fix» ni «x̄ és aleatòria».
  Pregunta o reformula.
- Si l'alumne ha parlat només d'un dels dos símbols, fes una pregunta
  que el porti a pensar en l'altre.
- Si l'alumne ha invertit els dos rols, fes una pregunta que el porti
  a notar quina dependeix de la mostra concreta.
- Si t'han passat pistes anteriors, no les repeteixis.
- Màxim 2 frases. En català. Sense LaTeX.

EXEMPLES per a la mateixa pregunta del reforç:

  Cas A — resposta de l'alumne: «μ és constant»
          (keyword_only: només parla d'un dels dos símbols)

    ❌ PISTA DOLENTA — completa la resposta:
       «Sí, μ és constant. I x̄ varia segons la mostra.»

    ✓ PISTA BONA — porta l'alumne a notar el que falta:
       «D'acord amb el que has dit sobre μ. I si t'agafessin una altra
       mostra d'aquesta mateixa població, la x̄ que en sortiria seria
       la mateixa o diferent?»

  Cas B — resposta de l'alumne: «els paràmetres són constants i els
          estadístics varien» (keyword_only: abstracte, no aplica)

    ❌ PISTA DOLENTA — fa la connexió per l'alumne:
       «Aplica-ho: μ és el paràmetre, x̄ és l'estadístic.»

    ✓ PISTA BONA — pregunta sobre l'aplicació:
       «Bé en abstracte. Aplica-ho ara: dels dos símbols del problema
       (μ i x̄), quin és el paràmetre i quin l'estadístic?»

Genera UNA pista del segon tipus per a la situació següent.
""".strip()


# ============================================================
# Les tres funcions públiques
# ============================================================
_VALID_CONFIDENCE = ("high", "medium", "low")


def _format_recent_steps(recent_steps: list) -> str:
    """Renderitza la llista de torns recents per al context del judge
    (Proposta 1). Format: 'pas N → verdict (etiqueta)', més recents
    primer, separats per punt i coma."""
    if not recent_steps:
        return "(cap torn previ)"
    parts = []
    for s in recent_steps:
        sid = s.get("step_id", "?")
        v = s.get("verdict", "?")
        label = s.get("error_label")
        if label:
            parts.append(f"pas {sid} → {v} ({label})")
        else:
            parts.append(f"pas {sid} → {v}")
    return "; ".join(parts)


def _format_prereq_info(prereq: dict) -> str:
    """Renderitza l'estat del reforç per al context del judge."""
    if not prereq or not prereq.get("activated"):
        return "no s'ha activat en aquesta sessió"
    final = prereq.get("final_verdict") or "?"
    attempts = prereq.get("attempts", 1)
    return f"activat; verdict final={final}; intents={attempts}"


def _build_judge_user_msg(step: dict, student_answer: str, context: dict = None) -> str:
    """Construeix el user message per a `judge_step` (i la seva
    versió interna single-call). Extret a funció pròpia per evitar
    duplicar la construcció entre la primera crida i el re-mostreig."""
    parts = [
        "Pas presentat a l'alumne:",
        f"  {step['text']}",
        "",
        "Resum de la resposta esperada (NO el reveli a l'alumne):",
        f"  {step['expected_summary']}",
        "",
        "Error típic per a aquest pas:",
        f"  {step['typical_error']} (etiqueta: {step['typical_error_label']})",
        "",
        "Resposta de l'alumne:",
        f"  {student_answer}",
    ]
    if context:
        parts += [
            "",
            "PATRÓ DE LA SESSIÓ:",
            f"  - Intents previs en aquest pas: {context.get('step_attempts', 0)}",
            f"  - Reforç PRE-PARAM: {_format_prereq_info(context.get('prereq'))}",
            f"  - Darrers torns: {_format_recent_steps(context.get('recent_steps', []))}",
            f"  - concept_failure_streak: {context.get('concept_failure_streak', 0)}",
        ]
    parts += ["", "Classifica la resposta."]
    return "\n".join(parts)


def _judge_step_single(user_msg: str, temperature: float = None) -> dict:
    """Una crida individual al judge. Retorna el dict parsejat amb
    verdict, reason, error_label i confidence ja normalitzats.

    `temperature` permet forçar 0 per al re-mostreig (Proposta 5);
    si és None, fa servir el default de `_call` (0.2)."""
    kwargs = {"json_mode": True, "max_tokens": 300}
    if temperature is not None:
        kwargs["temperature"] = temperature
    raw = _call(_SYSTEM_JUDGE, user_msg, **kwargs)
    data = _parse_json(raw)
    v = data.get("verdict", "typical_error")
    if v not in ("correct", "typical_error", "conceptual_gap"):
        v = "typical_error"
    c = data.get("confidence", "high")
    if c not in _VALID_CONFIDENCE:
        c = "high"
    return {
        "verdict": v,
        "reason": data.get("reason", ""),
        "error_label": data.get("error_label"),
        "confidence": c,
    }


def judge_step(step: dict, student_answer: str, context: dict = None,
               allow_resample: bool = True) -> dict:
    """
    Avalua la resposta de l'alumne. Self-consistency selectiva
    (Proposta 5): si la primera crida reporta confiança baixa o
    mitjana, en fem una segona a temperatura 0 i agafem la segona
    com a verdict final.

    Retorna: {verdict, reason, error_label, confidence, resampled,
              initial_verdict?, initial_error_label?, agreement?,
              n_api_calls}

    Args:
        step: el pas actual.
        student_answer: la resposta de l'alumne.
        context: opcional, trajectòria de la sessió (Proposta 1).
        allow_resample: si False, el re-mostreig es desactiva encara
            que la confiança sigui baixa. L'invocador el posa a False
            quan no té quota suficient per a 2 crides.

    Llança excepció si Gemini falla després dels reintents interns
    de `_call`. Si la PRIMERA crida té èxit però la SEGONA falla,
    retornem el verdict de la primera (millor que cap classificació)
    i marquem `resampled: false`.
    """
    user_msg = _build_judge_user_msg(step, student_answer, context)
    first = _judge_step_single(user_msg)
    n_calls = 1

    if not allow_resample or first["confidence"] == "high":
        return {
            "verdict": first["verdict"],
            "reason": first["reason"],
            "error_label": first["error_label"],
            "confidence": first["confidence"],
            "resampled": False,
            "n_api_calls": n_calls,
        }

    # Re-mostreig: segona crida amb temperatura 0 sobre exactament
    # el mateix prompt. La idea és que aquesta crida convergeixi a
    # l'opció modal del model — la primera (temp 0.2) pot haver
    # sampled una opció menys probable.
    try:
        second = _judge_step_single(user_msg, temperature=0)
        n_calls = 2
    except Exception:
        # Si la segona crida falla, retornem la primera. El cost en
        # qualitat és el mateix que tindríem sense self-consistency,
        # però no degradem la robustesa global per un incident tècnic
        # a una crida concretament re-mostrejada.
        return {
            "verdict": first["verdict"],
            "reason": first["reason"],
            "error_label": first["error_label"],
            "confidence": first["confidence"],
            "resampled": False,
            "resample_failed": True,
            "n_api_calls": n_calls,
        }

    agreement = (second["verdict"] == first["verdict"])

    # Política: agafem el verdict de la segona crida (més
    # determinista) com a final. Si coincideixen, no canvia res; si
    # no, hem corregit una possible fluctuació de la primera crida.
    return {
        "verdict": second["verdict"],
        "reason": second["reason"],
        "error_label": second["error_label"],
        "confidence": first["confidence"],  # la self-report del primer
        "resampled": True,
        "initial_verdict": first["verdict"],
        "initial_error_label": first["error_label"],
        "agreement": agreement,
        "n_api_calls": n_calls,
    }


def generate_hint(step: dict, dep_id: str,
                  student_answer: str = None,
                  judge_reason: str = None,
                  error_label: str = None,
                  prior_hints: list = None) -> str:
    """Pista socràtica per al pas actual.

    Paràmetres opcionals afegits a la Proposta 3: si s'informen, la
    pista es genera DIRIGIDA a l'error concret de l'alumne en lloc
    d'una pista genèrica per al pas. Quan `student_answer` és None
    (cas del primer `?` sense haver respost res), la pista és genèrica
    però el prompt sap distingir-ho i adapta el to.

    Args:
        step: el pas actual (de PB.PROBLEM["passos"]).
        dep_id: la dependència rellevant per a aquest pas.
        student_answer: darrera resposta no-correct de l'alumne a aquest
            pas, si n'hi ha.
        judge_reason: text del camp `reason` que el judge va retornar
            per a aquella resposta.
        error_label: etiqueta d'error del judge (p.ex. "KEY_only",
            "INT_prob_param") si n'hi ha.
        prior_hints: llista de pistes ja donades a aquest pas; el
            prompt demana al model que no les repeteixi.

    Returns: la pista en text pla, o un missatge d'error si la IA
    falla (no llança excepció — la pista és recuperable).
    """
    dep = PB.DEPENDENCIES.get(dep_id, {})
    dep_desc = dep.get("description", dep_id)

    parts = [
        "PAS PRESENTAT A L'ALUMNE:",
        f"  {step['text']}",
        "",
        "CONCEPTE CLAU QUE HA D'APLICAR:",
        f"  {dep_desc}",
    ]

    if student_answer:
        parts += [
            "",
            "RESPOSTA DE L'ALUMNE (incorrecta):",
            f"  {student_answer}",
        ]

    if judge_reason:
        parts += [
            "",
            "DIAGNÒSTIC DEL JUDGE (per què la resposta no era correcta):",
            f"  {judge_reason}",
        ]

    if error_label:
        label_hint = ""
        if error_label == "KEY_only":
            label_hint = ("  → L'alumne té mots correctes però no els "
                          "justifica ni els aplica. La pista ha d'agafar "
                          "el mot que ha dit i fer-li la pregunta que "
                          "el porti a aplicar-lo.")
        elif error_label == "INT_prob_param":
            label_hint = ("  → L'alumne tracta μ com a variable aleatòria. "
                          "La pista ha de qüestionar aquest supòsit ocult "
                          "sense afirmar directament que μ és fix.")
        parts += [
            "",
            f"ETIQUETA D'ERROR: {error_label}",
        ]
        if label_hint:
            parts.append(label_hint)

    if prior_hints:
        parts += [
            "",
            "PISTES JA DONADES A AQUEST PAS (NO les repeteixis ni les"
            " parafrasegis; canvia d'angle):",
        ]
        for h in prior_hints:
            parts.append(f"  - {h}")

    parts += [
        "",
        "Genera UNA pista socràtica dirigida.",
    ]

    user_msg = "\n".join(parts)

    try:
        return _call(_SYSTEM_HINT, user_msg, json_mode=False,
                     max_tokens=200, temperature=0.4).strip()
    except Exception as e:
        return f"(No s'ha pogut generar la pista: {e})"


def generate_prereq_hint(prereq: dict,
                         student_answer: str = None,
                         judge_reason: str = None,
                         prior_hints: list = None) -> str:
    """Pista socràtica per al reforç actiu (Proposta 3).

    Variant de `generate_hint` adaptada a l'estructura del prereq:
    la pregunta demana DUES afirmacions (una sobre μ, una sobre x̄)
    i les pistes adequades tenen forma diferent — típicament porten
    l'alumne a pensar en el símbol que falta o a aplicar una
    distinció abstracta als dos símbols concrets.

    Args paral·lels als de `generate_hint`, sense `error_label`
    (al prereq la categoria d'error rellevant ja és el verdict mateix).

    Returns: text de la pista, o missatge d'error si la IA falla.
    """
    parts = [
        "PREGUNTA DEL REFORÇ:",
        f"  {prereq['question']}",
    ]

    if student_answer:
        parts += [
            "",
            "RESPOSTA DE L'ALUMNE:",
            f"  {student_answer}",
        ]

    if judge_reason:
        parts += [
            "",
            "DIAGNÒSTIC DEL JUDGE:",
            f"  {judge_reason}",
        ]

    if prior_hints:
        parts += [
            "",
            "PISTES JA DONADES (NO les repeteixis; canvia d'angle):",
        ]
        for h in prior_hints:
            parts.append(f"  - {h}")

    parts += [
        "",
        "Genera UNA pista socràtica dirigida.",
    ]

    user_msg = "\n".join(parts)

    try:
        return _call(_SYSTEM_HINT_PREREQ, user_msg, json_mode=False,
                     max_tokens=200, temperature=0.4).strip()
    except Exception as e:
        return f"(No s'ha pogut generar la pista: {e})"


def _judge_prereq_single(user_msg: str, temperature: float = None) -> dict:
    """Una crida individual al judge del prereq, paral·lela a
    `_judge_step_single`. Suport per al re-mostreig de la Proposta 5."""
    kwargs = {"json_mode": True, "max_tokens": 250}
    if temperature is not None:
        kwargs["temperature"] = temperature
    raw = _call(_SYSTEM_JUDGE_PREREQ, user_msg, **kwargs)
    data = _parse_json(raw)
    v = data.get("verdict", "incorrect")
    if v not in ("correct", "keyword_only", "incorrect"):
        v = "incorrect"
    c = data.get("confidence", "high")
    if c not in _VALID_CONFIDENCE:
        c = "high"
    return {
        "verdict": v,
        "reason": data.get("reason", ""),
        "confidence": c,
    }


def judge_prereq(prereq: dict, student_answer: str,
                 allow_resample: bool = True) -> dict:
    """
    Avalua la resposta de l'alumne a un exercici de reforç (prereq).

    Substitueix la validació deterministica per keyword matching que
    es feia originalment a `app._process_prereq_turn` (Proposta 2),
    i incorpora self-consistency selectiva (Proposta 5).

    Retorna: {verdict, reason, confidence, resampled, initial_verdict?,
              agreement?, n_api_calls}
      verdict ∈ {"correct", "keyword_only", "incorrect"}

    NOTA: a diferència de judge_step, NO retorna `error_label` perquè
    el catàleg d'errors del prereq és estructuralment més simple
    (només una categoria d'error rellevant: keyword_only, codificada
    al verdict mateix).

    Llança excepció si Gemini falla a la primera crida després dels
    reintents interns de `_call`. Si la PRIMERA crida té èxit però la
    SEGONA falla, retornem el verdict de la primera i marquem
    `resampled: false`.
    """
    user_msg = (
        f"Pregunta del prereq:\n  {prereq['question']}\n\n"
        f"Resposta de l'alumne:\n  {student_answer}\n\n"
        f"Classifica la resposta."
    )
    first = _judge_prereq_single(user_msg)
    n_calls = 1

    if not allow_resample or first["confidence"] == "high":
        return {
            "verdict": first["verdict"],
            "reason": first["reason"],
            "confidence": first["confidence"],
            "resampled": False,
            "n_api_calls": n_calls,
        }

    try:
        second = _judge_prereq_single(user_msg, temperature=0)
        n_calls = 2
    except Exception:
        return {
            "verdict": first["verdict"],
            "reason": first["reason"],
            "confidence": first["confidence"],
            "resampled": False,
            "resample_failed": True,
            "n_api_calls": n_calls,
        }

    agreement = (second["verdict"] == first["verdict"])

    return {
        "verdict": second["verdict"],
        "reason": second["reason"],
        "confidence": first["confidence"],
        "resampled": True,
        "initial_verdict": first["verdict"],
        "agreement": agreement,
        "n_api_calls": n_calls,
    }
