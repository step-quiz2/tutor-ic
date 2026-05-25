# Tutor IC — tutor conversacional d'estadística

Tutor socràtic mínim per a temes d'interpretació estadística. Actualment
ofereix dos problemes a triar per l'alumne a l'inici de la sessió:

- **IC-001** — interpretació d'un interval de confiança del 95%.
- **CAUS-001** — interpretació d'una correlació observada (correlació
  vs. causalitat).

Pensat per a una demo en directe de ~20 minuts. Una única crida al
model per cada torn de conversa; sense classificadors intermedis.

## Característiques

- **Dos problemes seleccionables** (IC-001 i CAUS-001), tria a l'inici
  de la sessió via picker (UI Streamlit) o `--problem` (CLI).
- **Tres passos Socràtics** per problema, escalonats fins a la
  formulació correcta. IC-001 treballa la interpretació de l'IC del
  95%; CAUS-001 treballa la lectura crítica d'una diferència de taxes
  real (abandonament escolar prematur per origen migrat, dades de
  l'Idescat i la Fundació Bofill).
- **Un reforç per problema**: PRE-PARAM (paràmetre vs. estadístic) per
  a IC-001; PRE-CONFOUNDER (variable confusora) per a CAUS-001.
- **Una crida a Gemini per torn** (`tutor_turn`), amb multi-turn API i
  marcador de posició al darrer missatge user.
- **Format de sortida del model**: text natural per a l'alumne +
  separador `---CONTROL---` + JSON `{action, objectives_met}`.
- Senyals UI: `💡 Pista` (botó), `🚪 Acabar` (botó). A CLI: `?` i `!!`.
- Rastre JSON complet al final amb bloc `quality_signals` (ràtio
  stay/advance, distribució per pas, ús de reforç, falles de parse,
  durada, etc.).
- **195 tests** repartits en tres suites: `test_tutor_turn.py` (77),
  `test_simulator_state.py` (86), `test_app.py` (32). Inclouen tests
  específics del registry multi-problema.

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
python3 simulator.py --problem CAUS-001 --debug
```

(Opcional) Canviar el model:
```bash
export GEMINI_MODEL=gemini-2.5-flash   # default, recomanat per a la demo
# export GEMINI_MODEL=gemini-2.5-pro   # més qualitat, més car
```

## Selecció de problema

L'alumne tria a l'inici quin problema treballarà. La selecció és per
sessió: per canviar de problema cal recarregar la pàgina (UI) o
re-executar el simulador (CLI). Aquesta restricció és intencional —
barrejar problemes a mitja sessió embolicaria el rastre i el reforç.

A nivell de codi, el problema actiu viu a `state["problem_id"]` i la
resta del flux en deriva tot: el system prompt (per-problema), el
prereq que activa `retreat_to_prereq`, el nombre de passos, el text
de l'enunciat. Per back-compat, qualsevol codi que segueixi accedint
a `PB.PROBLEM` veu el problema per defecte (CAUS-001) — cap
import-time error, però el flux multi-problema requereix passar
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

### Demo CAUS-001 — correlació vs. causalitat

Tema: lectura crítica d'una diferència de taxes real publicada per
l'**Idescat** (Enquesta de Població Activa, 2022-2023): l'abandonament
escolar prematur entre joves de 18-24 anys és del 34,2% per a joves
de nacionalitat estrangera vs 10,1% per als nascuts a Catalunya.
L'objectiu pedagògic és que l'alumne identifiqui per què aquesta
diferència NO autoritza la lectura "l'origen migrat causa
l'abandonament", reconegui el feix de variables confusores
(nivell socioeconòmic, educació dels pares, segregació escolar,
llengua, racisme institucional), i sàpiga proposar evidència de
qualitat causal (control estadístic dels confusors; quasi-experiments
com l'estudi del Centre d'Estudis Demogràfics).

#### Sessió A — "alumne que raona bé"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | Una diferència de taxes és una associació observada, no un mecanisme. Que els dos grups tinguin resultats diferents en l'abandonament no diu res sobre què causa aquesta diferència. Els dos grups difereixen també en moltes altres variables — nivell socioeconòmic, educació dels pares, recursos escolars — que afecten l'AEP. La diferència observada pot venir d'aquestes altres variables i no de l'origen mateix. |
| 2 | L'alternativa dominant aquí són les variables confusores, no una sola sinó tot un feix entrellaçat: el nivell socioeconòmic familiar, el nivell educatiu dels pares (segons la Fundació Bofill, fins a 5× més AEP entre joves amb pares amb estudis baixos), la segregació escolar, la competència en la llengua vehicular i la discriminació institucional. També hi ha una component de selecció migratòria. La causalitat inversa aquí no s'aplica (abandonar estudis no et fa migrar) i l'atzar mostral és irrellevant donada la mida de la població. |
| 3 | L'experiment aleatoritzat aquí és impossible — no es pot assignar l'origen. La via és el control estadístic dels confusors: comparar AEP entre joves d'origen migrat i nascuts a Catalunya dins de cada nivell socioeconòmic, dins de cada nivell d'educació dels pares, dins de cada zona territorial. Si les diferències es redueixen quan es controla, és confusió, no causa. Una evidència quasi-experimental potent: l'estudi del Centre d'Estudis Demogràfics que compara fills d'estrangers nascuts a Catalunya (21,2% no acaben ESO) amb fills d'estrangers arribats abans dels 7 anys (21,7%) — taxes pràcticament idèntiques. |

Resultat esperat: tres `action="advance"` consecutius, sessió
completada en 3-4 torns LLM, ratio `stay/advance` ≈ 0.

#### Sessió B — "alumne amb la confusió clàssica"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | És evident: si abandonen tant més, és perquè ser d'origen migrat fa més difícil acabar els estudis. La diferència és tres vegades més gran, està claríssim. |
| 1 (resposta al repte socràtic) | Però la diferència és claríssima, no entenc per què no podem dir que una cosa causa l'altra. |
| (eventualment dins el reforç) | La calor fa que hi hagi més hores de sol i que la gent compri més begudes fredes; la temperatura és la variable que causa les dues coses alhora, no hi ha cap relació directa entre el sol i les begudes. |
| 1 (segon intent) | Aleshores la diferència 34,2% vs 10,1% no vol dir que l'origen sigui la causa: podria ser que les famílies migrades tinguessin, de mitjana, condicions socioeconòmiques diferents, i que sigui això el que afecta els fills. |

Resultat esperat: 1-2 `stay` al Pas 1, eventualment
`retreat_to_prereq` → reforç → `advance` de tornada a Pas 1 → tres
`advance` fins a `finished`. El bloc `quality_signals` del JSON final
mostra `used_prereq: true`.

## Cost

Gemini Flash. Cada sessió completa fa entre 3 i 18 crides totals,
~3 000-15 000 tokens en total per sessió segons la dificultat. Cost
estimat: menys d'1 cèntim per sessió. Pots fer 20 minuts de demo amb
la quota gratuïta sense apropar-te al límit.

## Fitxers principals

| Fitxer | Què fa |
|---|---|
| `problem.py` | Registry dels dos problemes (`PROBLEMS`, `get`, `list_ids`), més noms globals (`PROBLEM`, `PREREQUISITES`, ...) apuntant al per defecte per back-compat. |
| `prompts/tutor_system_v1.2_IC-001.md` | System prompt per al problema IC-001 (interval de confiança). |
| `prompts/tutor_system_v1.2_CAUS-001.md` | System prompt per al problema CAUS-001 (correlació vs. causalitat). |
| `llm.py` | Una funció pública: `tutor_turn(problem, current_position, transcript)`. Càrrega el prompt corresponent a `problem["id"]` amb cache per problema. |
| `simulator.py` | Estat de sessió (`new_session(problem_id)`, `apply_action`, `compute_quality_signals`). Loop CLI a `run_session` amb picker interactiu o flag `--problem`. |
| `app.py` | UI Streamlit: pantalla inicial de selecció de problema; targeta del tutor colorada per acció, viewport net, resum visual al final. |
| `test_tutor_turn.py` | 77 tests de les mecàniques de `tutor_turn` (parse, control block, transcript invariants, càrrega del prompt per problema). |
| `test_simulator_state.py` | 86 tests de la màquina d'estats, quality_signals, i el registry multi-problema. |
| `test_app.py` | 32 tests dels helpers de l'app (color logic, heurística de vacil·lar, markdown→HTML). |
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

4. **Multi-problema via registry**. `problem.py` exposa
   `PROBLEMS = {"IC-001": {...}, "CAUS-001": {...}}` i les funcions
   `get(problem_id)` / `list_ids()`. L'estat de sessió porta
   `problem_id`; tots els consumidors (state machine, càrrega de
   prompt, marcador de posició) en deriven la informació concreta.
   `PB.PROBLEM` (i companys) segueix existint apuntant al problema
   per defecte (CAUS-001), només per a back-compat amb tests.

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
python3 test_tutor_turn.py        # 77 tests, ~1s
python3 test_simulator_state.py   # 86 tests, ~1s
python3 test_app.py               # 32 tests, ~1s
```

Cap dels tres requereix clau Gemini — tots stubben les crides al
model. Per a tests d'integració amb el model real, usar el simulador
CLI amb el flag `--save` i revisar el JSON manualment.
