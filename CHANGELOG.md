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

Nota: les entrades anteriors d'aquest changelog que descriuen feina
sobre CAUS-001 es conserven com a registre històric del que va passar;
no es reescriuen.

## 2026-05-29 — Paginació de bombolles llargues ("Continuar")

Millora d'UI/UX: les bombolles del tutor massa llargues per a una sola
viewport (sobretot l'obertura de CAUS-001 i els passos 2 i 3, amb
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
pregunta. Les dues seccions fràgils del prompt s'han eliminat dels dos
fitxers (IC-001 i CAUS-001). Camps nous `canonical_question` per pas a
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

## 2026-05-25 — CAUS-001: nou contingut (origen migrat i AEP, dades Idescat/Bofill)

Substitució del contingut pedagògic del bundle CAUS-001 dins del
registry de problemes. L'arquitectura multi-problema no canvia; el
reforç (PRE-CONFOUNDER, sol/begudes fredes) no canvia; només es
reescriu el problema principal. IC-001 segueix intacte.

**Nou contingut del problema:** lectura crítica de la diferència de
taxes d'**abandonament escolar prematur** entre joves de 18-24 anys
a Catalunya, segons dades de l'**Idescat** (Enquesta de Població
Activa, 2022-2023): 34,2% entre joves de nacionalitat estrangera
vs 10,1% entre joves nascuts a Catalunya, una ràtio de més de 3×.

**Motivació pedagògica:** l'error típic ("l'origen migrat causa
l'abandonament") és real, alimenta discursos d'odi documentats, i
té conseqüències directes a l'aula. Desmuntar-lo amb la maquinària
de variable confusora és exactament l'aplicació socialment útil del
mètode. La literatura (Fundació Bofill, Centre d'Estudis Demogràfics,
estudis de Bayona/UB i Serra/UdG) ofereix tant el feix de confusores
estructurals (nivell socioeconòmic, educació dels pares —fins a 5×
més AEP entre joves amb pares amb estudis baixos—, segregació
escolar, llengua, racisme institucional) com evidència
quasi-experimental que neutralitza la lectura causal (fills
d'estrangers nascuts a Catalunya: 21,2% no acaben ESO; arribats
abans dels 7 anys: 21,7% — taxes pràcticament idèntiques entre dos
grups del mateix origen amb trajectòries escolars diferents).

**Adaptació del llenguatge:** el problema anterior usava una
correlació de Pearson (r = 0,60); aquest usa una diferència de
taxes entre grups. Pedagògicament idèntic ("associació observada
≠ causa"), però el vocabulari concret canvia.

### Canvis a fitxers

- **`problem.py`**: el bundle `_CAUS001_PROBLEM` reescrit
  íntegrament (enunciat, 3 passos amb expected_summary i typical_error
  nous). Descripcions del `_CAUS001_ERROR_CATALOG` generalitzades
  per no referir-se específicament a "r alta" o "causalitat inversa
  oblidada" (errors del problema anterior). IC-001 intacte.
- **`prompts/tutor_system_v1.2_CAUS-001.md`**: reescriptura de totes
  les Situacions A-E amb el nou tema (la causalitat inversa, que era
  l'alternativa dominant al problema anterior, aquí no s'aplica i no
  apareix als exemples; la variable confusora estructural pren el
  seu lloc). Secció "Quan retrocedir al reforç" amb senyals i exemples
  actualitzats. Exemples genèrics de "comprensió encarnada" i
  "vocabulari tècnic" actualitzats. Secció "El reforç" intacta
  (sol/begudes fredes inalterats). Situació F intacta.
- **`test_tutor_turn.py`**: `BASIC_TRANSCRIPT` actualitzat al nou tema.
  Assertion del Test 16 (`"música" in last_text`) actualitzada a
  `"origen" in last_text`. Test MP de càrrega de prompt per problema
  ara comprova `"abandonament"` i `"Idescat"` en lloc de
  `"corredors"` i `"BPM"`.
- **`test_simulator_state.py`**: Test MP4 (new_session amb problem_id
  concret) ara comprova `"abandonament"` al transcript[0] de CAUS-001
  en lloc de `"corredors"`.
- **`README.md`**: secció "Demo CAUS-001" reescrita: nou paràgraf
  introductori amb la motivació pedagògica i les fonts; Sessió A i
  Sessió B amb respostes adaptades al nou tema. Bullet de
  característiques actualitzat per mencionar les fonts (Idescat,
  Fundació Bofill).

### Verificació

195/195 tests verds (77 + 86 + 32). Cap canvi a l'arquitectura del
state machine, llm.py, simulator.py o app.py.

## 2026-05-25 — Multi-problema: picker IC-001 / CAUS-001 + verificació de la migració anterior

L'alumne pot triar a l'inici de la sessió quin problema vol treballar:
**IC-001** (interval de confiança, antic) o **CAUS-001** (correlació
vs. causalitat, recent). La selecció és per sessió; per canviar de
problema cal recarregar la pàgina (UI Streamlit) o re-executar el
simulador (CLI).

### Refactor multi-problema

- **`problem.py`** ja no és single-problem. Exposa un `PROBLEMS`
  registry indexat per id (IC-001, CAUS-001) on cada entrada conté
  el bundle complet (`problem`, `prerequisites`, `dependencies`,
  `error_catalog`, `prereq_id`, `title_human`). Funcions noves:
  `get(problem_id)` i `list_ids()`. Els noms globals heretats
  (`PROBLEM`, `PREREQUISITES`, etc.) segueixen existint apuntant al
  problema per defecte (`DEFAULT_PROBLEM_ID = "CAUS-001"`) només per
  back-compat amb tests heretats. Assercions d'integritat al càrrega
  del mòdul detecten errors d'esquema a la base de dades pedagògica.
- **`llm.py::_load_system_prompt(problem)`** ara accepta el problema
  com a paràmetre i carrega el fitxer corresponent
  (`prompts/tutor_system_<version>_<problem_id>.md`). La cache passa
  de variable única a dict per `problem["id"]`. `tutor_turn` passa el
  seu paràmetre `problem` a `_load_system_prompt` (abans s'ignorava
  i sempre s'usava `PB.PROBLEM`).
- **`llm.py::_format_position_marker`** accepta `total_steps` com a
  paràmetre. `tutor_turn` el calcula de `problem["passos"]` i el
  passa explícitament; el fallback a `PB.PROBLEM` només es manté per
  back-compat amb tests existents que criden la funció sense passar
  total_steps.
- **`simulator.py`**: nova funció `pick_problem_interactive()` que
  presenta la llista i accepta tant índex com id literal. `run_session`
  i `new_session` accepten `problem_id`. La constant `PREREQ_ID` es
  reemplaça per `_prereq_id_for(state)`, que llegeix del state. Flag
  CLI `--problem ID` per saltar el picker.
- **`app.py`**: pantalla inicial `render_picker()` amb una targeta per
  problema (botó "Treballar aquest problema"). El títol de la pàgina
  esdevé dinàmic després de la selecció. `tutor_turn` rep el bundle
  del problema actiu, no `PB.PROBLEM`.
- **Prompts**: el fitxer únic `tutor_system_v1.2.md` es divideix en
  `tutor_system_v1.2_IC-001.md` i `tutor_system_v1.2_CAUS-001.md`.
  Cada un té els exemples (Situacions A-F, secció "El reforç",
  exemples de retreat) adaptats al seu tema.
- **Tests**: 6 tests nous a `test_simulator_state.py` (registry,
  bundles, KeyError, new_session multi-problema, retreat amb prereq
  correcte per problema) i 1 a `test_tutor_turn.py` (càrrega de
  prompt per problema). Total: 77 + 86 + 32 = **195 tests**, tots
  verds.

### Reparació dels quatre defectes detectats a la verificació de Fase 3

- **`app.py`** línies 39 i 553: `page_title` i `st.title` segueixen
  amb "intervals de confiança" → `page_title` ara és genèric ("Tutor
  d'estadística"); el `st.title` esdevé dinàmic en funció del problema
  triat (`"Tutoria ({title_human})"`).
- **`test_tutor_turn.py`** línia 399: assertion residual
  `"mitjana" in last_text` que pertanyia al `BASIC_TRANSCRIPT`
  d'IC-001 → reemplaçada per `"música" in last_text`. La fixture ja
  s'havia migrat correctament; només faltava l'assertion.
- **`prompts/tutor_system_v1.2.md`** línia 273: exemple il·lustratiu
  rovellat ("Si l'alumne ja ha entès que el 95% és sobre el
  procediment...") → reescrit per al tema correlació-causalitat al
  fitxer `_CAUS-001.md`. El fitxer `_IC-001.md` conserva l'exemple
  original (que pertoca al seu tema).
- **`llm.py`** línia 178: exemple del format del marcador a un
  docstring esmentava literalment `PRE-PARAM` → generalitzat a
  `<PREREQ_ID>` amb nota explicativa que cada problema en té un
  diferent.

## 2026-05-25 — Intercanvi de tema: IC-001 → CAUS-001

Substitució completa del contingut pedagògic del tutor. L'arquitectura
(màquina d'estats, crida per torn, control block JSON, quality signals,
UI Streamlit) no canvia. Canvis de contingut purs:

- **`problem.py`** (Agent B): nou `PROBLEM` amb id `CAUS-001`,
  enunciat dels 150 corredors amb r = 0,60 entre BPM de música i
  velocitat de cursa. Tres passos socràtics sobre correlació vs.
  causalitat (Pas 1: per què r no implica causalitat; Pas 2: tres
  alternatives — causalitat inversa, variable confusora, atzar mostral;
  Pas 3: quin disseny experimental permetria defensar la causalitat).
  Nou prerequisit `PRE-CONFOUNDER` (escenari: hores de sol i vendes
  de begudes fredes en un poble de la costa). Nou `ERROR_CATALOG` amb
  etiquetes `CAUS_direct` i `CAUS_no_alternatives`. Nova entrada
  `confounding_variable` a `DEPENDENCIES`.
- **`simulator.py`** (Agent C): cap canvi de lògica; actualitzades
  referències literals a `PRE-PARAM` → `PRE-CONFOUNDER` si n'hi havia.
- **`prompts/tutor_system_v1.2.md`** (Agent D): secció `## El reforç`
  renomenada de `PRE-PARAM` a `PRE-CONFOUNDER`; pregunta del reforç
  substituïda per l'escenari sol/begudes fredes; exemples de
  `retreat_to_prereq` actualitzats a la nova confusió causal.
- **`app.py`** (Agent E): etiqueta `**Reforç PRE-PARAM**` →
  `**Reforç PRE-CONFOUNDER**` (una sola línia).
- **`test_tutor_turn.py`, `test_simulator_state.py`, `test_app.py`**
  (Agent F): assertions sobre contingut antic (`IC-001`, `PRE-PARAM`,
  literals d'intervals) actualitzades al nou tema; tokens opacs
  renomenats per claredat.
- **`README.md`, `CHANGELOG.md`** (Agent G): secció "Demo planificada"
  reescrita amb respostes de Sessió A i Sessió B per a CAUS-001;
  bullet de característiques actualitzat (`IC-001` → `CAUS-001`,
  `PRE-PARAM` → `PRE-CONFOUNDER`).

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
