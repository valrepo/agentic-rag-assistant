# Metric catalogue (MC-001 to MC-032)

Source of truth: `specs/spec.md`, section "Metric catalogue". The script
`scripts/compute_metrics.py` implements every formula; this table must list the same ids and
names (checked by `tests/skill/test_compute_metrics.py`).

Conventions:

- Population: retrieval metrics (MC-001 to MC-005) and MC-010 use the questions whose
  `expected_behavior` is `answer`; the unanswerable question is covered by MC-015.
- Retrieved list: the up to k chunks of `retrieved`, before the minimum-score filter.
  Missing positions count as non-relevant; Precision@k always divides by k.
- Relevance is binary at document level: a chunk is relevant if its `file` is in the
  question's `expected_sources` (optimistic, see `methodology.md`).
- Averaged metrics are macro averages of per-question values; the metrics file stores the
  per-question values and n. Questions with a zero denominator are excluded and listed.

| Id | Family | Metric | Formula | Evidence | Default status | Decision supported |
|---|---|---|---|---|---|---|
| MC-001 | Retrieval | Hit Rate@k | questions with at least one relevant chunk / questions | results, expected answers | measured (script) | tune k, chunking, or the embedding model |
| MC-002 | Retrieval | Recall@k (document level) | per question: expected sources retrieved / expected sources; averaged | results, expected answers | measured (script) | tune k or chunking |
| MC-003 | Retrieval | Precision@k | per question: relevant chunks / k; averaged | results, expected answers | measured (script) | lower k or raise the minimum relevance score |
| MC-004 | Retrieval | MRR | per question: 1 / rank of first relevant chunk, 0 if none; averaged | results, expected answers | measured (script) | change the embedding model or add reranking |
| MC-005 | Retrieval | nDCG@k | DCG = sum rel(i) / log2(i + 1); ideal places min(k, R) relevant chunks first, R = indexed chunks of the expected sources; averaged | results, header, expected answers | measured (script) | compare retrieval configurations |
| MC-006 | Retrieval | Context relevance | retrieved chunks relevant at passage level / retrieved chunks | passage labels | unavailable | tune the minimum relevance score |
| MC-007 | Retrieval | Chunk coverage | answer points supported by a retrieved chunk / answer points | point-to-chunk labels | unavailable | change chunk size or overlap |
| MC-008 | Generation | Faithfulness / groundedness | per answered question: claims_supported / claims_total; averaged | human labels | measured (human labels) | strengthen the guardrail or prompts |
| MC-009 | Generation | Answer relevance | mean answer_relevance (1 to 5) | human labels | measured (human labels) | revise the Answer/Verifier task |
| MC-010 | Generation | Context utilization | per question: relevant retrieved chunks cited / relevant retrieved chunks; averaged; plus answered questions citing an expected source | results, expected answers | measured (script) | revise the citation instructions |
| MC-011 | Generation | Citation correctness | (a) draft citations in the retrieved list / draft citations, and total citations_removed; (b) citations_supporting / citations_checked | results; human labels | (a) measured (script); (b) measured (human labels) | strengthen the citation guardrail |
| MC-012 | Generation | Citation completeness | per answered question: (claims_supported - uncited_supported_claims) / claims_supported; averaged | human labels | measured (human labels) | require a citation per statement |
| MC-013 | Generation | Unsupported-claim rate | per answered question: 1 - faithfulness; averaged | human labels | measured (human labels) | strengthen the guardrail or change model |
| MC-014 | Task outcome | Correctness against answer points | per answer-expected question: points_covered / answer_points; abstention or failure counts 0; averaged (primary metric) | human labels, expected answers | measured (human labels) | release or change model |
| MC-015 | Task outcome | Abstention quality | four counts: correct abstentions, correct answers, wrong refusals, unsupported answers; value = correct decisions / questions | results, expected answers | measured (script) | tune the minimum relevance score or prompts |
| MC-016 | Task outcome | Human rubric score | mean rubric_score (1 to 5) | human labels | measured (human labels) | compare releases with a human view |
| MC-017 | Agent workflow | Task success rate | questions answered or abstained / questions | results | measured (script) | fix failing steps before tuning quality |
| MC-018 | Agent workflow | Tool / retrieval failure rate | questions failed at retrieval / questions | results | measured (script) | fix the retrieval tool or store |
| MC-019 | Agent workflow | Number of retries | sum and per-question retry_count (LLM calls beyond the two expected) | Langfuse exports | measured (script) if exports contain retry_count | tune structured-output prompts or model |
| MC-020 | Agent workflow | Trace completeness | questions whose export exists with every presence flag true / questions | results, Langfuse exports | measured (script) if exports exist | fix instrumentation gaps |
| MC-021 | Agent workflow | Step latency | median and maximum duration_ms per step name | Langfuse exports | measured (script) if exports exist | find the slowest step |
| MC-022 | Agent workflow | End-to-end latency | median and maximum latency_ms; p95 only when n is at least 20; value = maximum | results | measured (script) | choose model size or hardware |
| MC-023 | Agent workflow | Cost / token usage | total and per-question prompt and completion tokens; cost only from Langfuse cost fields | results, Langfuse exports | measured (script); cost unavailable without Langfuse cost | shorten prompts or reduce k |
| MC-024 | Operations | Upload success rate | sample files indexed / sample files submitted | run header | measured (script) | fix parsing of failing files |
| MC-025 | Operations | Indexing latency | per-file duration_ms and total_indexing_ms (value) | run header | measured (script) | batch embeddings or change model |
| MC-026 | Operations | Query throughput | questions per minute under load | not instrumented | unavailable | size hardware for concurrent users |
| MC-027 | Operations | Error rate | questions failed / questions (MC-017 = 1 - MC-027) | results | measured (script) | fix failing steps before tuning quality |
| MC-028 | Operations | Resource usage | CPU and memory during indexing and answering | not instrumented | unavailable | size hardware |
| MC-029 | Safety / privacy | Prompt-injection detection rate | injection cases handled safely / injection cases | needs injection test cases | unavailable | harden prompts and guardrail |
| MC-030 | Safety / privacy | Data leakage checks | answers containing content from outside the retrieved chunks | needs dedicated test cases | unavailable | harden the guardrail |
| MC-031 | Safety / privacy | Secret exposure | findings of the secret scan over tracked files and exports (file, line, pattern name) | evidence manifest | measured (script) | remove and rotate exposed secrets |
| MC-032 | Safety / privacy | PII handling | text: what personal data is traced, logged, and stored | specs, configuration | not applicable (reported as text) | decide what may be traced and logged |

A metric whose evidence is missing for the selected run is "unavailable", whatever its
default status; its `collection_plan` in the metrics file says how to collect it.
