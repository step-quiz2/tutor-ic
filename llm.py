"""
Crides a Gemini per al tutor d'IC.

Tres funcions:
  - judge_step(step, student_answer)   → veredicte + raó + etiqueta
  - diagnose_dependency(step, answer)  → quin concepte falla
  - generate_hint(step, dep_id)        → pista socràtica curta

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
RETRY_PATTERNS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL", "DEADLINE_EXCEEDED")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
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
  "correct"         — interpretació freqüentista correcta, fins i tot
                      si és informal, parcial, o no menciona "a llarg
                      termini" explícitament
  "typical_error"   — l'alumne fa un intent ESTRUCTURAT de raonament,
                      però és incorrecte. Inclou:
                       (a) l'error clàssic (atribuir probabilitat al
                           paràmetre μ) o qualsevol variant
                           reconeixible
                       (b) definicions alternatives inventades amb
                           aparença sofisticada (p.ex. "l'IC és la
                           unió de tots els intervals que contenen el
                           paràmetre", "és la mitjana de mitjanes")
                       (c) confondre l'IC amb una predicció sobre
                           mostres o observacions futures
  "conceptual_gap"  — l'alumne demostra que NO té els conceptes
                      bàsics: no sap què és μ vs x̄, tracta la mostra
                      com si fos la població, o respon amb evident
                      desorientació respecte al tema ("no entenc",
                      "què és això", etc.)

REGLA DE DESEMPAT: si hi ha un raonament identificable encara que
erroni, prefereix "typical_error". Reserva "conceptual_gap" per a
casos clars de manca de fonament conceptual.

Respon ÚNICAMENT amb JSON vàlid, sense markdown ni preàmbul:
{"verdict": "...", "reason": "una frase breu en català dirigida a
l'alumne", "error_label": "etiqueta o null"}
""".strip()


_SYSTEM_DIAG = """
Estàs diagnosticant quin concepte prerequisit li falta a un alumne
que ha mostrat un buit conceptual interpretant un interval de
confiança.

L'única dependència rellevant en aquest sistema és:
  param_vs_stat — distinció entre paràmetre poblacional (μ, fix) i
                  estadístic mostral (x̄, aleatori).

Retorna sempre aquesta dependència, amb una justificació breu.

Respon ÚNICAMENT amb JSON, sense preàmbul:
{"dep_id": "param_vs_stat", "justification": "una frase"}
""".strip()


_SYSTEM_HINT = """
Ets un tutor socràtic d'estadística. L'alumne entén el concepte de
diferència entre paràmetre i estadístic, però no l'està aplicant
correctament al pas actual.

Dona UNA pista socràtica mínima que l'orienti cap a la resposta sense
revelar-la. Pregunta'l alguna cosa que el porti a notar el seu propi
error.

Màxim 2 frases. En català. Sense LaTeX ni fórmules complicades.
""".strip()


# ============================================================
# Les tres funcions públiques
# ============================================================
def judge_step(step: dict, student_answer: str) -> dict:
    """
    Avalua la resposta de l'alumne.
    Retorna: {verdict, reason, error_label}

    Llança excepció si Gemini falla després dels reintents interns de
    `_call` (típicament 503 UNAVAILABLE). L'invocador (app.process_turn)
    l'ha de capturar i tractar com un incident tècnic — NO com un error
    de l'alumne. Anteriorment es retornava un fals 'typical_error' aquí
    mateix, cosa que feia que una caiguda transitòria del proveïdor es
    comptabilitzés com a fallada conceptual.
    """
    user_msg = f"""
Pas presentat a l'alumne:
  {step['text']}

Resum de la resposta esperada (NO el reveli a l'alumne):
  {step['expected_summary']}

Error típic per a aquest pas:
  {step['typical_error']} (etiqueta: {step['typical_error_label']})

Resposta de l'alumne:
  {student_answer}

Classifica la resposta.
""".strip()
    raw = _call(_SYSTEM_JUDGE, user_msg, json_mode=True, max_tokens=300)
    data = _parse_json(raw)
    v = data.get("verdict", "typical_error")
    if v not in ("correct", "typical_error", "conceptual_gap"):
        v = "typical_error"
    return {
        "verdict": v,
        "reason": data.get("reason", ""),
        "error_label": data.get("error_label"),
    }


def diagnose_dependency(step: dict, student_answer: str) -> str:
    """
    Identifica quin prerequisit falla. En aquest sistema mínim sempre
    és el mateix, però mantenim la signatura per claredat arquitectònica.
    """
    user_msg = f"""
Pas: {step['text']}
Resposta errònia: {student_answer}
Dependència del problema: param_vs_stat — distinció paràmetre/estadístic.

Quina dependència falta?
""".strip()
    try:
        raw = _call(_SYSTEM_DIAG, user_msg, json_mode=True, max_tokens=150)
        data = _parse_json(raw)
        dep_id = data.get("dep_id")
    except Exception:
        dep_id = None
    # Defensiu: si la IA es lia, retornem la dependència del problema.
    if dep_id not in PB.DEPENDENCIES:
        dep_id = PB.PROBLEM["dependencies"][0]
    return dep_id


def generate_hint(step: dict, dep_id: str) -> str:
    """Pista socràtica curta per al pas actual."""
    dep = PB.DEPENDENCIES.get(dep_id, {})
    dep_desc = dep.get("description", dep_id)
    user_msg = f"""
L'alumne coneix el concepte: "{dep_desc}".
Pas on s'ha bloquejat: {step['text']}

Dona-li una pista socràtica.
""".strip()
    try:
        return _call(_SYSTEM_HINT, user_msg, json_mode=False,
                     max_tokens=200, temperature=0.4).strip()
    except Exception as e:
        return f"(No s'ha pogut generar la pista: {e})"
