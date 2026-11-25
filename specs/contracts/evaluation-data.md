# Contract: Evaluation data files

Interface between the application (evaluation runner, trace export) and the
`rag-evaluation-report` skill. Implements EV-002, EV-003, EV-005, EV-006. All files are UTF-8
JSON Lines (one JSON object per line) unless stated otherwise. Unknown extra fields are
allowed and ignored; a missing required field makes the dependent metrics "unavailable"
(SK-009).

## evaluation/questions.jsonl (EV-002)

| Field | Type | Required |
|---|---|---|
| id | str, unique, for example `q1` | yes |
| category | `answerable`, `unanswerable`, `multi_source` | yes |
| question | str | yes |

```json
{"id": "q4", "category": "unanswerable", "question": "What is the company's parental leave policy?"}
```

## evaluation/expected_answers.jsonl (EV-002)

| Field | Type | Required |
|---|---|---|
| id | str, joins questions.jsonl | yes |
| expected_behavior | `answer` or `abstain` | yes |
| answer_points | list of `{point_id: str, text: str}`; empty when `abstain` | yes |
| expected_sources | list of original file names; empty when `abstain` | yes |

## evaluation/results/<run_id>.jsonl (EV-003)

Line 1 is the header (`"record": "header"`); each following line is one question
(`"record": "question"`).

Header:

| Field | Type |
|---|---|
| record | `"header"` |
| run_id | str, `YYYYMMDDTHHMMSSZ-<model_kind>` |
| started_at | ISO-8601 UTC |
| git_commit | str; suffix `-dirty` if the working tree had changes |
| model | str, for example `ollama/llama3.1:8b` or `stub` |
| model_kind | `fake` or `real` |
| embedding_model | str |
| k | int |
| chunk_size, chunk_overlap | int |
| min_relevance_score | float |
| langfuse_enabled | bool |
| indexing | list of `{file, status, chunk_count, duration_ms}` (`file` = original name) |
| total_indexing_ms | int (embedding model download excluded) |

Question record:

| Field | Type | Required when |
|---|---|---|
| record | `"question"` | always |
| id | str | always |
| request_id | str | always |
| status | `answered`, `abstained`, `failed` | always |
| error_stage | `retrieval`, `answer`, `guardrail`, `other` | status = failed |
| error_type | str | status = failed |
| retrieved | list of `{rank, file, chunk_id, score, above_min_score}`, up to k, before the minimum-score filter | always (empty if retrieval failed) |
| answer | str | status != failed |
| draft_cited_chunk_ids | list of str | status != failed |
| cited_chunk_ids | list of str | status != failed |
| citations_removed | int | status != failed |
| guardrail_decision | `passed`, `citations_removed`, `safe_response` | status != failed |
| latency_ms | int | always |
| prompt_tokens, completion_tokens | int or null | when the provider reports usage |
| trace_id | str or null | when Langfuse is enabled |

## reports/langfuse/<run_id>/<trace_id>.json (EV-005)

Single JSON object per trace, written by `scripts/export_traces.py`:

| Field | Type |
|---|---|
| trace_id, request_id, model | str |
| observations | list of `{name, type, status, duration_ms, prompt_tokens, completion_tokens, cost}` (numbers may be null) |
| retry_count | int or null |
| presence | object of booleans: `has_question`, `has_request_id`, `has_agent_task_spans`, `has_retrieval_metadata`, `has_generation_io`, `has_model_name`, `has_token_usage`, `has_latency_and_status`, `has_error_if_failed` |
| exported_at | ISO-8601 UTC |

No credential, API key, or raw HTTP header may appear in these files.

## evaluation/labels/<run_id>.jsonl (EV-006, optional)

One record per question with status `answered`:

| Field | Type |
|---|---|
| id | str |
| points_covered | list of point_id |
| claims_total, claims_supported, uncited_supported_claims | int >= 0, `claims_supported <= claims_total` |
| citations_checked, citations_supporting | int >= 0, `citations_supporting <= citations_checked` |
| answer_relevance, rubric_score | int 1..5 |
| labeller | str (initials or role, no personal data) |

The skill writes an empty template to `evaluation/labels/<run_id>.template.jsonl`; only the
file without `.template` is read.
