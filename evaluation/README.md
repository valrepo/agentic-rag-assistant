# Evaluation data

Data contract: `specs/contracts/evaluation-data.md` (EV-002 to EV-006).

| Path | Content | Written by |
|---|---|---|
| `questions.jsonl` | 5 questions: `id`, `category` (`answerable`, `unanswerable`, `multi_source`), `question` | project (fixed) |
| `expected_answers.jsonl` | expected behavior, answer points (the rubric), expected source files | project (fixed) |
| `results/<run_id>.jsonl` | one header record and one record per question | `scripts/run_evaluation.py` |
| `labels/<run_id>.jsonl` | optional human labels for one run | you, from the template |
| `labels/<run_id>.template.jsonl` | empty label template for the latest real run | the evaluation skill |

The questions cover the three sample documents in `data/sample-knowledge/`: one question per
document (`q1` to `q3`), one question the documents cannot answer (`q4`, expected safe
response), and one question that needs two documents (`q5`, monitoring guide and runbook).

## Fake and real runs

Two kinds of run exist and are never mixed in one metric:

- `--model-kind fake`: deterministic extractive fake model and lexical fake embeddings
  (`tests/fakes/`), no network, Langfuse disabled. It checks the pipeline and the data
  contract; its answers say nothing about answer quality.
- `--model-kind real`: the configured model (default `ollama/llama3.1:8b`), the local ONNX
  embeddings, and Langfuse enabled. This is the run the evaluation report is about.

Each run indexes the sample knowledge into its own empty knowledge base under
`storage/eval-runs/` (git-ignored), so it never touches the knowledge base of the UI.

```sh
uv run python scripts/run_evaluation.py --model-kind fake
uv run python scripts/run_evaluation.py --model-kind real
uv run python scripts/export_traces.py --run <run_id of the real run>
```

`export_traces.py` reads Langfuse (read-only) and writes one summary per trace to
`reports/langfuse/<run_id>/`. Langfuse ingests traces asynchronously: the export waits until
each trace has its root observation and a stable number of observations, and lists the
traces that are still missing or partial; rerun the export for those. `retry_count` in an export is the
number of LLM calls beyond the two expected per question (one retriever call, one answer
call), for example a structured-output retry.

## Tuning disclosure (EM-007)

`MIN_RELEVANCE_SCORE` was tuned on these evaluation questions, so retrieval and abstention
results are optimistic. On a real run with the ONNX embeddings (2026-11-25), the best chunk
of every expected source scored 0.40 or more for `q1`, `q2`, `q3`, and `q5`, and the best
chunk for `q4` scored 0.08. The threshold was raised from the starting value 0.30 to 0.35:
the highest value that keeps every expected source above it, which also drops more
off-topic chunks. Prompts were not tuned on these questions.

## Human labels (optional, EV-006)

Metrics that need judgement (faithfulness, answer relevance, correctness against answer
points, citation support) are measured only from human labels. After the evaluation skill
has written `labels/<run_id>.template.jsonl`, copy it to `labels/<run_id>.jsonl` and fill
one record per answered question:

| Field | Meaning |
|---|---|
| `points_covered` | `point_id` values of `expected_answers.jsonl` that the answer states correctly |
| `claims_total` | statements presented as fact in the answer |
| `claims_supported` | of those, statements supported by the cited or retrieved chunks |
| `uncited_supported_claims` | supported statements without a citation |
| `citations_checked` | citations you checked |
| `citations_supporting` | checked citations whose chunk supports its statement |
| `answer_relevance`, `rubric_score` | 1 (poor) to 5 (excellent) |
| `labeller` | initials or role only, no personal data |

Then invoke `/rag-evaluation-report` again.
