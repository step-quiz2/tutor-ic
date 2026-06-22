# Tutor IC — tutor conversacional d'estadística

Tutor socràtic mínim per a temes d'interpretació estadística. Actualment
ofereix un problema:

- **IC-001** — interpretació d'un interval de confiança del 95%.

Pensat per a una demo en directe de ~20 minuts. Una única crida al
model per cada torn de conversa; sense classificadors intermedis.

## Característiques

- **Problema treballat**: IC-001, presentat a l'inici de la sessió via
  picker (UI Streamlit) o `--problem` (CLI).
- **Tres passos Socràtics**, escalonats fins a la formulació correcta.
  IC-001 treballa la interpretació de l'IC del 95%.
- **Un reforç**: PRE-PARAM (paràmetre vs. estadístic) per a IC-001.
- **Una crida a Gemini per torn** (`tutor_turn`), amb multi-turn API i
  marcador de posició al darrer missatge user.
- **Python posa la pregunta de cada pas** (determinista). En avançar o
  retrocedir, és el codi qui injecta l'enunciat canònic del pas/reforç
  com a bombolla pròpia, no el model. Això elimina la classe de bugs de
  desincronització `action`/text i permet un system prompt més prim.
- **Doble codi de colors**: el color de fons codifica l'acció
  pedagògica (verd avança · groc avança amb dubtes/reforç · gris es
  queda) i un xip indica l'origen de cada bombolla (🐍 Python
  determinista · 🤖 IA heurística).
- **Pistes pre-escrites** per pas (2 progressives) i **mode de reserva**
  sense IA (heurística per paraules clau): si l'API cau durant una demo,
  l'app degrada en lloc de petar.
- **Format de sortida del model**: text natural per a l'alumne +
  separador `---CONTROL---` + JSON `{action, objectives_met}`.
- Senyals UI: `💡 Pista` (botó), `🚪 Acabar` (botó). A CLI: `?` i `!!`.
- Rastre JSON complet al final amb bloc `quality_signals` (ràtio
  stay/advance, distribució per pas, ús de reforç, falles de parse,
  durada, etc.).
- **232 tests** repartits en tres suites: `test_tutor_turn.py` (74),
  `test_simulator_state.py` (79), `test_app.py` (79). Inclouen tests
  específics del registry de problemes.

## Instal·lació

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...   # clau gratuïta a https://aistudio.google.com/apikey
streamlit run app.py
```

També hi ha un simulador CLI per a iteració ràpida del prompt sense UI:

```bash
# Picker interactiu (defecte)
python3 simulator.py --debug --save sessio.json

# Saltant el picker, problema directe
python3 simulator.py --problem IC-001 --debug
```

(Opcional) Canviar el model:
```bash
export GEMINI_MODEL=gemini-2.5-flash   # default, recomanat per a la demo
# export GEMINI_MODEL=gemini-2.5-pro   # més qualitat, més car
```

## Selecció de problema

Actualment hi ha un sol problema (IC-001), que el picker obre a l'inici
de la sessió. El registry està pensat per allotjar-ne més: afegir una
entrada a `PROBLEMS` tornaria a mostrar la tria. Per disseny, el
problema no es pot canviar a mitja sessió (cal recarregar la pàgina o
re-executar el simulador), perquè barrejar problemes embolicaria el
rastre i el reforç.

A nivell de codi, el problema actiu viu a `state["problem_id"]` i la
resta del flux en deriva tot: el system prompt (per-problema), el
prereq que activa `retreat_to_prereq`, el nombre de passos, el text
de l'enunciat. Per back-compat, qualsevol codi que segueixi accedint
a `PB.PROBLEM` veu el problema per defecte (IC-001) — cap
import-time error, però el flux requereix passar
explícitament `problem_id` a `new_session()` i el bundle a
`tutor_turn()`.

## Demos planificades (~20 minuts cadascuna)

### Demo IC-001 — interval de confiança

#### Sessió A — "alumne que raona bé"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | Si repetíssim el mateix procés de mostreig moltes vegades, el 95% dels intervals construïts contindrien la veritable mitjana poblacional (μ). |
| 2 | μ és un valor fix (desconegut), no aleatori. No té probabilitat d'estar o no estar en cap lloc. |
| 3 | Tenim una confiança del 95% que μ estigui dins de [3,2; 4,8], on "confiança" vol dir fiabilitat a llarg termini del procediment. |

Resultat esperat: tres `action="advance"` consecutius, sessió
completada en 3-4 torns LLM, ratio `stay/advance` ≈ 0.

#### Sessió B — "alumne amb la confusió clàssica"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | Hi ha un 95% de probabilitat que μ estigui entre 3,2 i 4,8. |
| 1 (resposta a la insistència socràtica) | μ és un valor fix... no entenc bé què vols dir. |
| (eventualment dins el reforç) | μ és la mitjana real de la població, és fixa però no la sabem; x̄ canvia segons la mostra. |
| 1 (segon intent) | Aleshores el 95% es refereix al procediment, no a aquest interval concret. |

Resultat esperat: 1-2 `stay` al Pas 1, eventualment
`retreat_to_prereq` → reforç → `advance` de tornada a Pas 1 → tres
`advance` fins a `finished`.

## Cost

Gemini Flash. Cada sessió completa fa entre 3 i 18 crides totals,
~3 000-15 000 tokens en total per sessió segons la dificultat. Cost
estimat: menys d'1 cèntim per sessió. Pots fer 20 minuts de demo amb
la quota gratuïta sense apropar-te al límit.

## Fitxers principals

| Fitxer | Què fa |
|---|---|
| `problem.py` | Registry dels problemes (`PROBLEMS`, `get`, `list_ids`), més noms globals (`PROBLEM`, `PREREQUISITES`, ...) apuntant al per defecte per back-compat. |
| `prompts/tutor_system_v1.2_IC-001.md` | System prompt per al problema IC-001 (interval de confiança). |
| `llm.py` | Una funció pública: `tutor_turn(problem, current_position, transcript)`. Càrrega el prompt corresponent a `problem["id"]` amb cache per problema. |
| `simulator.py` | Estat de sessió (`new_session(problem_id)`, `apply_action`, `compute_quality_signals`). Loop CLI a `run_session` amb picker interactiu o flag `--problem`. |
| `app.py` | UI Streamlit: pantalla inicial de selecció de problema; targeta del tutor colorada per acció, viewport net, resum visual al final. |
| `test_tutor_turn.py` | 74 tests de les mecàniques de `tutor_turn` (parse, control block, transcript invariants, càrrega del prompt per problema). |
| `test_simulator_state.py` | 79 tests de la màquina d'estats, quality_signals, i el registry de problemes. |
| `test_app.py` | 79 tests dels helpers de l'app (color logic, heurística de vacil·lar, markdown→HTML). |
| `requirements.txt` | Dependències (Streamlit + google-genai). |

## Arquitectura — el que cal saber

Si vens d'una versió anterior, els canvis estructurals més rellevants
són:

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

4. **Problemes via registry**. `problem.py` exposa
   `PROBLEMS = {"IC-001": {...}}` i les funcions
   `get(problem_id)` / `list_ids()`. L'estat de sessió porta
   `problem_id`; tots els consumidors (state machine, càrrega de
   prompt, marcador de posició) en deriven la informació concreta.
   `PB.PROBLEM` (i companys) segueix existint apuntant al problema
   per defecte (IC-001), només per a back-compat amb tests. El registry
   és extensible: afegir una entrada nova reactivaria el picker
   automàticament.

## Què NO té (intencionalment)

- Sense persistència a disc (la sessió es perd quan es tanca la pestanya).
- Sense pseudonimització ni RGPD (no és per a un pilot amb alumnes reals).
- Sense bilingüisme (només català).
- Sense DAG, sense profunditat de retrocés > 1, sense detecció de mal ús.
- Sense canvi de problema a mitja sessió (per canviar, recarrega).
- Sense `!text` (la discrepància es resol conversacionalment ara).

Per a qualsevol d'aquestes coses, mira els projectes germans `tutor-eq`
i `tutor-grups`.

## Tests

```bash
python3 test_tutor_turn.py        # 74 tests, ~1s
python3 test_simulator_state.py   # 79 tests, ~1s
python3 test_app.py               # 79 tests, ~1s
```

Cap dels tres requereix clau Gemini — tots stubben les crides al
model. Per a tests d'integració amb el model real, usar el simulador
CLI amb el flag `--save` i revisar el JSON manualment.
