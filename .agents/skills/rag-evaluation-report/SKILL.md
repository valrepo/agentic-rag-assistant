---
name: rag-evaluation-report
description: >-
  Produce an honest Markdown evaluation report of the Agentic RAG Knowledge Assistant
  (retrieval, generation, task outcome, agent workflow, operations, safety/privacy) from the
  project specs, test results, evaluation dataset and results, configuration, and available
  Langfuse trace summaries. Invoked only when the user explicitly requests an evaluation
  report, after the application has been implemented and tested.
user-invocable: true
disable-model-invocation: true
argument-hint: "[optional: path to evaluation results or Langfuse trace export]"
---

# RAG Evaluation Report

> Draft. The full skill (reference files, report template, deterministic scripts,
> self-check, fixtures) is built during implementation as required by SK-004 to SK-011 in
> `specs/spec.md`. Until then, this file only fixes the scope and the honesty rules.

## When this skill runs

- This skill is invoked **only when the user explicitly requests an evaluation report**
  (for example by typing `/rag-evaluation-report`).
- It MUST NOT run automatically during coding, file upload, indexing, or question answering,
  and MUST NOT be triggered by another skill or agent.
- It is meant to run after the application has been implemented and the automated tests and
  the evaluation dataset have been run. If they have not, say so in the report instead of
  running the application yourself.

## Golden rule: never fabricate

- Every number in the report MUST come from a file or trace you actually read in this run.
  Cite the source path (or trace id) next to each value.
- If a metric cannot be computed from the available evidence, write **unavailable**, state
  why (missing data, missing instrumentation, missing human labels, no Langfuse access), and
  explain how to collect it.
- Do not estimate, extrapolate, or "typical value" any metric. Do not invent Langfuse traces,
  trace ids, latencies, token counts, or costs.
- If two sources disagree, report both and flag the inconsistency.

## Step 1 - Collect evidence

Read what exists; record what is missing. Do not modify any of these files.

| Evidence | Where to look |
|---|---|
| Constitution | `specs/constitution.md` |
| Specification, plan, tasks | `specs/spec.md` (including the evaluation data contract EV-001 to EV-006, the skill requirements SK-001 to SK-011, the metric catalogue MC-001 to MC-032, and the Evaluation Methodology EM-001 to EM-007), `specs/plan.md`, `specs/tasks.md` |
| Evaluation dataset | `evaluation/questions.jsonl`, `evaluation/expected_answers.jsonl` |
| Evaluation run results | `evaluation/results/`, or the path given as argument; note for each file whether it comes from the fake model or a real model |
| Automated test results | `reports/test-results/` |
| Application configuration | `.env.example`, `pyproject.toml`, configuration module defined in `plan.md` (never read or print `.env` values) |
| Langfuse trace summaries | `reports/langfuse/`, the path given as argument, or, if Langfuse credentials are configured in the environment, read-only queries through the `langfuse` skill |

For each source, note: found / not found, path, timestamp, and number of records.

## Step 2 - Decide which metrics apply

Go through the catalogue below. For each metric decide: **measured** (value computed from
evidence), **unavailable** (applicable but not computable now), or **not applicable**
(explain why). Use the definitions given; if `k` is used, state its value from configuration.

Apply the metric catalogue (MC-001 to MC-032) and the Evaluation Methodology (EM-001 to EM-007) in `specs/spec.md`. In short:

- Primary metric: correctness against expected answer points (MC-014). Guardrails:
  unsupported-claim rate, abstention quality, citation validity, end-to-end latency,
  tokens. Say which decision each metric supports.
- Correctness is judged on answer points, never on word overlap (no BLEU/ROUGE as
  correctness).
- Deterministic script metrics first; metrics that need judgement come only from the human
  labels in `evaluation/labels/`. No LLM judge in this version.
- Below 10 questions, write rates as counts ("3/4") and call results indicative. Latency as
  median and maximum (p95 only when n is at least 20), never a mean alone.
- Report per question category (answerable, unanswerable, multi-source) and overall; never
  mix fake-model and real-model runs; say if the evaluation questions were used for tuning.

**Retrieval** (needs, per question, the ranked retrieved chunks and the expected sources)

- Recall@k: share of expected source documents found in the top k.
- Precision@k: share of the top k chunks that come from an expected source.
- Hit Rate@k: share of answerable questions with at least one expected source in the top k.
- MRR: mean of 1 / rank of the first relevant chunk (0 if none).
- nDCG@k: discounted cumulative gain of relevant chunks, normalized by the ideal ranking.
- Context relevance: share of retrieved chunks judged relevant to the question (needs a
  human passage labels).
- Chunk coverage: share of expected answer points supported by at least one retrieved chunk.

**Generation / RAG quality**

- Faithfulness / groundedness: share of answer claims supported by the retrieved chunks.
- Answer relevance: whether the answer addresses the question (human rating).
- Context utilization: share of retrieved relevant chunks actually used (cited) in the answer.
- Citation correctness: share of citations pointing to a retrieved chunk that supports the
  cited claim.
- Citation completeness: share of supported claims that carry a citation.
- Unsupported-claim rate: share of answer claims with no supporting retrieved chunk.

**Task outcome**

- Correctness against expected answer points: points covered / points expected, per
  question and overall.
- Abstention quality: unanswerable questions correctly answered with the safe "not found"
  response, and answerable questions wrongly refused.
- Human preference or rubric score: only if human ratings exist.

**Agent workflow** (mostly from Langfuse traces)

- Task success rate, tool/retrieval failure rate, number of retries, trace completeness
  (share of runs whose trace contains every required observation), step latency,
  end-to-end latency, cost/token usage.

**Operations**

- Upload success rate, indexing latency, query throughput, error rate, resource usage.

**Safety / privacy**

- Prompt-injection detection rate (needs injection test cases), data leakage checks, secret
  exposure (scan traces, logs, and tracked files for keys), PII handling.

## Step 3 - Compute

- Compute only from the collected evidence. Show the formula and the inputs (counts) for
  each measured value, so the reader can recompute it.
- Report per-question results for the evaluation dataset (question id, category, expected
  sources, retrieved sources, cited sources, abstained or not, points covered).
- State numerator and denominator for every rate. Below 10 questions, use counts and say
  results are indicative; never declare two runs different on fewer than 10 questions.
- Distinguish runs made with a deterministic fake model from runs made with a real model;
  never mix them in one metric.

## Step 4 - Write the report

Write `reports/rag-evaluation-report.md` (create `reports/` if needed; overwrite a previous
report only after telling the user). Use this structure and plain text only (no emojis):

1. **Summary**: date, application version/commit, model and embedding configuration (names
   only, no secrets), what was evaluated, headline findings.
2. **Evidence inventory**: table of sources found / missing with paths and record counts.
3. **Metrics**: start with the primary metric and its guardrails, then one table per family
   with columns Metric | Status (measured / unavailable / not applicable) | Value | Sample
   size | Source | Decision supported | How to collect (if unavailable).
4. **Per-question results** for the evaluation dataset.
5. **Langfuse observations**: trace ids used, completeness of traces, latency and token
   figures as read (or "unavailable" with the reason).
6. **Limitations**: dataset size, fake vs real model, label reliability, non-determinism.
7. **Data-quality concerns**: sample knowledge, expected answers, labelling issues.
8. **Privacy and security considerations**: what is traced and logged, secret scan result,
   PII handling.
9. **Recommended next experiments**: concrete, prioritized, each tied to an unavailable or
   weak metric.

## Step 5 - Hand back

Tell the user the report path, how many metrics were measured versus unavailable, and the
most important missing instrumentation. Do not claim more than the report contains.
