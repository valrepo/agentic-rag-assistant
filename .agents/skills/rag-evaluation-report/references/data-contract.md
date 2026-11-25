# Data contract

Source of truth: `specs/spec.md` (EV-002 to EV-006, SK-003, SK-004) and
`specs/contracts/evaluation-data.md`, `specs/contracts/evaluation-report-files.md`.

## Inputs read by the scripts (SK-003)

`scripts/collect_evidence.py` records exactly these paths in the evidence manifest (path,
existence, size, modification time, SHA-256, record count):

| Path | Content |
|---|---|
| `specs/constitution.md`, `specs/spec.md`, `specs/plan.md`, `specs/tasks.md` | project specifications |
| `reports/test-results/junit.xml` | automated test results (JUnit XML) |
| `evaluation/questions.jsonl` | `id`, `category`, `question` |
| `evaluation/expected_answers.jsonl` | `id`, `expected_behavior`, `answer_points`, `expected_sources` |
| `evaluation/results/*.jsonl` | one header record and one record per question per run |
| `evaluation/labels/*.jsonl` | optional human labels (templates are ignored) |
| `.env.example` | configuration variable names (never `.env`) |
| `pyproject.toml` | dependency ranges |
| `reports/langfuse/**/*.json` | trace exports written by `scripts/export_traces.py` |

It also records the current commit, whether the working tree is dirty, whether `.env`
exists (never opened), every known trace id, and the secret scan result.

## Result file (EV-003)

Header: `record` = `header`, `run_id` (`YYYYMMDDTHHMMSSZ-<model_kind>`), `started_at`,
`git_commit` (suffix `-dirty`), `model`, `model_kind` (`fake` or `real`), `embedding_model`,
`k`, `chunk_size`, `chunk_overlap`, `min_relevance_score`, `langfuse_enabled`, `indexing`
(`file`, `status`, `chunk_count`, `duration_ms`), `total_indexing_ms`.

Question record: `record` = `question`, `id`, `request_id`, `status` (`answered`,
`abstained`, `failed`), `error_stage` and `error_type` when failed, `retrieved` (`rank`,
`file`, `chunk_id`, `score`, `above_min_score`), `answer`, `draft_cited_chunk_ids`,
`cited_chunk_ids`, `citations_removed`, `guardrail_decision` (`passed`,
`citations_removed`, `safe_response`), `latency_ms`, `prompt_tokens`, `completion_tokens`,
`trace_id`.

`file` and `expected_sources` use the original uploaded file name (the join key).

## Trace export (EV-005)

`reports/langfuse/<run_id>/<trace_id>.json`: `trace_id`, `request_id`, `model`,
`observations` (`name`, `type`, `status`, `duration_ms`, `prompt_tokens`,
`completion_tokens`, `cost`), `retry_count`, `presence` (`has_question`, `has_request_id`,
`has_agent_task_spans`, `has_retrieval_metadata`, `has_generation_io`, `has_model_name`,
`has_token_usage`, `has_latency_and_status`, `has_error_if_failed`), `exported_at`.

## Labels (EV-006)

`evaluation/labels/<run_id>.jsonl`, one record per answered question: `id`,
`points_covered`, `claims_total`, `claims_supported`, `uncited_supported_claims`,
`citations_checked`, `citations_supporting`, `answer_relevance` (1 to 5), `rubric_score`
(1 to 5), `labeller`. When the latest real run has no labels, `collect_evidence.py` writes
`evaluation/labels/<run_id>.template.jsonl`; only the file without `.template` is read.

## Outputs (written only under `reports/` and `evaluation/labels/`)

| File | Writer |
|---|---|
| `reports/rag-evaluation-evidence.json` | `collect_evidence.py` |
| `reports/rag-evaluation-metrics.json` | `compute_metrics.py` |
| `reports/rag-evaluation-report.md` | the agent, from `templates/rag-evaluation-report.template.md` |
| `evaluation/labels/<run_id>.template.jsonl` | `collect_evidence.py` |

Metrics file: `run` (run id, model, model kind, k, commit, other runs, staleness,
per-question summary), `metrics` (all 32 ids once: `id`, `name`, `family`, `status`,
`value`, `numerator`, `denominator`, `per_question`, `n`, `per_category`, `details`,
`inputs`, `decision`, `reason`, `collection_plan`), `tests`, `success_criteria`,
`fake_runs` (never part of `metrics`), `primary_metric`, `guardrail_metrics`.
