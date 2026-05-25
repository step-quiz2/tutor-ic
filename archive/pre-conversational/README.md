# Arxiu — pre-conversational

Aquest directori conté codi associat a una arquitectura anterior del
tutor IC, basada en tres classificadors LLM (`judge_step`,
`judge_prereq`, `generate_hint`). Aquesta arquitectura es va abandonar
el 24/05/2026 quan es va redissenyar el sistema a una sola crida per
torn (`tutor_turn`, a `llm.py` al directori arrel).

## Contingut

| Fitxer | Què era |
|---|---|
| `eval_cases.py` | Dataset de 30 casos (12 correct + 12 typical_error + 6 conceptual_gap) per a l'eval de `judge_step`. |
| `eval_runner.py` | Runner per al dataset anterior. Calculava matrius de confusió i taxes de fals positiu/negatiu. |
| `eval_results_20260523_135124.json` | Artefacte d'una execució de l'eval framework. |

## Per què queda

Cap d'aquests fitxers s'executa al sistema actual. Es conserven per
si en algun moment cal:

- Recuperar formulacions concretes dels 30 casos de prova (canonical
  paraphrases del professor, formes específiques de l'error clàssic,
  etc.). Bona base de partida per a una eventual eval de trajectòries.
- Documentar empíricament què feia bé i malament el sistema anterior
  (mètrica de fals positius vs negatius).

Per a executar res d'això caldria també restaurar les funcions
`judge_step` / `judge_prereq` / `generate_hint` a `llm.py`, que ja no
hi són. **No està previst tornar-hi.**

Veure `../../README.md` per al sistema actual i `../../CHANGELOG.md`
per a la transició.
