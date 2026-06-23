# Tutor IC — tutor conversacional d'estadística

Tutor socràtic mínim per a temes d'inferència estadística. Actualment
ofereix dos problemes:

- **IC-001** — construcció i disseny d'un interval de confiança per a
  una **mitjana** (error estàndard, mida de mostra, biaix de selecció,
  nivell de confiança).
- **IC-002** — construcció d'un interval de confiança per a una
  **proporció** (variància lligada a p, biaix de selecció, nivell de
  confiança).

Tots dos comparteixen context (les hores de son dels adolescents) però
treballen arquitectures conceptuals diferents: IC-001 usa la
distribució *t* perquè estima σ amb una *s* mostral; IC-002 torna a la
*z* perquè la variància d'una proporció ja ve donada per p(1-p).

Pensat per a una demo en directe de ~20 minuts. Una única crida al
model per cada torn de conversa; sense classificadors intermedis.

## Característiques

- **Problemes treballats**: IC-001 i IC-002, presentats a l'inici de la
  sessió via picker (UI Streamlit) o `--problem` (CLI).
- **Tres passos Socràtics** per problema, escalonats fins a la
  comprensió correcta. IC-001 treballa construcció · biaix · confiança
  per a una mitjana; IC-002, els mateixos tres eixos per a una proporció.
- **Un reforç per problema**: PRE-SE (error estàndard, s/√n) per a
  IC-001; PRE-VARP (variància p(1-p), màxima a 0,5) per a IC-002.
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
- **Pistes pre-escrites** per pas (2 progressives, més pistes mapejades
  a codis d'error concrets) i **mode de reserva** sense IA (heurística
  per paraules clau): si l'API cau durant una demo, l'app degrada en
  lloc de petar.
- **Format de sortida del model**: text natural per a l'alumne +
  separador `---CONTROL---` + JSON `{action, objectives_met, diagnostic}`.
- Senyals UI: `💡 Pista` (botó), `🚪 Acabar` (botó). A CLI: `?` i `!!`.
- Rastre JSON complet al final amb bloc `quality_signals` (ràtio
  stay/advance, distribució per pas, ús de reforç, falles de parse,
  durada, etc.).
- **275 tests** repartits en sis suites: `test_tutor_turn.py` (74),
  `test_simulator_state.py` (83), `test_app.py` (79), `test_enrichment.py`
  (30), `test_cortesia.py` (6), `test_enunciat_length.py` (3). Inclouen
  tests específics del registry de problemes (ara amb dos problemes).

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
python3 simulator.py --problem IC-002 --debug
```

(Opcional) Canviar el model:
```bash
export GEMINI_MODEL=gemini-2.5-flash   # default, recomanat per a la demo
# export GEMINI_MODEL=gemini-2.5-pro   # més qualitat, més car
```

## Selecció de problema

Hi ha dos problemes (IC-001, mitjana; IC-002, proporció), que el picker
ofereix a l'inici de la sessió. El registry està pensat per allotjar-ne
més: afegir una entrada a `PROBLEMS` amb el seu prompt corresponent els
mostra al picker automàticament. Per disseny, el problema no es pot
canviar a mitja sessió (cal recarregar la pàgina o re-executar el
simulador), perquè barrejar problemes embolicaria el rastre i el reforç.

A nivell de codi, el problema actiu viu a `state["problem_id"]` i la
resta del flux en deriva tot: el system prompt (per-problema), el
prereq que activa `retreat_to_prereq`, el nombre de passos, el text
de l'enunciat. Per back-compat, qualsevol codi que segueixi accedint
a `PB.PROBLEM` veu el problema per defecte (IC-001) — cap
import-time error, però el flux requereix passar
explícitament `problem_id` a `new_session()` i el bundle a
`tutor_turn()`.

## Demos planificades (~20 minuts cadascuna)

### Demo IC-001 — interval de confiança per a una mitjana

#### Sessió A — "alumne que raona bé"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | El marge és petit perquè depèn de l'error estàndard s/√n, no de la dispersió de les dades. La mitjana de 100 persones és molt més estable que un individu; per això ±0,32 i no ±1,6. I el valor crític no és 1,96 sinó ≈1,984, perquè surt de la t amb 99 graus de llibertat (hem estimat σ amb s). |
| 2 | No seria de fiar: si l'enquesta es passa a la porta a les 8, en queden fora justament els que dormen poc. x̄ surt esbiaixada. Augmentar n a 5.000 estreny l'interval però no toca el centre: queda precís però descentrat. La n redueix la variància, no el biaix. |
| 3 | L'interval s'eixamplaria, perquè el valor crític creix (de ≈1,984 a ≈3,392). No demanem sempre el 99,9% perquè un interval massa ample deixa de ser informatiu: hi ha un trade-off entre fiabilitat i utilitat, i el 95% és el compromís habitual. |

Resultat esperat: tres `action="advance"` consecutius, sessió
completada en 3-4 torns LLM, ratio `stay/advance` ≈ 0.

#### Sessió B — "alumne amb la confusió clàssica"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | El marge hauria de ser d'1,6 aproximadament, que és la desviació de les dades. |
| 1 (resposta a la insistència socràtica) | Ah... però l'interval parla de la mitjana, no d'un individu. No sé bé com es relacionen. |
| (eventualment dins el reforç) | La mitjana de moltes persones es mou menys perquè els alts i baixos es compensen; la dispersió de la mitjana és s dividit per l'arrel de n. |
| 1 (segon intent) | Aleshores el marge surt de s/√n = 0,16, no d'1,6: per això ±0,32. |

Resultat esperat: 1-2 `stay` al Pas 1, eventualment
`retreat_to_prereq` → reforç PRE-SE → `advance` de tornada a Pas 1 →
tres `advance` fins a `finished`.

### Demo IC-002 — interval de confiança per a una proporció

#### Sessió A — "alumne que raona bé"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | Aquí no es mesura cap desviació a part: per a una variable sí/no la variància és p(1-p), i l'error estàndard és √(p(1-p)/n). Com que p(1-p) és màxima a 0,5 i petita als extrems, un p̂ del 90% donaria menys marge que el 45%. |
| 2 | No seria de fiar: a la porta a les 8 en falten justament els que dormen poc, que són els que compten per al "sí", així que el percentatge surt esbiaixat. Amb 5.000 al mateix lloc l'interval s'estreny però queda centrat al valor equivocat. La n no corregeix el biaix. |
| 3 | L'interval s'eixamplaria fins a omplir gairebé tot el rang. Amb mostra ridícula o un 99,99% pot arribar a [1%, 99%]: és cert (cap valor és impossible) però no diu res. Per això no demanem sempre el màxim de confiança. |

Resultat esperat: tres `action="advance"` consecutius, sessió
completada en 3-4 torns LLM.

#### Sessió B — "alumne amb la confusió clàssica"

| Pas | Resposta a copiar i enganxar |
|---|---|
| 1 | Però falta la desviació estàndard de les dades per calcular el marge, no? |
| 1 (resposta a la insistència socràtica) | És que com pot haver-hi dispersió si cada persona només diu sí o no? |
| (eventualment dins el reforç) | La variància d'una proporció és p(1-p): és màxima quan està partit per la meitat (0,5) i baixa cap als extrems. |
| 1 (segon intent) | Llavors no cal mesurar res a part: la dispersió surt sola de la proporció, i l'error estàndard és √(p(1-p)/n). |

Resultat esperat: 1-2 `stay` al Pas 1, eventualment
`retreat_to_prereq` → reforç PRE-VARP → `advance` de tornada a Pas 1 →
tres `advance` fins a `finished`.

## Cost

Gemini Flash. Cada sessió completa fa entre 3 i 18 crides totals,
~3 000-15 000 tokens en total per sessió segons la dificultat. Cost
estimat: menys d'1 cèntim per sessió. Pots fer 20 minuts de demo amb
la quota gratuïta sense apropar-te al límit.

## Fitxers principals

| Fitxer | Què fa |
|---|---|
| `problem.py` | Registry dels problemes (`PROBLEMS`, `get`, `list_ids`), més noms globals (`PROBLEM`, `PREREQUISITES`, ...) apuntant al per defecte per back-compat. Conté IC-001 (mitjana) i IC-002 (proporció). |
| `prompts/tutor_system_v1.2_IC-001.md` | System prompt per al problema IC-001 (interval de confiança per a una mitjana). |
| `prompts/tutor_system_v1.2_IC-002.md` | System prompt per al problema IC-002 (interval de confiança per a una proporció). |
| `llm.py` | Una funció pública: `tutor_turn(problem, current_position, transcript)`. Càrrega el prompt corresponent a `problem["id"]` amb cache per problema. |
| `simulator.py` | Estat de sessió (`new_session(problem_id)`, `apply_action`, `compute_quality_signals`). Loop CLI a `run_session` amb picker interactiu o flag `--problem`. |
| `app.py` | UI Streamlit: pantalla inicial de selecció de problema; targeta del tutor colorada per acció, viewport net, resum visual al final. |
| `test_tutor_turn.py` | 74 tests de les mecàniques de `tutor_turn` (parse, control block, transcript invariants, càrrega del prompt per problema). |
| `test_simulator_state.py` | 83 tests de la màquina d'estats, quality_signals, i el registry de problemes (dos problemes). |
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
   `PROBLEMS = {"IC-001": {...}, "IC-002": {...}}` i les funcions
   `get(problem_id)` / `list_ids()`. L'estat de sessió porta
   `problem_id`; tots els consumidors (state machine, càrrega de
   prompt, marcador de posició) en deriven la informació concreta.
   `PB.PROBLEM` (i companys) segueix existint apuntant al problema
   per defecte (IC-001), només per a back-compat amb tests. El registry
   és extensible: afegir una entrada nova (amb el seu fitxer de prompt)
   la mostra al picker automàticament.

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
python3 test_simulator_state.py   # 83 tests, ~1s
python3 test_app.py               # 79 tests, ~1s
python3 test_enrichment.py        # 30 tests, ~1s
python3 test_cortesia.py          #  6 tests, ~1s
python3 test_enunciat_length.py   #  3 tests, ~1s
```

Cap requereix clau Gemini — tots stubben les crides al model. Total:
**275 tests**. Per a tests d'integració amb el model real, usar el
simulador CLI amb el flag `--save` i revisar el JSON manualment.
