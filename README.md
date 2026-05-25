# Tutor IC — tutor conversacional d'intervals de confiança

Tutor socràtic mínim per a la interpretació d'un interval de confiança
del 95%. Pensat per a una demo en directe de ~20 minuts. Una única
crida al model per cada torn de conversa; sense classificadors
intermedis.

## Característiques

- **Un sol problema** (IC-001): interpretació de l'interval [3,2 ; 4,8].
- **Tres passos** Socràtics que escalen fins a la formulació correcta.
- **Un reforç** (PRE-PARAM): distinció paràmetre / estadístic.
- **Una crida a Gemini per torn** (`tutor_turn`), amb multi-turn API i
  marcador de posició al darrer missatge user.
- **Format de sortida del model**: text natural per a l'alumne +
  separador `---CONTROL---` + JSON `{action, objectives_met}`.
- Senyals UI: `💡 Pista` (botó), `🚪 Acabar` (botó). A CLI: `?` i `!!`.
- Rastre JSON complet al final amb bloc `quality_signals` (ràtio
  stay/advance, distribució per pas, ús de reforç, falles de parse,
  durada, etc.).
- **172 tests** repartits en tres suites: `test_tutor_turn.py`,
  `test_simulator_state.py`, `test_app.py`.

## Instal·lació

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...   # clau gratuïta a https://aistudio.google.com/apikey
streamlit run app.py
```

També hi ha un simulador CLI per a iteració ràpida del prompt sense UI:

```bash
python3 simulator.py --debug --save sessio.json
```

(Opcional) Canviar el model:
```bash
export GEMINI_MODEL=gemini-2.5-flash   # default, recomanat per a la demo
# export GEMINI_MODEL=gemini-2.5-pro   # més qualitat, més car
```

## Demo planificada (~20 minuts)

### Sessió A — "alumne que raona bé"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | Si repetíssim el mateix procés de mostreig moltes vegades, el 95% dels intervals construïts contindrien la veritable mitjana poblacional (μ). |
| 2 | μ és un valor fix (desconegut), no aleatori. No té probabilitat d'estar o no estar en cap lloc. |
| 3 | Tenim una confiança del 95% que μ estigui dins de [3,2; 4,8], on "confiança" vol dir fiabilitat a llarg termini del procediment. |

Resultat esperat: tres `action="advance"` consecutius, sessió
completada en 3-4 torns LLM, ratio `stay/advance` ≈ 0.

### Sessió B — "alumne amb la confusió clàssica"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | Hi ha un 95% de probabilitat que μ estigui entre 3,2 i 4,8. |
| 1 (resposta a la insistència socràtica) | μ és un valor fix... no entenc bé què vols dir. |
| (eventualment dins el reforç) | μ és la mitjana real de la població, és fixa però no la sabem; x̄ canvia segons la mostra. |
| 1 (segon intent) | Aleshores el 95% es refereix al procediment, no a aquest interval concret. |

Resultat esperat: 1-2 `stay` al Pas 1, eventualment
`retreat_to_prereq` → reforç → `advance` de tornada a Pas 1 → tres
`advance` fins a `finished`. Ràtio `stay/advance` típica al voltant
de 1.5-3. El bloc `quality_signals` del JSON final mostra
`used_prereq: true`.

## Cost

Gemini Flash. Cada sessió completa fa entre 3 i 18 crides totals,
~3 000-15 000 tokens en total per sessió segons la dificultat. Cost
estimat: menys d'1 cèntim per sessió. Pots fer 20 minuts de demo amb
la quota gratuïta sense apropar-te al límit.

## Fitxers principals

| Fitxer | Què fa |
|---|---|
| `problem.py` | El problema, els passos, el prerequisit, errors típics. Mateixa estructura que les versions anteriors. |
| `prompts/tutor_system_v1.2.md` | System prompt actual del tutor. Versió viva. Les versions `v1.md` i `v1.1.md` queden per comparació històrica. |
| `llm.py` | Una funció pública: `tutor_turn(problem, current_position, transcript)`. Resol el system prompt amb placeholders, fa una crida multi-turn a Gemini, parseja la resposta. |
| `simulator.py` | Estat de sessió (`new_session`, `apply_action`, `compute_quality_signals`, `format_quality_signals`). Loop CLI a `run_session`. Compartit amb l'app Streamlit. |
| `app.py` | UI Streamlit: targeta del tutor colorada segons l'acció, viewport net (sense scrollback), resum visual al final amb mètriques i barres per pas. |
| `test_tutor_turn.py` | 71 tests de les mecàniques de `tutor_turn` (parse, control block, transcript invariants). |
| `test_simulator_state.py` | 69 tests de la màquina d'estats i el bloc quality_signals. |
| `test_app.py` | 32 tests dels helpers de l'app (color logic, heurística de vacil·lar, markdown→HTML). |
| `requirements.txt` | Dependències (Streamlit + google-genai). |

## Arquitectura — el que cal saber

Si vens d'una versió anterior, els tres canvis estructurals més
importants són:

1. **Una crida per torn**, no tres. Va haver-hi una fase amb tres
   classificadors (`judge_step`, `judge_prereq`, `generate_hint`) que
   es va abandonar. Veure `PROJECT_LOG.md` i `CHANGELOG_SOFISTICACIO.md`
   per al registre històric d'aquella fase, i `CHANGELOG.md` per a la
   transició.

2. **El model rep la conversa completa** com a multi-turn `contents`
   de Gemini, no un text agregat. El darrer missatge user porta un
   marcador `[Posició actual: ...]` que actua com a font de veritat
   sobre quin pas està actiu.

3. **El control flow viu a Python**. El model retorna `action ∈
   {stay, advance, retreat_to_prereq}` al control block; Python
   manté l'estat (`current_step`, `active_prereq`,
   `step_before_prereq`, `finished`) i aplica les transicions.

## Què NO té (intencionalment)

- Sense persistència a disc (la sessió es perd quan es tanca la pestanya).
- Sense pseudonimització ni RGPD (no és per a un pilot amb alumnes reals).
- Sense bilingüisme (només català).
- Sense DAG, sense profunditat de retrocés > 1, sense detecció de mal ús.
- Sense `!text` (la discrepància es resol conversacionalment ara).

Per a qualsevol d'aquestes coses, mira els projectes germans `tutor-eq`
i `tutor-grups`.

## Tests

```bash
python3 test_tutor_turn.py        # 71 tests, ~1s
python3 test_simulator_state.py   # 69 tests, ~1s
python3 test_app.py               # 32 tests, ~1s
```

Cap dels tres requereix clau Gemini — tots stubben les crides al
model. Per a tests d'integració amb el model real, usar el simulador
CLI amb el flag `--save` i revisar el JSON manualment.
