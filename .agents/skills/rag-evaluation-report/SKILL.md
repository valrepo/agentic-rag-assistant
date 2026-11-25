---
name: rag-evaluation-report
description: >-
  Produce an honest Markdown evaluation report of the Agentic RAG Knowledge Assistant
  (retrieval, generation, task outcome, agent workflow, operations, safety/privacy) from the
  project specs, test results, evaluation dataset and results, human labels, configuration,
  and exported Langfuse trace summaries. Invoked only when the user explicitly requests an
  evaluation report, after the application has been implemented and tested.
user-invocable: true
disable-model-invocation: true
argument-hint: "(no argument: the latest real-model run in evaluation/results/ is used)"
---

# RAG Evaluation Report

## When this skill runs

- Only when the user explicitly requests an evaluation report, for example by typing
  `/rag-evaluation-report`.
- Never automatically during coding, file upload, indexing, or question answering, and never
  triggered by another skill or agent.
- It runs after the application has been implemented and the automated tests and the
  evaluation runs have been made by the developer. If evidence is missing, report it as
  missing; do not produce it yourself.

## Golden rules

1. **Never fabricate.** Every number in the report comes from
   `reports/rag-evaluation-metrics.json` or `reports/rag-evaluation-evidence.json`, written
   by the scripts below. Never compute, estimate, extrapolate, or round a value yourself
   (SK-005). Never invent a trace id, latency, token count, or cost.
2. **Unavailable is an answer.** A metric without evidence is "unavailable", with the reason
   and the collection plan from the metrics file.
3. **Read-only outside `reports/` and `evaluation/labels/`** (SK-007). Do not run the
   application, the tests, `scripts/run_evaluation.py`, or `scripts/export_traces.py`. Do
   not query or write to Langfuse; read only the exports in `reports/langfuse/`. Do not
   commit. Do not open `.env` or any `.env.*` file other than `.env.example`. Do not print
   environment variables or credentials.
4. **Privacy** (SK-011): quote questions if useful, never answers or chunk text; refer to
   questions by id and to sources by file name. Details: `references/privacy.md`.
5. Plain text, no emojis.

## References

- `references/data-contract.md`: the files read and written, and their fields.
- `references/metric-catalogue.md`: MC-001 to MC-032, formulas, default status, decision.
- `references/methodology.md`: EM-001 to EM-007 (primary metric, small samples, slices).
- `references/privacy.md`: read/write limits, secret scan patterns, PII text.
- `templates/rag-evaluation-report.template.md`: the report structure (14 sections).

## Steps

Run the commands from the project root. The scripts use the Python standard library only
(Python 3.11 or later); `uv run python` uses the project interpreter.

### Step 1 - Collect evidence

```sh
uv run python .agents/skills/rag-evaluation-report/scripts/collect_evidence.py --root .
```

Writes `reports/rag-evaluation-evidence.json`: the SK-003 sources (path, existence, size,
modification time, SHA-256, record count), the current commit and dirty flag, whether `.env`
exists (never opened), known trace ids, and the secret scan (file, line, pattern name only).
When the latest real run has no labels, it also writes the empty label template
`evaluation/labels/<run_id>.template.jsonl`; mention it in the report.

### Step 2 - Compute the metrics

```sh
uv run python .agents/skills/rag-evaluation-report/scripts/compute_metrics.py --root .
```

Writes `reports/rag-evaluation-metrics.json`: the selected run (latest real-model run by
`started_at`, other real runs listed, staleness warnings), all 32 metrics with status,
value, numerator and denominator or per-question values and n, per-category slices,
inputs, decision supported, reason, and collection plan; the test summary from the JUnit
file with the FR-035 areas; the success-criteria verdicts; and fake-model runs separately.
`scripts/summarize_langfuse.py` is used by this step to read the trace exports.

### Step 3 - Write the report

Copy `templates/rag-evaluation-report.template.md` to `reports/rag-evaluation-report.md`
(tell the user if a previous report is overwritten) and fill each section by copying values
from the two JSON files, following the guidance comments, then delete the comments.

- If `run.run_id` is null, say first that no real-model run exists; every real-run metric is
  then unavailable (SK-008). If `run.staleness` is not empty, say so in the summary.
- Section 3: the primary metric (MC-014) and its guardrails (MC-013, MC-015, MC-011,
  MC-022, MC-023), each with the decision it supports (EM-001).
- Section 4: one table per family; all 32 ids; rates as "numerator/denominator" (fewer than
  10 questions: counts, not percentages, results indicative, EM-005); latency as median and
  maximum. Add the per-category values (EM-007). State that retrieval relevance is judged at
  document level and is optimistic (EM-002).
- Section 9 is the only place where fake-model run ids and their metrics appear.
- Section 10: one provenance row per value reported in sections 3 to 6 (metric, value,
  source file, record or trace id, field).
- Sections 11 to 14: limitations, data quality, privacy (MC-031 findings, MC-032 text from
  `references/privacy.md`), and next experiments, each tied to an unavailable or weak
  metric. Mention the tuning disclosure of `evaluation/README.md`.

### Step 4 - Self-check

```sh
uv run python .agents/skills/rag-evaluation-report/scripts/check_report.py --root .
```

It fails if a number in sections 3 to 6 or 10 is not in the metrics file, a trace id is not
in the evidence, an unavailable row has a value or no collection plan, a catalogue id is
missing, a fake run id appears outside section 9, answer text is copied, or a section is
missing. Fix the report and run it again until it prints "self-check passed". Never hand
back a report whose self-check fails (SK-006).

### Step 5 - Hand back

Tell the user: the report path, the selected run, how many metrics are measured by script,
measured from human labels, unavailable, and not applicable (count the statuses in the
metrics file listing; do not compute rates), the most important missing evidence and how to
collect it, and whether a label template was written. Do not claim more than the report
contains.
