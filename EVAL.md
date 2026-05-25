# Avaluació i tests

Aquest projecte té tres suites de test, totes executables sense clau
Gemini real (els tests stubben les crides al model). Total: **172
tests**.

## Suites

### `test_tutor_turn.py` — 71 tests

Cobreix les mecàniques de la funció pública `llm.tutor_turn()`:

- Parse correcte de respostes ben formades amb cada acció.
- Coerció a `stay` davant d'accions invàlides o JSON malformat.
- Tolerància a `---CONTROL---` embolicat en fences ` ```json `.
- Validació d'invariants del transcript (no buit, acaba en student,
  alternança user/model).
- Construcció correcta del multi-turn `contents` passat a Gemini.
- Carrega i interpolació del system prompt.
- Injecció del marcador de posició al darrer missatge user.
- Format del marcador a tots els estats possibles (pas normal, reforç
  actiu, sense posició).

### `test_simulator_state.py` — 69 tests

Cobreix la màquina d'estats compartida entre simulator i app, i el
bloc `quality_signals`:

- Transicions `stay` / `advance` / `retreat_to_prereq` des de tots els
  estats possibles.
- Avenç des de l'últim pas → `finished=True`.
- Cicle complet de reforç (retreat → diversos torns → advance →
  retorn al pas previ).
- `compute_quality_signals` sobre sessions buides, netes, amb
  arsenal complet d'esdeveniments (stays, retreats, pistes,
  parse failures).
- Càlcul correcte de `elapsed_seconds_total` des de timestamps del
  rastre (no del rellotge actual, regressió del bug que va donar
  durades absurdes en processar JSONs antics).
- `format_quality_signals` per al render terminal.

### `test_app.py` — 32 tests

Cobreix els helpers de l'app Streamlit (la lògica que no és UI):

- `simple_md_to_html` — conversió markdown bàsica (negretes,
  cursives, codi inline, paràgrafs, blockquotes, escape d'HTML).
- `is_disengaged` — heurística per detectar "vacil·lar" (paraules
  de mofa, missatges molt curts repetits).
- `count_consecutive_stays_in_same_position` — suport per a la
  decisió green vs yellow.
- `determine_turn_color` — color final segons acció i context.
- `position_label` — badge del torn segons l'estat.

## Execució

```bash
python3 test_tutor_turn.py        # ~1s
python3 test_simulator_state.py   # ~1s
python3 test_app.py               # ~1s
```

Cada suite imprimeix `✓` o `✗` per test i un resum al final. Codi
de sortida 0 si tot passa, 1 si alguna fallada.

## Què NO cobreixen els tests

Aquests tests són tots aïllats: stubben Gemini i no executen la UI
Streamlit. Per tant:

- **No verifiquen el comportament del model.** Si Gemini decideix
  malament en una situació concreta (per exemple: `action=stay` quan
  el reply suggereix `advance`), els tests no ho detectaran. Aquesta
  classe de fallada s'ha de detectar per inspecció humana de sessions
  reals (vegeu el simulator CLI, sota).

- **No verifiquen el render visual de Streamlit.** Els tests
  d'`app.py` cobreixen la lògica auxiliar, no com es veu la
  pàgina al navegador.

## Test d'integració manual amb el model real

El simulador CLI (`simulator.py`) és l'eina per a tests d'extrem a
extrem:

```bash
export GEMINI_API_KEY=...
python3 simulator.py --debug --save sessio.json
```

Després, inspeccionar el JSON desat: el bloc `quality_signals` resum
les mètriques agregades (ràtio stay/advance, parse failures, ús de
reforç) i `history` conté el rastre detallat torn a torn.

## Eval antiga

L'eval framework anterior (`eval_cases.py`, `eval_runner.py`,
`eval_results_*.json`), que mesurava `judge_step` sobre 30 casos
classificats, viu a `archive/pre-conversational/`. No s'executa al
sistema actual.
