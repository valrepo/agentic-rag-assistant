# Data Model: Agentic RAG Knowledge Assistant

Phase 1 output of `/speckit-plan`. Entities from the specification (Key Entities, EV-002 to
EV-006), with fields, validation rules, and state transitions. File formats exchanged with
the evaluation skill are specified in [contracts/evaluation-data.md](contracts/evaluation-data.md).

## KnowledgeFile

| Field | Type | Rule |
|---|---|---|
| original_name | str | as uploaded; shown in the UI and used in citations and evaluation joins |
| stored_name | str | sanitized: basename only, characters outside `[A-Za-z0-9._-]` replaced by `_`, at most 120 characters, resolved path inside `DATA_DIR` (FR-033) |
| file_type | enum `txt`, `pdf`, `md` | from the extension, lower case; anything else is rejected (FR-003) |
| size_bytes | int | `0 < size <= MAX_UPLOAD_MB * 1024 * 1024` (FR-004, FR-005) |
| sha256 | str | content hash; duplicate key (FR-009) |
| status | enum | see state machine below |
| reason | str or null | set when rejected or failed |
| chunk_count | int | set when indexed |
| duration_ms | int | parse + chunk + embed + store time |

State machine (FR-006):

```text
received -> processing -> indexed(N chunks)
                       -> rejected(unsupported type | empty file | too large | unreadable)
                       -> failed(indexing error)
received -> indexed, already_present = true (same sha256 found; nothing stored again)
```

Validation order: type, size, readability (parse), emptiness (no non-whitespace text after
parsing).

## Chunk

| Field | Type | Rule |
|---|---|---|
| chunk_id | str | `<sha256[:12]>-<index>`, stable for the same content |
| source_file | str | KnowledgeFile.original_name |
| file_sha256 | str | KnowledgeFile.sha256 |
| index | int | position in the file, from 0 |
| page | int or null | 1-based page for PDF, null otherwise |
| text | str | non-empty; target 800 characters, overlap 120, never across pages |
| embedding | float[384] | stored in the vector store only |

## RetrievedChunk

| Field | Type | Rule |
|---|---|---|
| rank | int | 1..k |
| chunk_id, source_file, page | | from Chunk |
| score | float | 1 - cosine distance, in [-1, 1] |
| above_min_score | bool | `score >= MIN_RELEVANCE_SCORE` |

## AnswerDraft (output of the Answer/Verifier task)

| Field | Type | Rule |
|---|---|---|
| sufficient_evidence | bool | the agent's sufficiency decision (FR-018) |
| statements | list of `{text, chunk_ids}` | each statement presented as fact, with the chunk ids it relies on |
| uncertain | list of str | what is uncertain or missing |

## Answer (after the guardrail)

| Field | Type | Rule |
|---|---|---|
| text | str | the safe response exactly when `status = abstained` |
| statements | list of `{text, citations}` | only statements with at least one valid citation |
| uncertain | list of str | "Uncertain or missing" section, plus statements whose citations were all invalid |
| related_passages | list of chunk refs | only when abstained (optional) |
| draft_cited_chunk_ids | list | all chunk ids proposed in the draft |
| cited_chunk_ids | list | displayed citations (subset of retrieved chunk ids) |
| citations_removed | int | draft citations not in the retrieved list |
| guardrail_decision | enum `passed`, `citations_removed`, `safe_response` | |

Guardrail rules, in order (FR-018, FR-020):

1. No retrieved chunk above `MIN_RELEVANCE_SCORE`, or `sufficient_evidence = false`:
   `safe_response`, status `abstained`.
2. Remove citations whose chunk id is not in the retrieved list; count them.
3. Move statements left without any valid citation to `uncertain`.
4. No statement left: `safe_response`, status `abstained`.
5. Otherwise status `answered`; decision `citations_removed` if step 2 or 3 changed
   anything, else `passed`.

## QuestionRun

| Field | Type | Rule |
|---|---|---|
| request_id | str | random UUID4 hex, generated per question (FR-023) |
| question | str | stripped; non-empty; at most `MAX_QUESTION_CHARS` |
| status | enum `answered`, `abstained`, `failed` | |
| error_stage | enum `retrieval`, `answer`, `guardrail`, `other` or null | set when failed |
| error_type | str or null | exception class name |
| retrieved | list of RetrievedChunk | from the tool's recorded result, not from model text |
| answer | Answer or null | |
| latency_ms | int | end to end |
| prompt_tokens, completion_tokens | int or null | summed over generations when available |
| trace_id | str or null | Langfuse trace id when enabled |

State machine: `started -> retrieving -> answering -> guarding -> answered | abstained`;
any step may go to `failed` with the corresponding `error_stage`.

## Evaluation entities

EvaluationItem (EV-002), EvaluationRun (EV-003), TraceExport (EV-005), LabelSet (EV-006),
EvidenceManifest and MetricsFile (SK-004): see
[contracts/evaluation-data.md](contracts/evaluation-data.md) and
[contracts/evaluation-report-files.md](contracts/evaluation-report-files.md).
