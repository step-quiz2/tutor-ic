# Changelog

Registre concís dels canvis significatius del sistema, en ordre
cronològic invers. El detall tècnic de cada fase viu als documents
referenciats.

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
