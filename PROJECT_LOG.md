> ⚠️ **NOTA HISTÒRICA — DOCUMENT D'UNA ARQUITECTURA ABANDONADA**
>
> Aquest document descriu el desenvolupament d'una arquitectura
> basada en tres classificadors LLM (`judge_step`, `judge_prereq`,
> `generate_hint`) que **es va abandonar el 24/05/2026**. El sistema
> actual usa una arquitectura conversacional amb **una sola crida**
> al model per torn (`tutor_turn`).
>
> Es conserva aquest registre per a posteritat metodològica: il·lustra
> com una sèrie d'optimitzacions ben argumentades sobre una
> arquitectura equivocada pot degradar el resultat global. Veure
> `README.md` per a la descripció del sistema actual i `CHANGELOG.md`
> per a la transició.

---

# Iterative Refinement of an LLM-as-Judge Classifier — Project Log

**Audience:** another LLM picking up the project, or a human researcher.
**Purpose:** document the development trajectory of an LLM-based classifier
for a Socratic tutoring system, including what was found, what was fixed,
and what remains open.

---

## Context

`tutor-ic` is a minimal Socratic tutor (Python + Streamlit + Gemini 2.5 Flash
via API) for teaching the frequentist interpretation of confidence intervals.
The system targets one problem with three sequential steps and one
prerequisite micro-exercise. The pedagogically critical component is a
single LLM call that classifies each student response into one of three
verdicts:

| Verdict          | Meaning                                              | Downstream behavior              |
|------------------|------------------------------------------------------|----------------------------------|
| `correct`        | The student demonstrated the target understanding.   | Advance to the next step.        |
| `typical_error`  | The student attempted reasoning that is wrong.       | Show feedback; offer hint after 2 consecutive failures. |
| `conceptual_gap` | The student lacks foundational concepts.             | Retreat to the prerequisite mini-exercise. |

The relevant safety property is **zero false positives**: the system must
never classify a wrong answer as `correct`. A false positive means the
student advances with an undetected misconception. False negatives
(rejecting a correct answer) are recoverable via a `!text` discrepancy
mechanism the student can use to flag disagreement.

The classification prompt uses temperature 0.2 and `response_mime_type =
"application/json"` to enforce structured output.

---

## Phase 1 — Initial a priori evaluation

### Design

A test suite of 30 cases was authored before any optimization, distributed
across the three steps and three verdict categories:

| Verdict          | Cases | Source                                          |
|------------------|------:|--------------------------------------------------|
| `correct`        |    12 | Canonical paraphrases (provided by the teacher) |
| `typical_error`  |    12 | The classic frequentist misinterpretation in various forms |
| `conceptual_gap` |     6 | Explicit confessions of not understanding       |

Each case is a tuple `(step_id, input, expected_verdict)` with optional
`expected_error_label` and tags for stratification.

The eval runner (`eval_runner.py`) invokes the real `judge_step` function
(no mocking, no fixtures) for each case, with **three repetitions per
case** to measure inter-run variance. Total: 90 API calls per full run,
≈2 minutes wall clock, ≈€0.01 with Gemini Flash.

Critically, the runner distinguishes the two error directions:

- **False positive:** `expected ∈ {typical_error, conceptual_gap}` but `got = correct` → pedagogically unacceptable.
- **False negative:** `expected = correct` but `got ∈ {typical_error, conceptual_gap}` → recoverable.

### Results

| Metric                                      | Value                |
|---------------------------------------------|---------------------:|
| Overall verdict-level agreement             | 80/88 = **90.9%**    |
| Successful API runs (2/90 hit 503)          | 88                   |
| **False positives**                         | **0**                |
| **False negatives**                         | **0**                |
| Inter-repetition variance                   | essentially zero     |

Stratified by step:

| Step | Cases | Successful runs | Verdict matches | Agreement |
|-----:|------:|----------------:|----------------:|----------:|
| 1    |    10 |              29 |              29 |   100.0%  |
| 2    |    10 |              30 |              22 |    73.3%  |
| 3    |    10 |              29 |              29 |   100.0%  |

All eight mismatches were concentrated in step 2 and were all in the same
direction: predicted `typical_error`, classifier returned `conceptual_gap`.
These were structured-but-misguided responses (e.g., "the percentage is
approximate, not exactly 95%") that the classifier reasonably interpreted
as evidence of missing foundational concepts rather than as a categorized
error. This is a taxonomy disagreement, not a safety failure.

### Conclusion of Phase 1

The classifier was robust against the failure modes anticipated by the
suite designer. Zero false positives and zero false negatives across 88
real API runs is a strong signal — but it only tells us the classifier
handles the cases we thought to write.

---

## Phase 2 — Stress test discovers a new failure mode

### Setup

In a live demo session, the teacher entered minimal, keyword-only
responses to probe the classifier's behavior at the boundary. These
responses were not in the eval suite and represent a category the
suite designer had not anticipated.

### Discovery

Three classification calls produced false positives:

| Step | Student input (Catalan)                          | Translation                                 | Verdict |
|-----:|--------------------------------------------------|---------------------------------------------|---------|
|   1  | `si repetim el mostreig moltes vegades`          | "if we repeat the sampling many times"      | `correct` |
|   2  | `mu és constant`                                 | "mu is constant"                            | `correct` |
|   3  | `tinc una confiança del 95%`                     | "I have a 95% confidence"                   | `correct` |

Each response contains a keyword pertinent to the step's correct answer
but does **not** apply that keyword to the question asked:

- Step 1 asks "probability of *what*, exactly?" — the student gestures
  at "repetition" without saying what happens upon repetition (i.e.,
  that 95% of constructed intervals contain μ).
- Step 2 asks "*why* is the sentence wrong?" — the student gives the
  premise ("μ is constant") without the inference ("therefore the
  probability statement is ill-defined").
- Step 3 asks "give a *correct* interpretation" — the student utters
  the keyword "confidence" without an object: confidence about what?
  about which interval? about μ?

### The diagnostic tell

The classifier's own `reason` field gave the failure mode away. In each
of the three false-positive cases, the model's justification *contained
the explanation the student had not provided*:

> Step 1 reason: "Very good! You've identified the key: the repetition
> of sampling. **The 95% refers to the proportion of intervals that
> would contain the true parameter if we repeated the process many
> times.**"

The bolded portion is what the student *should have said* and did not.
The classifier was completing the student's reasoning silently and then
grading the completion. This is the LLM-as-judge analogue of charitable
interpretation gone too far.

### Asymmetry observation

The same session produced equally short responses in the *negating*
direction, and these were rejected:

- Step 2: `95% no és de la mu` ("95% is not about mu") → `conceptual_gap`
- Step 2: `la mitjana no és probable que estigui allà` ("the mean is not probable to be there") → `conceptual_gap`

These responses contain the correct **negative** content (denying
probability over μ) but lack the keyword the classifier was attending
to. The asymmetry suggests the classifier was performing lexical
match against expected positive keywords rather than evaluating
demonstrated understanding.

### Conclusion of Phase 2

The eval suite achieved 100% within its categories but had not exercised
a category that turned out to exist: keyword-only responses. The
classifier failed exactly the safety property (no false positives) the
system is supposed to enforce. The cost of discovery was a single
five-minute live session.

---

## Phase 3 — Refinement: new category, new rule, new contraexemples

### New error category

A new entry was added to `ERROR_CATALOG` in `problem.py`:

```python
"KEY_only": (
    "Keyword response: contains a correct term (constant, fixed, "
    "parameter, confidence, repetition, procedure...) but does not "
    "justify or apply it to the specific question. The student must "
    "develop the reasoning: explain WHAT the term means in this context "
    "and WHY it answers the question."
),
```

### Strengthened classification prompt

The relevant section of `_SYSTEM_JUDGE` was rewritten. Three changes:

**1. The definition of `correct` now requires auto-sufficiency:**

> A `correct` response is one whose interpretation is frequentist-correct
> *and self-sufficient*. A self-sufficient response contains both
> (a) the key concept relevant to the step (μ fixed/constant, repetition
> of samples, confidence vs. probability...) and (b) its *explicit
> application* to the question asked (what the concept means here, or
> how it answers the question). The response may be concise or informal,
> but both elements (concept + application) must be present *without
> the examiner having to add them*.

**2. A fourth sub-category (d) was added to `typical_error`:**

> (d) KEYWORD-ONLY RESPONSE: contains a pertinent word or phrase
> (constant, fixed, parameter, confidence, repetition, procedure...)
> but does NOT justify or apply it to the specific question.
> Label: `KEY_only`.

**3. Three concrete contraexemples were included in the prompt** (Catalan,
matching the actual language of the system). LLMs respond more
reliably to concrete few-shot examples than to abstract rules. The
contraexemples are the exact false positives from Phase 2:

> Step 1 ("Probability about what?") → "if we repeat sampling many
> times" (has the concept of repetition but does not say what happens
> with repetition)
>
> Step 2 ("Why is it incorrect?") → "mu is constant" (has the concept
> but does not explain why it makes the sentence incorrect)
>
> Step 3 ("Give an interpretation") → "I have a 95% confidence"
> (repeats the step's term without applying it: confidence about
> what? about which interval? about μ?)

**4. A new tiebreaker rule was added:**

> TIEBREAKER 1 (auto-sufficiency): before labeling a response `correct`,
> read it without adding any context. If, to make it "sound correct",
> you would have to introduce the justification or conclusion yourself
> in the `reason` field, it is NOT `correct` — it is `typical_error`
> with `error_label = KEY_only`.

This rule operationalizes the diagnostic tell observed in Phase 2: the
model is asked to introspect on its own behavior. (LLMs are not
reliable introspectors, but combined with the concrete contraexemples
the rule should produce the right behavior in most cases.)

### Expanded evaluation suite

Six new cases were added to `eval_cases.py`, two per step:

| ID         | Input (Catalan)                                  | Expected verdict / label                 |
|------------|--------------------------------------------------|-------------------------------------------|
| S1-KEY-01  | `si repetim el mostreig moltes vegades`          | `typical_error` / `KEY_only`              |
| S1-KEY-02  | `es refereix al procediment`                     | `typical_error` / `KEY_only`              |
| S2-KEY-01  | `mu és constant`                                 | `typical_error` / `KEY_only`              |
| S2-KEY-02  | `perquè és un paràmetre fix`                     | `typical_error` / `KEY_only`              |
| S3-KEY-01  | `tinc una confiança del 95%`                     | `typical_error` / `KEY_only`              |
| S3-KEY-02  | `és una qüestió de confiança, no de probabilitat`| `typical_error` / `KEY_only`              |

The three cases discovered in the live session are tagged
`discovered-in-stress-test` for traceability. The other three are
plausible variants generated by extrapolation from the failure pattern.

The suite now covers 36 cases across four categories (CORR, TYP, KEY, GAP).
At 3 repetitions per case the full run is 108 API calls (≈3 minutes,
≈€0.01).

### Predicted behavior of the next eval run

Before re-running the suite, the following predictions were made
explicitly so that the next eval result can be compared against them:

- **CORRECT (12 cases):** should remain at 100%. The canonical
  paraphrases are all auto-sufficient — they state the concept *and*
  apply it. Risk of regression: low.
- **KEY_only (6 cases):** unknown. This is the metric to watch.
  Anything below 6/6 indicates the new prompt rule did not transfer
  generically and needs more contraexemples or sharper wording.
- **TYPICAL_ERROR (12 cases):** may improve from 77.8% because
  Tiebreaker 2 (structured reasoning → typical_error over
  conceptual_gap) is now more explicit. Risk of regression: low.
- **CONCEPTUAL_GAP (6 cases):** should remain at 100%. The definition
  was not modified.

---

## Phase 4 (postscript) — Second vulnerability discovered: escape valve abuse

During a separate live session, a different failure mode was identified.
The `!text` mechanism allows the student to signal disagreement with a
verdict ("I'm right because ..."). The mechanism is intentionally
permissive — it logs the discrepancy for teacher review and advances
the step without re-evaluating.

A user demonstrated that three consecutive uses of this mechanism
allowed completion of the entire problem with no actual evaluation:

| Step | Input        | Translation         | System behavior                  |
|-----:|--------------|---------------------|----------------------------------|
|   1  | `!tinc raó`  | "I'm right"         | Discrepancy logged, advance      |
|   2  | `!perquè tho dic jo` | "because I say so" | Discrepancy logged, advance |
|   3  | `!patata`    | "potato"            | Discrepancy logged, advance      |

Final state: "🎉 You have completed the problem!"

This is not a classifier issue — the LLM is never called for `!text`
input. The issue is in the policy layer (`app.py`): no minimum content
requirement on the discrepancy payload, no rate limit per session,
no flag for the final state when discrepancies cover all steps.

### Possible mitigations (open)

- Minimum length check on `!text` payload (≥ 20 chars) before accepting.
- Maximum N discrepancies per session (e.g., 1 or 2 of 3 steps).
- If all steps were completed via discrepancy, mark the final state as
  `referred` rather than `solved` and surface a warning in the JSON
  trace for the teacher.
- A teacher-facing JSON field `n_steps_via_discrepancy` quantifying
  abuse.

None of these are implemented yet. They are noted here for the next
iteration of the system.

---

## Reflection on methodology

Three observations stand out from this trajectory.

**First, the eval suite worked exactly as it should — and exactly as
limited as it is.** Phase 1 produced a clean result on the cases it
covered. Phase 2 found a category the suite designer did not
anticipate. Phase 3 expanded the suite to cover the new category.
The eval did not "fail" in Phase 1; it simply did not yet exist for
the new category. The proper development cycle is:

1. design suite → measure → think you're done
2. live test (or adversarial test) → discover blind spot
3. expand suite, rewrite prompt → measure again
4. repeat

**Second, the relevant metric is not overall accuracy.** It is the
*nature* of the errors. Phase 1's 90.9% overall agreement hid no
safety failures; the 8 errors were taxonomic confusions inside the
"wrong" category. Phase 2's 100% overall agreement on the *suite*
hid three live false positives on inputs outside the suite. The
question to ask of an LLM-as-judge is not "what is your accuracy",
it is "what is the worst error you commit", and specifically:
"how often do you accept a wrong answer as correct".

**Third, prompts respond better to examples than to rules.** The
ineffective prompt for KEY_only described the failure abstractly:
"correct responses must be self-sufficient and apply the concept".
The effective prompt includes the three exact false positives as
labeled examples ("here is what NOT to call correct, and what
to call it instead"). This is consistent with the prompt-pattern
literature: pattern-based prompting outperforms description-based
prompting on classification tasks.

A consequence of this last point: when the next failure mode is
discovered (and there will be one), the path of least resistance is
to add the exact failing input as a contraexemple in the prompt,
not to revise the rule architecture. This makes the prompt longer
over time, which is fine until token cost or coherence becomes a
constraint.

---

## Files involved

For an LLM continuing this work, the relevant files are:

| File              | Purpose                                                  |
|-------------------|----------------------------------------------------------|
| `problem.py`      | The single problem, steps, prerequisites, error catalog. Edit `ERROR_CATALOG` to add new error labels. |
| `llm.py`          | Three Gemini calls: `judge_step`, `diagnose_dependency`, `generate_hint`. The `_SYSTEM_JUDGE` constant is where prompt refinements go. |
| `app.py`          | Streamlit UI, session state, escape-valve handling (`?`, `!text`, `!!`), API quota counter, disclaimer gate. The `!text` mitigations from Phase 4 would land here. |
| `eval_cases.py`   | Test suite. Currently 36 cases across CORR / TYP / KEY / GAP. New cases go here, tagged for traceability. |
| `eval_runner.py`  | CLI runner. Computes confusion matrix, separates false positives from false negatives, supports `--repeat N` for variance, outputs JSON for posterior analysis. |

---

## Open work

In rough priority order:

1. Run the eval suite with the new prompt and the 6 new KEY_only cases.
   Verify the predictions above. Iterate the prompt if any KEY_only
   case fails.
2. Implement at least one of the Phase 4 mitigations against `!text`
   abuse.
3. Consider running the suite at higher repetition counts (5–10) to
   measure variance on the borderline cases.
4. Run the suite against a second model (Gemini Pro, Claude Sonnet) for
   cross-model comparison. This is the comparative-precision dimension
   of the research question.
5. Cross-check that the original 30 cases (especially the 4 step-2
   typical_error cases that disagreed in Phase 1) still pass under the
   new prompt. The new prompt has Tiebreaker 2 reinforced, so they may
   now agree.
