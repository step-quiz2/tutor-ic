# Registre de canvis — sofisticació de la interacció

Aquest fitxer documenta l'aplicació iterativa de les propostes del
memoràndum d'avaluació de l'arquitectura tutor↔Python↔API↔IA.
Cada entrada inclou: l'objectiu, els fitxers tocats, què s'ha canviat
exactament, i què queda pendent relacionat. L'objectiu d'aquest
registre és el mateix que el del PROJECT_LOG.md però focalitzat
exclusivament a aquest pla de canvis.

## Ordre acordat

| # | Proposta | Estat | Resum |
|---|----------|-------|-------|
| 1 | Proposta 2 — Reforç (prereq) amb judge LLM + segon intent | ✅ Fet | Substitució del keyword matching deterministic per un judge LLM amb categoria KEY_only equivalent a la del judge principal, més política de reintents per a respostes parcials. |
| 2 | Proposta 3 — Generador de pistes ben alimentat | ✅ Fet | `generate_hint` i nou `generate_prereq_hint` reben context d'error (resposta, raó del judge, etiqueta, pistes anteriors); contraexemples al system prompt segons el guió; reintent del reforç i `?` durant el reforç usen el generador dirigit. |
| 3 | Proposta 1 — Judge stateful amb trajectòria | ✅ Fet | `judge_step` accepta paràmetre `context` opcional amb (recent_steps, prereq, step_attempts, concept_failure_streak); nova REGLA DE DESEMPAT 3 al system prompt (P3a/P3b/P3c) que resol ambigüitats typical_error vs conceptual_gap segons el patró previ. Compatibilitat preservada amb l'eval framework (context=None → comportament stateless idèntic). |
| 4 | Proposta 5 — Self-consistency selectiva | ✅ Fet | Camp `confidence ∈ {high, medium, low}` al JSON dels dos judges; re-mostreig automàtic a temperatura 0 quan és medium o low; verdict final del segon sample. Triage per quota: si en queden < 2 crides, s'autodesactiva el resample. |
| 5 | Proposta 4b — `diagnose_dependency` amb feina real (opció a: eliminar) | ✅ Fet | Eliminació total de la funció, el seu system prompt i la seva entrada al docstring del mòdul. Era codi mort literal (cap caller a `app.py`) i la "claredat arquitectònica" que el comentari pretenia preservar era falsa: suggeria lògica de diagnòstic real on només hi havia un retorn constant. |

La Proposta 6 (mitigacions de Phase 4 — abús de `!text`, pista-farmer,
respostes copiades del guió) queda fora d'aquest pla, per acord, i
recollida per a una iteració de robustesa posterior.

---

## Canvi 1 — Proposta 2: Reforç amb judge LLM + segon intent

**Data:** 2026-05-23
**Estat:** ✅ Fet

### Motivació

`_process_prereq_turn` validava la resposta al prerequisit (PRE-PARAM)
amb una comprovació deterministica: una resposta era correcta si i
només si contenia almenys una keyword "required" i cap "forbidden".
Aquest era exactament el mateix patró de fallada KEY_only documentat
al Phase 2 del PROJECT_LOG per al judge principal: respostes com
«μ és fix» passaven el filtre (contenen "fix") tot i no completar la
distinció demanada. Inversament, una resposta correcta amb vocabulari
no reservat com «x̄ canvia segons la mostra mentre la mitjana real
no es mou» quedava rebutjada per no contenir cap mot de la llista.

A més, el reforç era one-shot: una resposta dolenta donava
directament l'explicació canònica i tornava al problema principal.
Això perdia l'oportunitat socràtica de fer reformular respostes
parcialment correctes (les KEY_only) abans de cantar la solució.

### Canvis concrets

**Nou prompt sistema a `llm.py`** — `_SYSTEM_JUDGE_PREREQ`. Estructura
paral·lela a `_SYSTEM_JUDGE` (el principal) amb tres categories:

  - `correct` — afirmacions (A) sobre μ i (B) sobre x̄ totes dues
    presents i auto-suficients.
  - `keyword_only` — toca el tema però falta concretar quina dels
    dos és aleatòria i quina fixa, o aplica el concepte només a un
    dels dos símbols. Inclou una llista de contraexemples concrets.
  - `incorrect` — atribueix aleatorietat a μ o constància a x̄, o
    confessa no saber-ho, o resposta sense fonament.

Inclou regla de desempat d'auto-suficiència idèntica en esperit a la
del judge principal: si l'examinador ha d'omplir mentalment una part
per fer la resposta «sonar correcta», la resposta és keyword_only.

**Nova funció a `llm.py`** — `judge_prereq(prereq, student_answer)`.
Retorna `{verdict, reason}` (sense `error_label`, ja que el catàleg
del prereq només té un error pedagògicament rellevant: keyword_only,
codificat al verdict mateix).

**Reescriptura de `_process_prereq_turn` a `app.py`** — substitueix
el matching deterministic per la crida al judge. Política:

  - `correct` → tanquem reforç, tornem al problema.
  - `keyword_only` al **primer** intent → micropista («digues
    explícitament què és μ i què és x̄, i quina és aleatòria») i
    nou intent sense avançar.
  - `keyword_only` al **segon** intent → explicació canònica, tornem
    al problema.
  - `incorrect` → explicació canònica, tornem al problema. Sense
    reintent: si la resposta està molt desviada del concepte, un
    segon intent rarament ajuda; l'alumne pot fer `!text` si pensa
    que té raó.

**Fast-reject deterministic conservat** — si la resposta conté el
literal «μ és aleatòria» (o variants `forbidden_keywords`), es
descarta com a incorrect sense crida API. Una crida estalviada quan
l'error és estructuralment trivial.

**Estat nou a `_new_state`** — `prereq_attempts: 0`. S'incrementa a
cada intent del prereq, es reseteja a 0 quan el reforç es tanca.

**Millora UX a `render_problem_header`** — quan hi ha un prereq
actiu, la seva pregunta es mostra de manera persistent a la
capçalera amb etiqueta del número d'intent. Abans, en submitar la
primera resposta, el missatge amb la pregunta del prereq es
netejava (era no-persistent) i el reintent quedava sense context
visible.

**Simplificació de `_activate_prereq`** — abans empenyia un missatge
amb el text complet del prereq (ara redundant amb la capçalera).
Empeny un missatge curt de transició.

**Trace JSON enriquit** — l'entrada `history[].type == "prereq"` ara
inclou `verdict` (str de tres valors), `attempt` (int), `reason`
(text de la IA) i `api_call` (bool). Es manté compatibilitat
descendent a `render_history` amb el format antic basat en `correct`
(bool), per si s'obre un trace generat amb la versió anterior.

### Fitxers tocats

- `llm.py` — afegit `_SYSTEM_JUDGE_PREREQ` (~60 línies) i la funció
  `judge_prereq` (~30 línies).
- `app.py` — reescrit `_process_prereq_turn`, ampliat `_new_state`,
  ampliat `render_problem_header`, simplificat `_activate_prereq`,
  ampliat `render_messages` (kind nou `prereq_feedback`), ampliat
  `render_history` amb compatibilitat descendent.

### Sense canvis (intencionalment)

- `problem.py` — `keywords_required` i `forbidden_keywords` es
  conserven. Les `forbidden_keywords` segueixen actives com a
  fast-reject. Les `keywords_required` queden com a dades òrfenes
  (cap codi les llegeix ara) però no fan mal i poden servir si en
  el futur volem afegir un fast-accept opcional. Esborrar-les
  trencaria contractes implícits no documentats; deixar-les és
  conservador.
- `eval_cases.py` — no s'ha afegit cap cas de prereq al dataset
  (vegeu "Pendent relacionat" més avall).

### Impacte sobre la quota API

El reforç ara consumeix entre 1 i 2 crides addicionals per sessió
(la del judge més, eventualment, la del segon intent). El sostre
de `MAX_API_CALLS_PER_SESSION = 20` ja inclou marge per a això,
però val la pena monitoritzar:

  - Sessió A ("estudiant que raona bé"): sense canvi, no toca el
    reforç. 3 crides judge_step + eventuals pistes.
  - Sessió B ("estudiant amb l'error clàssic"): abans 3-4 crides
    judge_step + 1 pista; ara 3-4 judge_step + 1 pista + 1-2
    judge_prereq. Total esperat 5-7. Continua per sota del sostre.

### Pendent relacionat

1. **Casos d'avaluació per al prereq.** El dataset `eval_cases.py`
   no cobreix `judge_prereq`. Cal afegir-hi entre 6 i 12 casos
   (correct/keyword_only/incorrect) i estendre `eval_runner.py`
   per saber-los executar — possiblement amb un nou tipus de cas
   que distingeixi entre invocar `judge_step` i invocar
   `judge_prereq`.

2. ~~**Pista intermèdia adaptativa al reintent.**~~ ✅ Resolt al
   Canvi 2 (Proposta 3). La micropista del segon intent ara la
   genera la IA partint de la resposta concreta de l'alumne.

3. ~~**Comportament de `?` durant el reforç.**~~ ✅ Resolt al
   Canvi 2 (Proposta 3). `?` durant el reforç ara dispara una
   pista socràtica generada, no l'explicació canònica. La
   explicació canònica queda com a fallback si la quota està
   plena.

4. **Mètriques de qualitat del judge_prereq.** Sense casos d'eval
   no podem mesurar falsos positius del prereq. Donat que ara hi ha
   un classificador real, el risc de fals positiu existeix (encara
   que el prompt està reforçat amb la regla d'auto-suficiència).
   Caldrà fer una iteració d'eval similar a la del judge principal:
   3 repeticions, mesura de variància, anàlisi de fronterers.

---

## Canvi 2 — Proposta 3: Generador de pistes ben alimentat

**Data:** 2026-05-23
**Estat:** ✅ Fet

### Motivació

`generate_hint` rebia només `(step, dep_id)`. No veia la resposta
errònia de l'alumne, no veia la raó del judge, no veia l'etiqueta
d'error, no veia les pistes anteriors. La conseqüència estructural:
la pista era SEMPRE la mateixa per a un pas donat. Si l'alumne fallava
dues vegades al mateix pas (escenari habitual de la sessió B), el
mecanisme `_try_generate_hint` empenyia una pista nova... idèntica
a l'anterior, perquè els únics inputs no havien canviat. Una pista
socràtica que no agafa el que l'alumne ha dit per mig no és una
pista socràtica — és una repetició disfressada.

A més, el guió de la xerrada declara explícitament (secció 5,
"Tercera crida"):
> *la instrucció no descriu com ha de ser la pista bona canònica,
> sinó que posa un exemple de pista dolenta i un altre de pista
> bona, per a una mateixa situació. Es demana a la IA que imiti el
> segon patró de pista.*

El system prompt original no contenia cap exemple. Aquesta
discrepància entre guió i implementació era visible a qualsevol
revisió del codi. El canvi tanca aquest gap.

Tercera motivació, derivada del Canvi 1: el reforç ara té reintent,
i a `?` durant el reforç encara dispara l'explicació canònica
completa, que revela la distinció demanada i invalida la idea
socràtica del reintent. Calia un generador de pistes específic del
reforç.

### Canvis concrets

**Nou `_SYSTEM_HINT` a `llm.py`** — reescrit amb regles inviolables
explícites (no revelar, agafar el tros que l'alumne ha dit, no
repetir pistes anteriors) i TRES contraexemples concrets per a la
mateixa pregunta:

  - Cas A: resposta de l'alumne keyword_only → pista dolenta que
    revela vs pista bona que pregunta sobre el tros dit.
  - Cas B: alumne prem `?` sense haver respost → pista dolenta
    genèrica vs pista bona orientadora.
  - Cas C: l'error clàssic INT_prob_param → pista dolenta que
    explica vs pista bona que qüestiona el supòsit ocult.

Aquest format coincideix amb la pràctica que el guió ja anunciava.

**Nou `_SYSTEM_HINT_PREREQ` a `llm.py`** — anàleg per al reforç,
amb dos contraexemples adaptats a l'estructura específica del prereq
(la pregunta demana DUES afirmacions, una sobre μ i una sobre x̄,
i les pistes adequades porten l'alumne a completar la que falta).

**Signatura ampliada de `generate_hint`** — afegits els paràmetres
opcionals `student_answer`, `judge_reason`, `error_label` i
`prior_hints`. Construeix el user message en seccions condicionals:
si hi ha resposta, secció "RESPOSTA DE L'ALUMNE"; si hi ha raó,
secció "DIAGNÒSTIC"; si hi ha etiqueta, una línia amb pistes
contextuals específiques per a `KEY_only` i `INT_prob_param`; si
hi ha pistes anteriors, llista perquè el model no les repeteixi.
Tots són opcionals — quan no s'informen, la pista cau al cas
"genèric per al pas" i el prompt sap distingir-ho.

**Nova funció `generate_prereq_hint`** — paral·lela però adaptada al
reforç. Sense `error_label` (al prereq el verdict mateix codifica
la categoria d'error rellevant).

**Tracking de pistes a `app.py`** — nous camps a `_new_state`:

  - `hints_by_step: dict[int, list[str]]` — pistes ja donades a cada
    pas del problema principal. Es passa a `prior_hints` perquè el
    generador no les repeteixi.
  - `prereq_hints: list[str]` — anàleg per al reforç actiu. Es buida
    quan el reforç es tanca (correct, canonical-done) i defensivament
    a `_activate_prereq`.

**Helpers de context històric a `app.py`** — `_last_non_correct_answer_for_step(step_id)`
retorna la darrera resposta no-correct de l'alumne a aquell pas amb
la raó i etiqueta del judge associades. Anàleg
`_last_non_correct_prereq_answer(prereq_id)` per al reforç. La cerca
és en sentit invers per agafar el torn més recent.

**Reescriptura de `_try_generate_hint`** — extreu el context històric
amb el helper i el passa a `generate_hint`. També afegeix una entrada
`type: "hint"` a l'historial amb `scope`, identificador del pas,
text de la pista, `had_student_context: bool` i `n_prior_hints` per
a l'auditoria a posteriori al rastre JSON.

**Nova `_try_generate_prereq_hint`** — anàleg per al reforç. Inclou
fallback transparent: si la quota està plena, l'invocador pot decidir
fer fallback a l'explicació canònica (això es fa al handler de `?`).

**Handler de `?` durant el reforç actualitzat** — abans dispara
canonical, ara dispara `_try_generate_prereq_hint`. Si la quota està
plena, fallback a `pre['explanation']` (que és gratuït i no necessita
IA). Si la quota té marge però la IA falla, mostra warning i no
mostra res més (l'alumne pot tornar a provar).

**Path `keyword_only` del primer intent actualitzat** — la
micropista estàtica del Canvi 1 ara és el fallback; el cas comú és
una pista generada per la IA partint de la resposta concreta i de la
raó del judge. Això tanca un loop estètic important: la pista del
reforç ja no és genèrica, i no se solapa amb el `reason` del judge
(que ara no es mostra a la UI; queda al trace per al professor).

**Trace JSON enriquit** — entries `type: "hint"` són noves; tenen
`scope` (step/prereq), identificador (step_id o prereq_id), text,
`had_student_context` i `n_prior_hints`. El path keyword_only del
primer intent les marca amb `auto: true` (generades automàticament,
no per `?` explícit), distinció útil per a anàlisi posterior dels
patrons d'ús de pistes.

**Render de pistes a `render_history`** — un bloc per a `type:
"hint"` que mostra l'àmbit, si tenia context d'alumne, i el text.

### Fitxers tocats

- `llm.py` — reescrits `_SYSTEM_HINT` i `generate_hint`; afegits
  `_SYSTEM_HINT_PREREQ` i `generate_prereq_hint`. ~250 línies noves.
- `app.py` — afegits 2 helpers, `_try_generate_prereq_hint`;
  reescrits `_try_generate_hint` i el path keyword_only-attempt-1;
  modificat el handler de `?`; modificat `_activate_prereq` i els
  dos paths de tancament del reforç per buidar `prereq_hints`;
  ampliat `render_history`. Estat ampliat amb dos camps.

### Sense canvis (intencionalment)

- `judge_step` i `judge_prereq` no toquen els seus prompts en aquest
  canvi. La separació de rols (judge dóna feedback genèric; generator
  dóna pista dirigida) ja s'aplica només per estructura: la UI ara
  no mostra el reason del judge al path keyword_only-attempt-1 i sí
  mostra la pista generada.
- `diagnose_dependency` segueix sent placeholder; es tractarà al
  Canvi 5. (Resolt al Canvi 5: eliminada.)

### Impacte sobre la quota API

L'escenari pic és ara la sessió B amb un keyword_only al primer
intent del reforç:

  - 1-3 crides judge_step al pas 1 (depèn de quants intents abans
    d'arribar a conceptual_gap).
  - 1 crida judge_prereq al primer intent del reforç.
  - 1 crida generate_prereq_hint (la micropista al keyword_only).
  - 1 crida judge_prereq al segon intent (idealment correct).
  - 1 crida judge_step al retorn al pas 1 (idealment correct).
  - 2 crides judge_step als passos 2 i 3.

Total esperat: 8-10 crides. Per sota dels 20 del sostre. Però val
la pena considerar que ara els hints automàtics al keyword_only del
reforç i a la cadena failure_streak ≥ 2 dels passos principals
consumeixen quota, i un alumne particularment errant podria
acostar-se al límit. Si això esdevé un problema observat a sessions
reals, una opció és afegir un cap per tipus de crida (p.ex. màx 3
crides de generate_*_hint per sessió) en lloc d'apujar el sostre.

### Pendent relacionat

1. **Comprovació empírica de la qualitat de les pistes generades.**
   El system prompt nou és substancialment més llarg que l'original
   i incorpora exemples. Cal verificar amb sessions reals que les
   pistes generades respecten les regles inviolables (especialment
   "no revelar la resposta") i que les segones pistes són
   genuïnament diferents de les primeres. Una bateria d'eval anàloga
   a la del judge no és trivial perquè la qualitat d'una pista no
   és binària — caldrà disseny ad-hoc, probablement amb avaluació
   humana o LLM-judge sobre les pistes mateixes.

2. **Casos d'eval per a `generate_prereq_hint`.** Mateixa situació
   que la del judge_prereq al Canvi 1, agreujada per la naturalesa
   generativa.

3. **La discrepància documentada al guió queda tancada.** El guió
   ja descriu correctament el comportament implementat. Encara
   així, val la pena revisar el guió per si la descripció pot
   reforçar-se ara que l'arquitectura efectivament la implementa
   — per exemple, mencionar que les pistes són dirigides a la
   resposta concreta de l'alumne i no només al pas.

---

## Canvi 3 — Proposta 1: Judge stateful amb trajectòria

**Data:** 2026-05-23
**Estat:** ✅ Fet

### Motivació

`judge_step` rebia `(step, student_answer)` i prou. Cada crida era una
classificació independent, apàtrida. El judge no sabia si l'estudiant
acabava de passar el reforç PRE-PARAM correctament, si era el tercer
intent al pas 1, o si havia resolt el pas anterior. Per tant, davant
d'una resposta ambigua entre `typical_error` i `conceptual_gap`, no
podia recolzar-se en informació externa per inclinar el veredicte.

Els eval results mostraven un patró persistent: 8 desacords al Pas 2
classificats com `conceptual_gap` quan a priori eren `typical_error`,
i la mateixa drift apareixia a la segona iteració d'eval del
2026-05-22. El judge identificava manca de fonament conceptual en
respostes que, en context de sessió, eren més probablement fallades
d'aplicació — l'estudiant SÍ que tenia el concepte (havia passat el
reforç o havia respost passos anteriors correctament), però la
resposta puntual al pas 2 era prou minimal perquè el judge la
qualifiqués com a buit conceptual.

Aquesta classificació errònia té conseqüència pedagògica concreta:
`conceptual_gap` re-activa el reforç (que l'estudiant acaba de
passar!), mentre que `typical_error` dispara una pista del Canvi 2,
que és el tractament adequat.

### Canvis concrets

**Nova REGLA DE DESEMPAT 3 al `_SYSTEM_JUDGE`** — tres sub-regles
condicionades a la presència de la secció "PATRÓ DE LA SESSIÓ" al
user message:

  - **P3a** — si el reforç PRE-PARAM s'ha tancat amb verdict `correct`
    en aquesta sessió, una resposta ambigua tira cap a `typical_error`.
    L'estudiant acaba de demostrar la distinció μ vs x̄; la fallada
    és aplicació, no manca de fonament.

  - **P3b** — si algun pas anterior d'aquest mateix problema s'ha
    resolt amb verdict `correct`, l'estudiant ha demostrat capacitat
    de raonament estructurat → tira cap a `typical_error`.

  - **P3c** — contrabalanç: si `concept_failure_streak >= 2` (dos o
    més veredictes no-correct consecutius), el patró ja indica
    dificultat persistent → suspèn P3a i P3b i classifica
    estrictament sobre la resposta puntual.

La regla és explícitament additiva: no modifica les anteriors. Quan
la resposta és clarament `correct` (compleix auto-suficiència) o
clarament `conceptual_gap` (manca de fonament evident), el patró no
canvia el veredicte. Només actua a la franja ambigua.

**Signatura ampliada de `judge_step`** — afegit paràmetre opcional
`context: dict = None`. Quan és None, la funció es comporta com
abans (compatibilitat completa amb l'eval framework, que no passa
context). Quan s'informa, el user_msg s'amplia amb una secció final
"PATRÓ DE LA SESSIÓ:" que el system prompt sap reconèixer.

**Dos formatadors a `llm.py`** — `_format_recent_steps` i
`_format_prereq_info` que renderitzen el context dict a text compacte
per al prompt. Mantenen la mida del context per crida sota uns 150
tokens additionals.

**Nou helper a `app.py`** — `_build_judge_context(step_id)` recorre
l'historial d'estat i construeix el dict amb:

  - `recent_steps`: fins als 3 torns `type: "step"` més recents
    (més nou primer), amb step_id, verdict i error_label.
  - `prereq`: `{activated, final_verdict, attempts}` del **darrer**
    cicle del reforç (no global). La lògica recorre cap enrere fins
    a trobar un canvi al comptador `attempt` que indiqui inici d'un
    nou cicle. Si l'estudiant ha passat per dos cicles de reforç
    en la mateixa sessió, només el darrer compta per al judge.
  - `step_attempts`: intents previs al MATEIX step_id (no inclou la
    resposta que estem a punt de jutjar).
  - `concept_failure_streak`: el camp d'estat homònim, sense
    transformacions.

Aquest helper té tests unitaris (executats com a validació interna
en aquest canvi) que cobreixen estat buit, prereq passat,
streak alt i múltiples cicles de prereq.

**Crida modificada a `process_turn`** — abans del `_consume_api_quota`
fem `judge_context = _build_judge_context(step["id"])` i el passem
a `judge_step` com a kwarg. L'ordre és important: el context reflecteix
l'estat ABANS de la resposta actual.

**Auditoria al rastre JSON** — guardem el `judge_context` al history
entry corresponent. Així el professor pot inspeccionar exactament
quin context va veure el judge per a cada veredicte; útil per a debug
de casos sospitosos i per a entendre per què el judge va aplicar (o
no) P3a/P3b/P3c.

### Fitxers tocats

- `llm.py` — afegida REGLA DE DESEMPAT 3 al `_SYSTEM_JUDGE`; ampliada
  signatura de `judge_step`; afegits dos helpers de formatació.
- `app.py` — nou helper `_build_judge_context`; modificada la crida
  a `judge_step` al `process_turn`; afegit camp `judge_context` a
  l'entrada history.

### Sense canvis (intencionalment)

- `_SYSTEM_JUDGE_PREREQ`, `_SYSTEM_HINT`, `_SYSTEM_HINT_PREREQ` —
  cap canvi al system prompt del reforç ni al generador de pistes.
  L'argument: l'ambigüitat typical_error vs conceptual_gap és
  específica del judge principal, no apareix al reforç (que té
  categories diferents: correct/keyword_only/incorrect).
- `eval_runner.py`, `eval_cases.py` — la signatura nova és
  retrocompatible. L'eval segueix passant `judge_step(step, input)`
  sense context i mesura el comportament stateless (que és el floor
  apropiat per a una bateria d'eval determinista). Vegeu "Pendent
  relacionat".
- Semàntica de `concept_failure_streak` — el comptador compta
  qualsevol veredicte no-correct, no només `conceptual_gap`. El
  nom és històric i podria induir a error. Modifiquem la
  documentació de la regla P3c al system prompt perquè sigui
  fidel al que realment representa el camp, en lloc de canviar la
  semàntica del camp (que afectaria també l'activació de pistes
  al `_process_main_turn`, fora de l'abast d'aquesta proposta).

### Impacte sobre la quota i el cost per crida

L'input per cada crida `judge_step` ara conté ~100-150 tokens
addicionals en el cas comú (la secció PATRÓ DE LA SESSIÓ). No
canviem el nombre de crides. Comparat amb el cost per crida actual
(prompt sistema ~1100 tokens + user message ~150 tokens), és un
increment del ~10% en input, sense impacte material.

### Pendent relacionat

1. **Re-execució de l'eval amb el prompt nou.** El system prompt
   ha crescut amb la REGLA DE DESEMPAT 3. Tot i que aquesta regla
   està condicionada a la presència de "PATRÓ DE LA SESSIÓ" al
   user message (que el runner d'eval no envia), la mera presència
   de la regla al system prompt podria afectar subtilment la
   classificació en casos fronterers. Cal re-run d'`eval_runner.py`
   amb 3 repeticions per confirmar que els 30 casos no han baixat
   d'accuracy respecte de la línia base del 92%.

2. **Eval amb context simulat.** El benefici real de la Proposta 1
   és en context de sessió — i això NO s'està mesurant a l'eval
   actual. Cal afegir un mode al `eval_runner.py` que permeti
   simular contextos (p.ex. casos del Pas 2 amb prereq.final_verdict
   = "correct" i recent_steps amb pas 1 correct) i mesurar si els
   8 desacords del Pas 2 efectivament es resolen cap a typical_error.
   Aquesta és la mètrica que justificaria pedagògicament el canvi.

3. **Mida del judge_context al rastre JSON.** L'historial JSON ara
   conté un camp `judge_context` per a cada entrada step. En una
   sessió típica això suma ~3-5 KB. Acceptable per a un rastre de
   sessió única, però si es vol agregar rastres de moltes sessions
   per a anàlisi, val la pena considerar serialitzar només els
   camps que el judge va realment usar (p.ex. ometre recent_steps
   si està buit).

4. **Coordinació amb la Proposta 5 (Canvi 4).** Quan implementem
   self-consistency selectiva amb un camp `confidence`, l'estratègia
   de re-mostreig podria refinar-se segons el context: si el judge
   diu `medium` però el context aplica P3a/P3b, podem inclinar-nos
   cap a typical_error sense fer una segona crida. Aquesta
   optimització queda recollida per al disseny del Canvi 4.

---

## Canvi 4 — Proposta 5: Self-consistency selectiva

**Data:** 2026-05-23
**Estat:** ✅ Fet

### Motivació

Els eval results mostren que `judge_step` és essencialment
determinista en els casos clars i drifteja en els fronterers — els
mateixos 8 casos del Pas 2 que reapareixen en cada repetició. La
solució canònica per a aquest tipus de variància és self-consistency:
multimostrejar i agafar el mode. Però fer-ho universalment triplicaria
la quota d'API per cada classificació (3 mostres + voto majoritari).

La proposta intermèdia és barata: demanar al model que reporti la
seva pròpia confiança al JSON de sortida, i només re-mostrejar quan
sigui baixa o mitjana. La calibració d'aquesta self-report no és
perfecta — un LLM pot estar segur d'una resposta errònia — però com
a triage funciona: redueix la inversió a només els casos on
probablement aporta valor.

A més, aquest canvi tanca un buit estructural del Canvi 3 (judge
stateful). La REGLA DE DESEMPAT 3 (P3a/P3b/P3c) actua quan el model
es troba davant d'una ambigüitat. Si en aquests casos el model
reporta `medium` o `low`, ara fem una segona crida a temperatura 0
on el model torna a aplicar la regla, ara sense soroll. La sinergia
és directa.

### Canvis concrets

**Nou camp `confidence` al JSON dels dos judges** — `_SYSTEM_JUDGE` i
`_SYSTEM_JUDGE_PREREQ` ara demanen un camp addicional al JSON de
sortida amb tres valors:

  - `high` — verdict inequívoc, cap senyal d'ambigüitat. Default
    esperat per a la majoria de respostes.
  - `medium` — dubte raonable entre dos verdicts (al judge principal:
    KEY_only vs conceptual_gap, typical_error sense etiqueta evident,
    correct fregant l'auto-suficiència; al prereq: keyword_only vs
    incorrect, o correct vs keyword_only).
  - `low` — material insuficient (resposta extremament curta,
    críptica, o ambigua).

El system prompt instrueix explícitament a no marcar `high` per
defecte. La calibració d'aquesta self-report queda pendent
d'auditoria empírica (vegeu "Pendent relacionat").

**Refactor de `judge_step` en dues capes a `llm.py`**:

  - `_build_judge_user_msg(step, student_answer, context)` —
    construeix el user message, extret de `judge_step` per
    no duplicar codi entre la primera crida i el re-mostreig.
  - `_judge_step_single(user_msg, temperature)` — una crida
    individual amb parse i normalització del JSON. Accepta
    `temperature` per permetre forçar 0 al re-mostreig.
  - `judge_step(step, student_answer, context, allow_resample)` —
    orquestra. Fa primera crida (temperatura default 0.2); si
    `confidence == "high"`, retorna directament; si no, fa segona
    crida a temperatura 0 sobre el mateix prompt; pren el verdict
    de la segona com a final i informa al retorn de `agreement`,
    `initial_verdict`, `initial_error_label`, `n_api_calls`.

  Estratègia de re-mostreig: agafem la segona crida (més
  determinista) com a verdict final. Si coincideix amb la primera,
  no canvia res (però hem confirmat el verdict). Si difereix, hem
  corregit una probable fluctuació de la primera. **No fem majority
  voting amb 3 samples** perquè el cost en quota no està justificat
  donat el patró d'errors observat (drift sistemàtic, no soroll
  pur).

  Robustesa: si la SEGONA crida llança excepció però la primera
  havia anat bé, retornem el verdict de la primera amb
  `resampled: false` i `resample_failed: true`. Mai degradem el
  comportament global per un incident tècnic a una crida concreta
  de re-mostreig.

**Refactor anàleg per a `judge_prereq`** — mateixa estructura amb
`_judge_prereq_single`. El prereq no té l'ambigüitat typical_error
vs conceptual_gap, però sí pot tenir-ne entre `keyword_only` i
`incorrect` (respostes parcials sense fonament) o entre `correct` i
`keyword_only` (auto-suficiència marginal).

**Gestió de quota a `app.py`** — abans de la crida calculem
`remaining = MAX_API_CALLS_PER_SESSION - api_calls_used` i passem
`allow_resample = (remaining >= 2)`. Si en queden < 2, el judge
no re-mostreja encara que reporti baixa confiança. Després de la
crida, llegim `n_api_calls` del retorn i consumim les extres
necessàries (`max(0, n - 1)`). Aquest patró és el mateix tant a
`_process_main_turn` com a `_process_prereq_turn`.

**Auditoria al rastre JSON** — l'entrada `history` ara inclou:
`confidence`, `resampled`, `initial_verdict`, `initial_error_label`,
`agreement`, `resample_failed`, `n_api_calls`. El professor pot
veure exactament quins casos van requerir re-mostreig i si els dos
samples coincidien.

**Renderitzat ampliat a `render_history`** — per cada torn `step` o
`prereq` es mostra `conf=high|medium|low` i, si hi ha hagut
re-mostreig, si va ser "acord amb {initial}" (mateix verdict abans
i després) o "canvi: {initial}→{final}" (re-mostreig va corregir
el primer sample). Útil per inspecció visual ràpida d'una sessió.

### Fitxers tocats

- `llm.py` — afegida secció AUTO-AVALUACIÓ DE CONFIANÇA a tots dos
  system prompts (judge + judge_prereq). Extret `_build_judge_user_msg`.
  Afegides `_judge_step_single` i `_judge_prereq_single`. Reescrites
  `judge_step` i `judge_prereq` com a orquestradors. Constant
  `_VALID_CONFIDENCE` al principi del bloc.
- `app.py` — modificades les dues crides a judges per calcular
  `allow_resample`, processar `n_api_calls` i guardar metadades a
  l'historial. Ampliada `render_history` amb la visualització de
  confiança i re-mostreig.

### Sense canvis (intencionalment)

- `generate_hint`, `generate_prereq_hint` — el camp `confidence`
  no aplica a la generació de pistes (no és una classificació; no
  hi ha "verdict" a re-confirmar). Si en algun moment es vol auto-
  evaluar la qualitat de la pista, és un canvi separat (Proposta 6
  o futur).
- `diagnose_dependency` — segueix sent placeholder; Canvi 5.
  (Resolt al Canvi 5: eliminada.)
- `eval_runner.py`, `eval_cases.py` — la signatura nova és
  retrocompatible (`allow_resample=True` per default). L'eval
  framework farà servir self-consistency automàticament. Vegeu
  "Pendent relacionat" sobre el cost addicional.

### Impacte sobre la quota i la latència

**En sessió típica**, l'escenari realista per a la sessió A
(estudiant que respon bé):
  - 3 judge_step amb confidence high → 3 crides
  - 0 re-mostrejos
  Total: 3 crides (igual que abans).

**En sessió B** (estudiant amb error clàssic):
  - 1-2 judge_step amb confidence medium → 2-4 crides
  - 1-2 judge_prereq (variabilitat segons el reforç) → 1-3 crides
  - 1 generate_prereq_hint (Canvi 2) → 1 crida
  - 1-2 generate_hint (Canvi 3) → 1-2 crides
  Total estimat: 5-10 crides (vs 8-10 sense self-consistency). El
  re-mostreig pot afegir fins a +3 crides al pic.

El sostre de 20 segueix amb marge en escenaris normals. **El cas
patològic** és un estudiant que faci entrades curtes i ambigües
en cada torn: cada classificació podria sortir low confidence i
re-mostrejar, sumant uns 2 × 7 ≈ 14 crides només de classificació,
més pistes. Aquí ens podríem acostar al sostre. La protecció és
el `allow_resample = (remaining >= 2)`, que apaga el resample
quan ja no en queden marges. Aleshores el classificador torna a
ser stateless-tipus (una sola crida amb la confiança original),
sense degradació pedagògica observable.

**Latència**: cada re-mostreig duplica la latència del torn afectat
(d'~2s a ~4s). L'experiència UI continua sent acceptable amb el
spinner.

### Pendent relacionat

1. **Calibració empírica de la self-report.** Aquesta és la
   incertesa més gran d'aquest canvi. No sabem si Gemini calibra bé
   `high`/`medium`/`low` per al nostre domini. Una self-report
   sistemàticament `high` faria que el re-mostreig no s'activés
   mai (degradant aquest canvi a no-op). Una self-report
   sistemàticament `medium` faria que tot es re-mostregi (cost
   doblat sense guany). Cal mesurar la distribució: passar tot
   `eval_cases.py` (30 casos × 3 repeticions) i agregar la
   distribució de `confidence` reportada. Tasca per a la propera
   iteració d'eval.

2. **Decisió sobre l'estratègia "segon sample manda".** La política
   actual agafa el verdict de la segona crida si difereix de la
   primera. Una alternativa: si difereixen, fer una tercera crida
   per desempatar (3-sample majority). Cost: triplicaria les
   crides en els casos de desacord. Si l'auditoria empírica mostra
   que els desacords són freqüents (>20% dels re-mostrejos), val
   la pena considerar-ho. Si són rars (<10%), la política actual
   és suficient.

3. **Sinergia amb la Proposta 1 (Canvi 3) no completament
   explotada.** El memo original sugeria una optimització: si
   `confidence == "medium"` però la regla P3a aplica amb força
   (prereq passat amb correct), podríem flipejar el verdict cap a
   typical_error sense fer la segona crida. Aquesta optimització
   no s'ha implementat — l'argument actual és que la segona crida
   ja veu el context i aplicarà la regla pel seu compte de manera
   més robusta que un override deterministic post-hoc. Si
   l'auditoria empírica mostra que el segon sample NO aplica
   sistemàticament P3a quan hauria, replantegem.

4. **Eval runner: gestió del cost variable.** Amb self-consistency
   activa per default, `eval_runner.py` pot fer fins a 2 crides
   per cas. 30 casos × 3 repeticions × 2 = 180 crides al pic
   (vs 90 fixes abans). Documentar-ho al runner o afegir un flag
   per desactivar el resample en mode eval — depèn de si volem
   que l'eval mesuri la qualitat amb o sense self-consistency
   (probablement les dues: una bateria comparativa té sentit).

5. **Mètrica nova al rastre JSON: "rerun rate".** Seria útil
   exposar a l'expander del professor (a sobre del historial) un
   resum: "X dels Y veredictes van requerir re-mostreig, dels
   quals Z van canviar". Aquesta agregació viu fora del rastre
   per torn i ajuda a entendre la dinàmica d'una sessió d'una
   ullada. Tasca de UX, no de motor.

---

## Canvi 5 — Proposta 4b: `diagnose_dependency` eliminada (opció a)

**Data:** 2026-05-23
**Estat:** ✅ Fet

### Motivació

El memo original deixava obertes dues alternatives per a aquesta
funció:

  (a) Eliminar-la. La funció era placeholder literal: el seu cos
      cridava una API que, per construcció (un sol prerequisit al
      sistema), sempre retornava la mateixa cadena `"param_vs_stat"`.
      El comentari intern ho documentava amb total honestedat
      ("En aquest sistema mínim sempre és el mateix, però mantenim
      la signatura per claredat arquitectònica").

  (b) Fer-la real: descompondre `param_vs_stat` en quatre
      sub-conceptes i fer que la funció diagnostiqués quin sub-
      concepte fallava perquè el reforç fos adaptat.

Decisió presa: **opció (a)**. Raonament:

  1. La pretesa "claredat arquitectònica" del comentari era falsa.
     Suggeria que hi havia lògica de diagnòstic real on només hi
     havia una crida API que retornava una constant; un futur
     lector del codi (humà o LLM) podria malinterpretar-ho com a
     punt d'extensió viu.

  2. La funció NO era cridada per `app.py`. Era codi mort literal
     al lloc on un sistema real l'hauria activada (a
     `_activate_prereq`). Hauria estat un canvi sense efecte
     observable des de la UI. Mantenir codi no executat només
     perquè algun dia podria activar-se va contra els principis
     declarats al guió de la xerrada (sistema mínim per a 20 min
     de demo).

  3. La descomposició de l'opció (b) afegiria 4 micro-explicacions
     condicionades + lògica de matching al reforç, multiplicant la
     superfície de testing. La granularitat (μ vs x̄ vs
     fix/aleatori vs connexió) no és pedagògicament evident per al
     nivell del problema — un alumne d'introducció que confon les
     dues mitjanes probablement no té cap dels quatre sub-conceptes
     clar, no només un.

Aquesta decisió queda registrada explícitament per si en una
iteració futura del sistema (més problemes, més dependències) cal
revisitar la pregunta. En aquell escenari, l'opció (b) deixaria de
ser sobre-enginyeria i passaria a ser arquitectura genuïna.

### Canvis concrets

**Esborrats de `llm.py`**:
  - Constant `_SYSTEM_DIAG` (system prompt sense ús efectiu).
  - Funció `diagnose_dependency(step, student_answer)`.

**Actualitzats**:
  - Docstring de mòdul de `llm.py`: l'enunciat "Tres funcions" ja
    era obsolet (de fet eren cinc abans d'aquest canvi). Ara
    declara correctament "Quatre funcions públiques" amb les
    signatures completes.
  - `README.md`, taula "Fitxers": l'entrada de `llm.py` deia
    "Tres crides a Gemini (`judge_step`, `diagnose_dependency`,
    `generate_hint`)"; ara diu "Quatre crides a Gemini
    (`judge_step`, `judge_prereq`, `generate_hint`,
    `generate_prereq_hint`)" amb nota sobre self-consistency.

### Fitxers tocats

- `llm.py` — esborrades ~20 línies (system prompt + funció).
- `README.md` — una línia actualitzada.

### Sense canvis (intencionalment)

- `PROJECT_LOG.md` — té una taula "Files involved" obsoleta que
  encara fa referència a `diagnose_dependency` i a "Three Gemini
  calls". Aquest document és històric (Phases 1-4); reescriure'l
  retroactivament seria revisionisme. La font de veritat del que
  hi ha ARA és el CHANGELOG_SOFISTICACIO i el README. Un LLM
  continuant la feina ha de llegir CHANGELOG abans que PROJECT_LOG.

- `problem.py` — el camp `keywords_required` segueix a
  `PREREQUISITES["PRE-PARAM"]`. És dades òrfenes des del Canvi 1
  (cap codi les llegeix) però conservades llavors per prudència.
  Una iteració de neteja futura el podria eliminar; no l'hem
  inclòs aquí perquè el Canvi 6 era específicament sobre
  `diagnose_dependency`.

### Impacte sobre la quota

L'eliminació no estalvia crides reals: `diagnose_dependency` MAI
era cridada des de `app.py`. L'estalvi és exclusivament cognitiu
(menys codi a llegir) i de mantenibilitat (menys lloc on els
prompts es poden desviar de la realitat).

### Pendent relacionat

1. **Neteja anàloga de `problem.py.keywords_required`.** Si vols
   coherència completa en l'eliminació de codi/dades mortes,
   `keywords_required` és l'altre cas. La diferència és que era
   conservat amb una raó plausible al CHANGELOG ("fast-accept
   opcional futur"). Si aquesta possibilitat ja no està a
   l'horitzó, val la pena treure-la també.

2. **`PROJECT_LOG.md` desactualitzat.** El document té una taula
   "Files involved" i una secció "Open work" que reflecteixen
   l'estat al final de Phase 4. Decisió a prendre: (a) afegir un
   tall al final del fitxer que digui "Aquí acaba la sèrie
   PROJECT_LOG; les iteracions posteriors viuen a
   CHANGELOG_SOFISTICACIO.md"; (b) reescriure la taula i el "Open
   work" per reflectir l'estat actual; (c) deixar-lo com està
   confiant que el lector entendrà el context. La opció (a) és la
   menys invasiva i la més honesta amb el caràcter històric del
   document.

---

## Síntesi de la sèrie

Aquesta sèrie de cinc canvis (Canvis 1-5 d'aquest registre,
corresponents a les propostes 2, 3, 1, 5 i 4b del memo original)
ha fet la transició del tutor d'una arquitectura de tres
classificadors apàtrides i independents a una arquitectura de
quatre crides interconnectades amb tracking de trajectòria,
self-consistency selectiva i pistes dirigides a l'error concret.

Els canvis es poden agrupar conceptualment en tres famílies:

  - **Simetrització pedagògica** (Canvis 1, 2): el reforç i el
    generador de pistes ara tenen la mateixa qualitat
    d'avaluació/dirigit que el classificador principal.
    L'asimetria que es va detectar al memo (judge sofisticat +
    reforç per keyword + pista genèrica) era el principal dèficit
    de coherència; ja no hi és.

  - **Memòria de sessió** (Canvi 3): el judge ara veu la
    trajectòria de l'estudiant — el reforç passat, els passos
    anteriors, el comptador de fallades. La REGLA DE DESEMPAT 3
    converteix patrons previs en decisions actuables al moment de
    classificar una resposta ambigua.

  - **Robustesa de la classificació** (Canvi 4): self-consistency
    selectiva via auto-report de confiança redueix la variància
    en els casos fronterers sense doblar el cost mitjà. El triage
    per quota evita que el sistema es bloquegi en sessions llargues.

  - **Higiene** (Canvi 5): codi mort eliminat.

Tres pendents són crítics per validar la sèrie empíricament i
queden recollits a les seccions "Pendent relacionat" individuals:

  - Re-run d'eval amb el prompt nou (Canvi 3, punt 1) per
    confirmar que no s'ha degradat el 92% de la línia base.
  - Eval amb context simulat (Canvi 3, punt 2) per mesurar si els
    8 desacords del Pas 2 efectivament es resolen.
  - Calibració empírica de la self-report `confidence` (Canvi 4,
    punt 1) per saber si Gemini reporta well el seu propi dubte.

Sense aquestes tres mesures, els canvis són defensables per
arguments pedagògics i estructurals (com s'argumenta al text de
cada entrada) però no estan validats com a millores numèriques.
