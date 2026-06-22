# Changelog

Registre concís dels canvis significatius del sistema, en ordre
cronològic invers. El detall tècnic de cada fase viu als documents
referenciats.

## 2026-06-22 — Supressió del problema CAUS-001 (correlació vs. causalitat)

S'elimina completament el problema CAUS-001 del sistema. El tutor torna
a oferir un sol problema, IC-001 (interpretació d'un interval de
confiança). L'arquitectura (Streamlit + capa LLM via API-key + registry
de problemes a `problem.py`) no canvia: el picker, la màquina d'estats i
el flux de prompt deriven dinàmicament del registry, així que treure una
entrada n'hi ha prou per fer desaparèixer el problema de tot el flux.

Canvis:

- **`problem.py`**: eliminat el bloc de dades sencer de CAUS-001
  (`_CAUS001_ERROR_CATALOG`, `_CAUS001_DEPENDENCIES`,
  `_CAUS001_PREREQUISITES`, `_CAUS001_PROBLEM`) i la seva entrada al
  registry `PROBLEMS`. `DEFAULT_PROBLEM_ID` torna a `"IC-001"`.
  Docstrings actualitzats. Les assercions d'invariants del mòdul
  continuen validant l'esquema en càrrega.
- **`prompts/tutor_system_v1.2_CAUS-001.md`**: fitxer eliminat.
- **`app.py`**: tret el bloc CSS del botó `pick_CAUS-001` i la
  referència del comentari de paginació.
- **`simulator.py`** i **`llm.py`**: nets els exemples d'ús, docstrings
  i el text de pista de reserva (ara genèric, no causal).
- **Tests**: `test_diagnostic.py` (construït íntegrament sobre CAUS-001)
  eliminat. A la resta de suites s'han reduït els bucles multi-problema
  a IC-001, normalitzat els tokens de reforç a `PRE-PARAM` i reescrit
  els stubs amb temàtica IC-001. Suite en verd: 232 tests a les tres
  suites principals (`test_tutor_turn` 74, `test_simulator_state` 79,
  `test_app` 79), més `test_enrichment`, `test_enunciat_length` i
  `test_cortesia`.
- **`README.md`**: actualitzat a un sol problema (intro, característiques,
  CLI, secció de selecció, taula de fitxers, arquitectura, recomptes de
  tests).

Nota sobre aquest changelog: les entrades dedicades íntegrament a
CAUS-001 (la introducció del tema i el picker multi-problema, del
2026-05-25) s'han retirat, i les mencions disperses a CAUS-001 dins
d'altres entrades s'han reformulat perquè el registre quedi coherent
amb un sistema d'un sol problema. Aquesta entrada és l'únic lloc on
es documenta, deliberadament, que CAUS-001 va existir i es va suprimir.

## 2026-05-29 — Paginació de bombolles llargues ("Continuar")

Millora d'UI/UX: les bombolles del tutor massa llargues per a una sola
viewport (sobretot les obertures de problema i els passos amb
subapartats) ara es revelen per parts. Es mostra la primera subpantalla
i un botó **"Continuar (N més) ↓"**; en prémer-lo s'afegeix la part
següent en una targeta nova **sense esborrar les anteriors**. Quan no
queden parts, el botó desapareix.

És purament de presentació (`app.py`): `paginate_text` parteix el text
en pàgines pels salts de paràgraf que ja hi ha, sense partir mai un
paràgraf pel mig i preferint tallar just abans d'un bloc que obre secció
(dades, preguntes). El comptador de pàgines revelades viu a
`st.session_state` amb una clau estable per bombolla; **no es toca cap
dada, ni el `transcript`, ni el context del model, ni la màquina
d'estats** — el model i la IA continuen veient el text sencer. Els
textos curts (enunciats breus, pistes) es mostren d'un sol cop, sense
botó. Tests nous a `test_app.py` (paginació). Total: 238 tests en verd.

## 2026-05-29 — Revisió de textos deterministes (lectura humana)

Reescriptura per part del docent de 15 de les frases que Python escriu
de manera determinista a l'alumne (enunciats, texts de pas, preguntes
canòniques, pistes, pregunta i explicació dels reforços), a `problem.py`.
Es forcen salts de línia per millorar la llegibilitat a l'app. No canvia
cap lògica ni cap test (232 en verd). En els tres passos d'IC-001, el
text complet del pas i la pregunta canònica passen a ser idèntics, de
manera que l'enunciat que es veu en entrar al pas i el que Python
reinjecta en avançar-hi coincideixen exactament.

## 2026-05-28 — Transvasament d'arquitectura des de tutor-div (Python posa la pregunta)

Backport de tres patrons del projecte germà `tutor-div` que feien la
seva interacció més natural i fiable, sense canviar el contingut
pedagògic ni el nombre de passos.

**Tier 1 — Python garanteix la pregunta canònica (canvi de fons).**
Abans, en avançar de pas, el model havia de redactar ell mateix
l'enunciat del pas següent i mantenir la coherència entre l'`action`
del control block i el text del reply; això es domava amb dues seccions
llargues i fràgils del system prompt ("Format obligatori del reply quan
avances" i "Regla absoluta de coherència entre `action` i contingut").
Ara `simulator.apply_action` retorna un codi de transició i
`simulator.enrich_after_transition` injecta de manera **determinista**
la pregunta canònica del pas nou (o del reforç, en retrocedir) com a
bombolla pròpia, també enganxada al transcript perquè el model la vegi.
Variant "xarxa de seguretat", no la dura: el model encara pot fer una
transició conversacional, i hi ha anti-duplicació si ja ha escrit la
pregunta. Les dues seccions fràgils del prompt s'han eliminat del
fitxer del system prompt. Camps nous `canonical_question` per pas a
`problem.py` + accessors `canonical_question`/`step_hints`/
`prereq_question`.

**Tier 2 — doble codi de colors (acció pedagògica + origen).** El
registre nou `state["display"]` etiqueta cada bombolla amb el seu
`source` (`py` determinista / `ai` heurística / `student`). La UI
(`app.py`) afegeix un xip 🐍 Python / 🤖 IA i una targeta determinista
diferenciada, mantenint intacte el color d'acció existent (verd/groc/
gris). Fa visible, per a una audiència de mètodes, la combinació de
control determinista i generació estocàstica en un mateix sistema.

**Tier 3 — pistes pre-escrites i mode de reserva.** Cada pas porta ara
2 pistes progressives (`pistes`) a `problem.py`. `llm.py` guanya
`ia_disponible()` i un `_fallback_turn` heurístic per paraules clau:
si l'API no està disponible (clau absent o caiguda), l'app no peta —
degrada a un tutor mínim, útil com a salvavides per a una demo en
directe. `app.py` mostra l'estat de la IA (connectada / mode reserva).

Tests nous a `test_enrichment.py` (37 casos: codis de transició,
injecció canònica, anti-duplicació, display/source, fallback). Total
de la suite: 232 tests en verd (195 previs intactes + 37 nous).

## 2026-05-25 — Registry de problemes (arquitectura multi-problema)

`problem.py` deixa de ser single-problem i passa a exposar un registry
`PROBLEMS` indexat per id, on cada entrada conté el bundle complet
(`problem`, `prerequisites`, `dependencies`, `error_catalog`,
`prereq_id`, `title_human`). Funcions noves: `get(problem_id)` i
`list_ids()`. Els noms globals heretats (`PROBLEM`, `PREREQUISITES`,
etc.) segueixen existint apuntant al problema per defecte
(`DEFAULT_PROBLEM_ID`) només per back-compat amb tests. Assercions
d'integritat en càrrega del mòdul detecten errors d'esquema a la base
de dades pedagògica.

La resta del sistema en deriva tot, sense lògica acoblada a cap
problema concret:

- **`llm.py::_load_system_prompt(problem)`** accepta el problema com a
  paràmetre i carrega el fitxer corresponent
  (`prompts/tutor_system_<version>_<problem_id>.md`), amb cache per
  `problem["id"]`. `_format_position_marker` accepta `total_steps`,
  calculat de `problem["passos"]`.
- **`simulator.py`**: `new_session(problem_id)` i `run_session`
  accepten el problema; el prereq es llegeix de l'estat
  (`_prereq_id_for(state)`). Picker interactiu i flag CLI `--problem`.
- **`app.py`**: pantalla inicial amb un picker que es construeix a
  partir de `list_ids()`; títol de pàgina dinàmic; `tutor_turn` rep el
  bundle del problema actiu.
- **Prompts**: el system prompt es vincula per id de problema, via
  convenció de nom de fitxer.

Aquesta és la base que, més endavant, permet afegir o retirar problemes
tocant només el registry. (En aquell moment el registry contenia dos
problemes; el segon es va suprimir el 2026-06-22 — vegeu l'entrada del
capdamunt.)

## 2026-05-24 — Pas 3b-bis: presentació separada de la lògica

- L'etiqueta visual "Pregunta." es passa al renderer (app.py
  `render_tutor_card`) com a element CSS separat. Es treuen del prompt
  les instruccions de format que la requerien.
- El prompt v1.2 manté la "Regla absoluta de coherència entre `action`
  i contingut" per atacar el bug d'inconsistència del model.
- `simulator.py new_session` deixa l'opening net (només enunciat +
  pregunta del pas 1).
- Decisió arquitectònica: la presentació del format és responsabilitat
  de Python, no del model. Vegeu `prompts/tutor_system_v1.2.md`.

## 2026-05-24 — Pas 3b: Streamlit UI

- Nou `app.py` amb UI friendly: targeta del tutor colorada per acció,
  capçalera persistent amb l'enunciat (després eliminada), viewport
  net (sense scrollback de conversa).
- Colors semàntics: verd (advance net) · groc (advance amb stays
  previs o retreat al reforç) · gris (stay, tutoria en curs) ·
  bordeus (heurística de vacil·lar).
- Resum visual al final amb `quality_signals`: mètriques top,
  distribució de torns per pas amb barres, comptatge d'accions,
  expander de transcripció completa.
- Nous tests a `test_app.py` (32 tests).
- Iteracions UI: títol simplificat ("Tutoria (intervals de
  confiança)"), font reduïda −10%, marge superior reduït amb override
  agressiu del chrome de Streamlit, ampliació del text del Pas 1.

## 2026-05-24 — `quality_signals` al rastre

- Nou bloc `state["quality_signals"]` calculat al final de cada sessió
  (`simulator.compute_quality_signals`): ràtio stay/advance,
  distribució de torns per pas, ús de reforç, sol·licituds de pista,
  falles de parse del control block, durada total i mitjana per torn.
- Bug fix col·lateral: `elapsed_seconds_total` ara es calcula des de
  `history[-1].ts - started_at` en comptes de `time.time() -
  started_at`, evitant durades absurdes al re-processar JSONs antics.

## 2026-05-24 — Defenses contra el bug del transcript

(Aplicades per l'usuari del projecte després de detectar la classe de
fallada.)

- **Bug original**: `simulator.py` afegia el resultat de `tutor_turn`
  a `state["history"]` però **no** a `state["transcript"]`. Cada
  crida posterior enviava a Gemini un transcript de la forma
  `[opening, student_1, student_2, ...]` sense els torns del tutor.
  El model literalment no podia veure cap dels seus propis missatges
  anteriors. Tot el comportament erràtic observat fins llavors
  (repetició de preguntes, pèrdua de context, falles de parse) era
  conseqüència d'aquest bug d'integració.
- **Fixes**:
  - Append explícit al transcript (la línia que faltava).
  - Validació d'invariant a `llm.tutor_turn`: ValueError si el
    transcript no alterna user/model.
  - `MAX_OUTPUT_TOKENS` pujat de 800 a 1500 amb comentari documentant
    el comportament de Gemini 2.5 Flash (els thinking tokens compten
    contra el pressupost; quan el model està confús consumeix
    centenars de tokens pensant abans de produir text visible, i la
    resposta es truncava per davant del separador `---CONTROL---`).
- Nous tests T17/T18 a `test_tutor_turn.py` que lock-in la invariant.
- Lliçó general registrada: els 102 tests previs verds passaven les
  mecàniques de cada component aïllat però mai validaven el contracte
  d'integració entre simulator i llm.

## 2026-05-23/24 — Pas 3a: simulador CLI

- Nou `simulator.py` per a iteració ràpida sense necessitat de
  Streamlit. Loop interactiu, comandes `?`, `!!`, `/state`, `/raw`,
  `/save`, `/debug`.
- Estat compartit (`new_session`, `apply_action`, `position_dict`)
  per ser reutilitzat per l'app Streamlit.

## 2026-05-23 — Pas 2: implementació del tutor conversacional

- Nou `llm.py` amb una sola funció pública `tutor_turn(problem,
  current_position, transcript)` que fa una crida multi-turn a Gemini
  i retorna `{reply, action, objectives_met, ...}`.
- Format de sortida: text natural + separador `---CONTROL---` + JSON.
- System prompt extern a `prompts/tutor_system_v1.md` amb placeholders
  `{{...}}` que s'interpolen amb dades de `problem.py`.
- 39 tests inicials a `test_tutor_turn.py`, més tard ampliats fins als
  71 actuals.

### Iteracions de prompt (mateix dia)

- **v1.1**: afegit marcador de posició al darrer missatge user
  (`[Posició actual: Pas N de 3]`) després de detectar que el model
  perdia la pista de quin pas estava actiu. Afegida secció de senyals
  d'abandonament i reforç del `retreat_to_prereq`.
- **v1.2**: el marker es va passar a format directiu (`[Pas N de 3.
  L'alumne respon a la teva pregunta del Pas N. Jutja: tanca
  (advance) o continua (stay).]`) i la secció Marcador es va
  reescriure amb procediment de 3 passos numerats. Posteriorment es
  va reverter el format directiu del marker (un cop el bug del
  transcript estava resolt, el format simple bastava); s'ha mantingut
  la subsecció "Regla absoluta de coherència entre `action` i
  contingut" que ataca el bug d'inconsistència acció/contingut del
  model.

## 2026-05-23 — Pas 1: disseny de l'arquitectura conversacional

- RFC complet a `DESIGN_NIVELL1.md` (no inclòs al repo;
  internament a la conversa de disseny).
- Decisió: una crida per torn, transcript real com a context, control
  block JSON per a la decisió d'estat.
- Eliminació de l'eval de snapshots; substitució prevista per
  trajectòries (no implementada encara).

## 2026-05-23 — Abandonament de la sèrie de sofisticació

Després d'executar el sistema sofisticat (Propostes 1-5, vegeu
`CHANGELOG_SOFISTICACIO.md`) en una sessió real, s'observa que el
sistema **fa pitjor que un chatbot genèric**: rebutja com a
`typical_error` respostes correctes que usen llenguatge construït en
la conversa. Diagnòstic: la classificació per torn aïllat trenca la
continuïtat conversacional. Es desestima la sèrie de canvis 1-5 i es
decideix un redisseny estructural.

## 2026-05-23 — Sèrie de sofisticació (abandonada)

Implementació de cinc propostes sobre l'arquitectura de tres
classificadors (`judge_step`, `judge_prereq`, `generate_hint`):

1. Reforç amb judge LLM + segon intent
2. Generador de pistes ben alimentat amb context d'error
3. Judge stateful amb trajectòria
4. Self-consistency selectiva amb resample en confiança baixa
5. Eliminació de `diagnose_dependency` (codi mort)

Detall tècnic complet a `CHANGELOG_SOFISTICACIO.md` (document
històric, no vigent).

## ~2026-05-22 — Estat inicial del projecte

- Arquitectura de tres classificadors LLM amb regla d'auto-suficiència
  estricta (cada resposta es classifica aïllada).
- Eval framework de 30 casos a `eval_cases.py` + `eval_runner.py`
  (avui a `archive/pre-conversational/`).
- Detall tècnic a `PROJECT_LOG.md` (document històric, no vigent).
