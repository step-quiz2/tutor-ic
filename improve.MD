# improve.MD

Engineering brief for an AI coding agent. Audience: an autonomous code-editing
model that will implement the tasks below across two sibling repositories. This
document is the single source of truth for scope, rationale, and acceptance
criteria. Read it fully before touching code.

The end goal is a **conference talk for university statistics faculty**. The
demo must make the *architecture* legible: a deterministic Python control layer
driving a stochastic LLM that only judges conceptual understanding. Every task
below serves that narrative. Optimize for "explainable on a projector", not for
child-friendliness.

---

## 0. The two projects

Two Socratic tutors, both Streamlit + Google Gemini (`google-genai` SDK), both
in Catalan. They share one architectural pattern but implement it unevenly.

### Shared architecture (the thesis of the talk)

- **Deterministic control lives in Python; the LLM only judges understanding.**
  Each conversational turn makes exactly one Gemini call. The model returns
  free-form tutor text, a literal `---CONTROL---` separator, and a JSON control
  block. Python owns the state machine (which step, which chapter, when to
  advance, when the session ends). The model never decides position.
- **Canonical question injection.** When the state machine advances, Python —
  not the model — injects the canonical question text for the new step as its
  own bubble, marked `source="py"`. This guarantees the prompt the student sees
  is always the authored one, never a model paraphrase.
- **Two-layer color semantics in the UI.** One layer encodes the *pedagogical
  action* (advance / stay / retreat); an orthogonal "source chip" encodes *who
  generated the bubble* (🐍 Python deterministic vs 🤖 IA heuristic).
- **Graceful fallback without an API key.** A keyword-heuristic "mode de
  reserva" runs the full flow with no Gemini call, so the system is demoable
  offline. Fallback turns are tagged `mode="py"`.
- **Per-turn trace + quality signals.** Each turn appends to `state["history"]`
  (action, position before/after, parse status, timings). One tutor aggregates
  this into `quality_signals` for the instructor.

### Project A — `tutor-div` (divisibility, age ~12)

Files: `app.py`, `tutor.py` (state machine, Streamlit-independent),
`llm.py` (Gemini interface + fallback), `problems.py` (content),
`prompts/tutor_system_v2.md`, `test_tutor.py`.

State model: linear **chapters → steps**. `tutor.apply_action(state, action)`
handles `stay` / `advance`; advancing past the last step of a chapter closes it
and opens the next (Python writes the chapter opening). Content unit per step:
`pregunta`, `resposta_ref` (internal), `conceptes_clau`, `pistes`.

Control block (current): `{"action": "stay"|"advance"}` only.
`llm.tutor_turn(...)` returns
`{reply, action, n_api_calls, mode, raw_output, control_parse_ok}`.

UI: native `st.chat_message` with mode badges. Has a `?debug=1` URL expander
showing internal state and the raw trace.

NOT present in div: no prerequisites/retreat, no `error_catalog`, no
`objectives_met`, no diagnostic field, no aggregated quality-signals summary,
no card-based CSS.

### Project B — `tutor-ic` (confidence intervals + correlation vs causation, age ~18)

Files: `app.py`, `simulator.py` (state machine + quality signals + CLI),
`llm.py`, `problem.py` (multi-problem registry), several
`prompts/tutor_system_v1.2*.md`, plus a test suite
(`test_app.py`, `test_simulator_state.py`, `test_tutor_turn.py`,
`test_enrichment.py`) and `EVAL.md`.

State model: **steps + a single prerequisite per problem** with retreat.
`simulator.apply_action` handles `stay` / `advance` /
`retreat_to_prereq`, returning a transition code
(`stay|next_step|finished|enter_prereq|exit_prereq|noop`).
`enrich_after_transition` injects the canonical question deterministically.

Multi-problem registry `PB.PROBLEMS` keyed by id (`IC-001`, `CAUS-001`). Each
bundle already contains an `error_catalog` (e.g. `INT_prob_param`,
`CAUS_direct`, `KEY_only`, `GEN_other`) and each step carries a
`typical_error_label`. **These exist but are not yet wired into the control
block** — the model is never asked to name the error.

Control block (current): `{"action": ..., "objectives_met": [...]}`.
`VALID_ACTIONS = ("stay", "advance", "retreat_to_prereq")`.
`llm.tutor_turn(...)` returns
`{reply, action, objectives_met, n_api_calls, mode, raw_output, control_parse_ok}`.

UI: bespoke CSS tutor cards, semantic action colors, source chips, a layer
legend, long-bubble pagination, a problem picker, and a rich end-of-session
summary built from `quality_signals`.

### Asymmetry summary (what each project is missing)

| Capability | div | ic |
|---|---|---|
| Card UI + source chips + action colors | ✗ | ✓ |
| Live per-turn trace surfaced in UI | partial (`?debug`) | only at end |
| `error_catalog` / `typical_error_label` | ✗ | ✓ (defined, unused) |
| `diagnostic` field in control block | ✗ | ✗ |
| `objectives_met` in control block | ✗ | ✓ |

---

## Scope of this brief

Three tasks, to be applied to **both** projects so they present as siblings:

- **Task 1 (UX):** live "How the tutor is thinking" inspector panel.
- **Task 2 (UX):** unify the visual language across both tutors.
- **Task 4 (algorithm):** control block returns *why* (a diagnostic), not just
  *whether*.

Out of scope for now (mentioned only as future direction): porting prerequisites
to div, and confidence-graded double-check advancing. Do **not** implement these.

Global non-negotiables for every task:

- **Never let the LLM own control flow.** The `diagnostic` field added in Task 4
  must not influence `apply_action`. Python advances/stays exactly as today; the
  diagnostic is recorded, not acted upon.
- **Preserve the fallback path.** Every change must keep the no-API-key mode
  working. Fallback results must populate any new field with a safe default.
- **Keep the transcript/display split intact.** `transcript` is the model's
  context (strict tutor/student alternation, ends in `student`); `display` is
  the UI log with `source` tags. New UI must read `display`/`history`, never
  mutate `transcript` shape.
- **Tests must stay green.** Run the existing suites after each task; add new
  tests where indicated. Do not weaken existing assertions to pass.

---

## Task 1 — Live "How the tutor is thinking" inspector (Type A, low risk)

### Goal
Surface, turn by turn, the deterministic decision behind each tutor reply. This
is the single highest-leverage demo feature for a statistics audience: it proves
the control flow is auditable and that the LLM only emits an action, while Python
decides position.

### What to render
A sidebar (or expander) panel, updated every turn, reading **only existing
state** (`state["history"]`, `state["last_raw_output"]`, position helpers). For
the latest turn show:

- the action taken (`stay` / `advance` / `retreat_to_prereq`), rendered with the
  same semantic color already defined in the ic CSS (green / yellow / gray);
- `control_parse_ok` (a small ⚠ marker when the control block failed to parse and
  fell back to `stay`);
- the state transition `position_before → position_after`
  (ic already stores both; div stores `position_before` + `transition`, derive
  the after-position from the post-action state);
- in div, fold the existing `?debug=1` content (cap_idx/pas_idx, raw_output,
  trace) into this same panel so there is one inspector, not two.

Keep it collapsible and off by default behind a toggle labeled e.g.
"Mode inspector (docent)" so a live demo can switch it on deliberately.

### How to implement
- **ic:** add a `render_inspector(state)` function in `app.py` invoked from
  `render_chat_view` (inside the existing `with st.sidebar:` block, below the
  action buttons). Read `state["history"][-1]`. Reuse `determine_turn_color` for
  the action swatch.
- **div:** add the analogous panel in `app.py`'s sidebar. Reuse the per-turn dict
  already appended in `processa(...)` (`position_before`, `action`, `transition`,
  `control_parse_ok`, `n_api_calls`). Replace the standalone `?debug=1` expander
  body with a call into the same renderer, but keep `?debug=1` as the gate that
  also reveals raw_output.

### Acceptance criteria
- [ ] Toggling the inspector on/off does not alter tutor behavior or state.
- [ ] Panel reflects the *latest* turn after every rerun.
- [ ] Action swatch color matches the tutor-card color for the same turn.
- [ ] A forced control-parse failure shows the ⚠ marker.
- [ ] No new writes to `transcript`.

### Status
- [ ] ic: inspector panel
- [ ] div: inspector panel + `?debug` consolidation
- [ ] Manual demo pass on both

---

## Task 2 — Unify the visual language across both tutors (Type A, low risk)

### Goal
The two tutors must look like one product family on stage. Today ic has the
mature card system (CSS cards, source chips, action colors, layer legend,
pagination, picker) while div uses native `st.chat_message` with simpler badges.
Bring div up to ic's visual system; do not regress ic.

### Direction
Promote ic's presentation layer to a shared style and port it to div. Concretely
in div's `app.py`:

- replace the `st.chat_message`-based history rendering with ic-style
  `.tutor-card` bubbles carrying the orthogonal **action color** (border/bg) and
  **source chip** (🐍 Python / 🤖 IA);
- add ic's **layer legend** (action colors + source chips) so the two-layer
  semantics read identically in both apps;
- adopt ic's `simple_md_to_html` (or factor it into a tiny shared helper) so
  markdown rendering is consistent;
- keep div's existing color meaning aligned: map div's `advance` → green,
  `stay` → gray; div has no retreat yet, so no yellow-from-retreat case.

Decide on shared CSS by copying ic's relevant blocks into div verbatim first
(fastest, lowest risk), then optionally extract a `style.py`/`assets.css`
imported by both. Extraction is a nice-to-have, not required for the talk.

Things to preserve:
- div's progress bar and chapter/step indicator in the sidebar;
- ic's pagination and picker (do not remove);
- both apps' fallback-mode status indicator.

### Acceptance criteria
- [ ] div renders tutor turns as cards with action color + source chip, no longer
      via `st.chat_message`.
- [ ] The layer legend appears in both apps with identical semantics.
- [ ] ic visuals unchanged (regression check on picker, pagination, summary).
- [ ] Both apps still clearly distinguish 🐍 Python bubbles from 🤖 IA bubbles.
- [ ] Fallback-mode banner still shows in both.

### Status
- [ ] Port card system + chips + legend to div
- [ ] Shared markdown helper aligned
- [ ] (optional) extract shared CSS module
- [ ] Regression pass on ic UI

---

## Task 4 — Control block returns *why*, not just *whether* (Type B, safe variant)

### Goal
Make the system diagnose the *conceptual misunderstanding*, not merely "stuck vs
progressed". For a statistics audience this reframes the tool from "a chatbot
with a prompt" to "a system that classifies misconceptions". The diagnostic is
**recorded and used for hint selection and instructor reporting only** — it must
never alter the state machine.

### Data model
Reuse ic's existing `error_catalog` and per-step `typical_error_label`. Introduce
the same concept in div.

- **div:** add an `error_catalog` dict to `problems.py` (a few stable codes per
  chapter, e.g. `MUL_DIV_confusion`, `INFINITE_multiples`, `PRIME_vs_odd`,
  `KEY_only`, `GEN_other`) and a `typical_error_label` on each step. Keep codes
  short and human-readable; they will appear on the instructor panel.

### Control block change
Extend the JSON the model returns with an optional `diagnostic` string that is
**either** one of the current step's catalog codes **or** `null` when the student
is on track (action would be `advance`) or when no catalog code fits
(`GEN_other`).

- ic new shape: `{"action": ..., "objectives_met": [...], "diagnostic": "<code|null>"}`
- div new shape: `{"action": ..., "diagnostic": "<code|null>"}`

### Parsing
- In each `llm.py`, extend `_parse_control_block` to read `diagnostic`:
  - accept only strings; coerce anything else to `null`;
  - **do not** validate the code against the catalog inside the parser (keep the
    parser dumb); validation/normalization happens in the caller against the
    active step's allowed codes, mapping unknown → `GEN_other`.
- Extend the `tutor_turn` return dict with `diagnostic` (default `None`).
- Extend each fallback path (`_fallback_turn` in div, `_fb_result`/fallback in ic)
  to set `diagnostic=None` (fallback has no real diagnostic capability).
- A missing `diagnostic` key must **not** set `_parse_error`/`control_parse_ok`
  to False — it is optional. Only malformed JSON or a missing `action` triggers
  the existing fallback-to-stay behavior.

### Prompt change
In each system prompt, add a short, explicit section: when `action="stay"` or
`action="retreat_to_prereq"`, the model SHOULD set `diagnostic` to the catalog
code that best names the student's current misconception (codes provided per
step), or `GEN_other` if none fit; when `action="advance"`, set `diagnostic` to
`null`. Provide the allowed codes for the current step inline (the prompt loader
already injects per-step content — extend the template + the loader's
replacements to include the step's catalog codes and their descriptions). Stress
that `diagnostic` is metadata and must appear *inside* the JSON control block,
never in the visible reply.

### Consumers of the new field
1. **Hint selection.** Today hints default to `pistes[0]`. When a `diagnostic`
   is present, prefer a hint mapped to that error. Minimal version: add an
   optional `pistes_per_error: {code: hint}` to steps and fall back to `pistes[0]`
   when absent. Do not over-engineer; `pistes[0]` remains the default.
2. **Instructor reporting.** Record `diagnostic` on each `history` entry. In ic,
   extend `compute_quality_signals` with a `diagnostic_counts` tally and surface
   the most frequent misconception per step in the summary view. In div, show the
   latest/most-frequent diagnostic in the Task 1 inspector panel.

### Acceptance criteria
- [ ] `apply_action` is byte-for-byte unchanged in behavior; flow ignores
      `diagnostic`. (Add a test asserting identical transitions with/without a
      diagnostic present.)
- [ ] Parser tolerates: diagnostic present, absent, null, wrong type, unknown
      code — none of these flip `control_parse_ok` to False on their own.
- [ ] Unknown/out-of-catalog codes normalize to `GEN_other` in the caller.
- [ ] Fallback turns yield `diagnostic=None` and still run end-to-end.
- [ ] `history` entries carry `diagnostic`; ic summary shows per-step misconception
      tally; div inspector shows current diagnostic.
- [ ] Existing test suites pass; new tests added for parsing + flow-invariance.

### Status
- [ ] div: add `error_catalog` + `typical_error_label` to `problems.py`
- [ ] div: extend parser, `tutor_turn`, fallback, prompt
- [x] ic: extend parser, `tutor_turn`, fallback, prompt (catalog already exists)
- [~] both: record `diagnostic` in `history` — **ic done** (app.py + simulator.py); div pending
- [~] both: hint selection prefers diagnostic-mapped hint — **ic done** (fallback path via `pistes_per_error` + `hint_for_diagnostic`); div pending. NB: live-LLM hint selection is driven by the model itself; the deterministic mapping currently applies to the fallback path.
- [x] ic: `diagnostic_counts` in `compute_quality_signals` + summary surfacing (app.py "Malentesos detectats" + CLI line)
- [ ] div: diagnostic shown in inspector
- [x] new tests: parser tolerance + flow invariance (ic: `test_diagnostic.py`, 35 checks)

#### IC implementation notes (for the div pass to mirror)
- `error_catalog` lives on the **bundle** (`PB.PROBLEMS[pid]["error_catalog"]`),
  not on the `problem` dict that `tutor_turn` receives. div's `problems.py` has
  no bundle layer, so place the catalog wherever its accessors can reach it and
  expose the same helper surface.
- New helpers added to ic `problem.py`: `GEN_OTHER`, `error_catalog`,
  `allowed_diagnostics`, `likely_diagnostic_for_step`, `normalize_diagnostic`,
  `hint_for_diagnostic`. The div port should provide equivalents.
- The system prompt is cached per `problem_id` and is **per-problem, not
  per-step**. Allowed diagnostic codes for the *current step* are therefore NOT
  injected into the system prompt (that would break the cache). Instead they are
  appended as a second line of the **position marker** (which is already
  prepended to the last user message every turn). div has an analogous marker in
  `llm._format_position_marker`-equivalent; inject codes there.
- Validation point is the caller (`tutor_turn` → `PB.normalize_diagnostic`); the
  parser stays dumb. `action="advance"` forces `diagnostic=None`.
- Fallback (`_fb_result`) gained an optional `diagnostic` arg (default `None`);
  stay-paths pass the step's `typical_error_label` so the instructor panel isn't
  empty offline.

---

## Suggested execution order

1. Task 1 on ic (smallest, proves the trace plumbing).
2. Task 1 on div (also consolidates `?debug`).
3. Task 2 (div adopts ic's card system; ic regression-checked).
4. Task 4 on ic (catalog already present — wire it through).
5. Task 4 on div (introduce catalog, then wire identically).

After each step: run that project's test suite, do a manual offline (fallback)
pass and, if a key is available, one live pass. Update the Status checkboxes in
this file as work completes.

## Talk narrative these tasks must support

- Task 2 → "same architecture, two domains."
- Task 1 → "the flow is deterministic and auditable; the LLM only emits an action."
- Task 4 → "we don't grade answers, we classify misconceptions."
