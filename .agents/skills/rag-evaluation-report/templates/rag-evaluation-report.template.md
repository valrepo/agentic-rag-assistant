# RAG evaluation report

<!--
How to fill this template (delete every comment when done):
- Copy values only from reports/rag-evaluation-metrics.json and
  reports/rag-evaluation-evidence.json. Never compute, estimate, or round a value.
- Write "-" for a missing value. Plain text only, no emojis.
- Refer to questions by id and to sources by file name; quote questions only, never answers
  or chunk text.
- Ids, paths, and field names go in backticks.
- Run scripts/check_report.py and fix the report until it passes.
-->

## 1. Summary

<!-- Date of the report, selected run id, model, embedding model, k, minimum relevance
score, commit. If metrics.run.run_id is null, start with: "No real-model run exists: every
real-run metric is unavailable." Then list metrics.run.staleness entries, if any, as
warnings. Then counts of metrics by status and the headline findings, each with its metric
id. State that the sample is small and results are indicative. -->

## 2. Evidence inventory

<!-- One row per entry of evidence.files: path, found or missing, records, modified at.
Also: .env present (yes or no, never its content), label template written (path or none). -->

| Path | Found | Records | Modified at |
|---|---|---|---|

## 3. Primary metric and guardrails

<!-- metrics.primary_metric (MC-014) first, then each id of metrics.guardrail_metrics, one row
each, with status, value (or numerator/denominator for rates), n, and decision supported.
For unavailable ones, say why and how to collect. -->

| Role | Id | Metric | Status | Value | n | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|

## 4. Metric tables

<!-- One table per family, in catalogue order: Retrieval, Generation, Task outcome, Agent
workflow, Operations, Safety / privacy. All 32 ids must appear. For rates, write the
value as "numerator/denominator" and also the value field. For averaged metrics, write the
value and n; per-question values may follow the table. Unavailable rows: Value "-" and a
non-empty How to collect. Then, for each family with per_category values, a short table
per category. State under the Retrieval table that relevance is judged at document level
(optimistic, EM-002). -->

### Retrieval

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|

### Generation

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|

### Task outcome

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|

### Agent workflow

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|

### Operations

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|

### Safety / privacy

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|

## 5. Test results

<!-- From metrics.tests: passed, failed, skipped, duration, then the FR-035 area table
(area, test modules, passed, failed). If tests.available is false, say the JUnit file is
missing. -->

| Passed | Failed | Skipped | Duration (s) |
|---|---|---|---|

| FR-035 area | Test modules | Passed | Failed |
|---|---|---|---|

## 6. Success criteria

<!-- From metrics.success_criteria: id, target, measured, verdict, metric. -->

| Id | Target | Measured | Verdict | Metric |
|---|---|---|---|---|

## 7. Per-question results

<!-- From metrics.run.per_question: id, category, status, expected sources, retrieved files,
cited files, guardrail decision, citations removed, latency. File names and ids only. -->

| Id | Category | Status | Expected sources | Retrieved files | Cited files | Guardrail | Removed | Latency (ms) |
|---|---|---|---|---|---|---|---|---|

## 8. Langfuse observations

<!-- Trace ids of the selected run (from metrics.run.per_question), MC-020 trace
completeness, MC-021 step latencies (step, median, max, n), MC-019 retries, MC-023 token
totals and cost status. If exports are missing, say so and give the collection plan. -->

## 9. Fake-model runs

<!-- From metrics.fake_runs: run ids and their script metrics, clearly labelled as fake-model
results that say nothing about answer quality. They never appear elsewhere in the report. -->

## 10. Provenance

<!-- One row per measured value reported in sections 3 to 6: metric id, value, source file,
record or trace id, field. -->

| Metric | Value | Source file | Record or trace | Field |
|---|---|---|---|---|

## 11. Limitations

<!-- Dataset size and indicative results (EM-005), document-level relevance (EM-002),
real model non-determinism, approximate prompt token counts for local models, labels from
one labeller if any, tuning on the evaluation questions (EM-007, see evaluation/README.md). -->

## 12. Data-quality concerns

<!-- Sample knowledge written for the project, few answer points per question, expected
sources at document level, missing or partial labels, stale run (metrics.run.staleness). -->

## 13. Privacy considerations

<!-- MC-031 secret scan result (file, line, pattern name only), MC-032 PII handling as text
(see references/privacy.md), .env never read. -->

## 14. Recommended next experiments

<!-- Concrete and prioritized; each tied to an unavailable or weak metric id and to the
decision it would support. -->
