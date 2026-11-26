# RAG evaluation report

## 1. Summary

- Report generated: 2026-11-25, from `reports/rag-evaluation-metrics.json` and
  `reports/rag-evaluation-evidence.json` (clean working tree).
- Selected run: `20261125T231209Z-real`, the latest and only real-model run
  (`evaluation/results/20261125T231209Z-real.jsonl`), started 2026-11-25T23:12:09Z. No
  staleness warning: the run was produced from the current commit with no uncommitted
  change.
- Configuration: model `ollama/llama3.1:8b`, embedding model `chroma-onnx/all-MiniLM-L6-v2`,
  k = 5, minimum relevance score 0.35, Langfuse enabled (Langfuse Cloud).
- Metric statuses: 19 measured (script), 6 measured (human labels), 6 unavailable,
  1 not applicable.
- Human labels: `evaluation/labels/20261125T231209Z-real.jsonl`, one record per answered
  question, labelled by the project author (`labeller` field).
- Headline findings (indicative: the dataset has five questions):
  - Retrieval found an expected source for every question expecting an answer (MC-001),
    always at rank 1 (MC-004).
  - Abstention was correct on every question (MC-015): four answers where an answer was
    expected, one safe response for the unanswerable question.
  - Every draft citation pointed to a retrieved chunk; the guardrail removed none (MC-011).
  - Primary metric, correctness against the expected answer points (MC-014), from the human
    labels: 0.9167 over four questions; the multi-source question `q5` covered two of its
    three points.
  - Every question produced one complete Langfuse trace (MC-020); the maximum end-to-end
    latency was within the target (MC-022, SC-008).

## 2. Evidence inventory

| Path | Found | Records | Modified at |
|---|---|---|---|
| `specs/constitution.md` | yes | - | 2026-11-25T18:48:50Z |
| `specs/spec.md` | yes | - | 2026-11-24T22:46:03Z |
| `specs/plan.md` | yes | - | 2026-11-25T23:11:38Z |
| `specs/tasks.md` | yes | - | 2026-11-25T23:11:38Z |
| `reports/test-results/junit.xml` | yes | 136 test cases | 2026-11-25T23:12:03Z |
| `evaluation/questions.jsonl` | yes | 5 | 2026-11-25T19:58:41Z |
| `evaluation/expected_answers.jsonl` | yes | 5 | 2026-11-25T19:58:41Z |
| fake-model result file in `evaluation/results/` (see section 9) | yes | 6 (header and 5 questions) | 2026-11-25T23:12:07Z |
| `evaluation/results/20261125T231209Z-real.jsonl` | yes | 6 (header and 5 questions) | 2026-11-25T23:13:17Z |
| `evaluation/labels/20261125T231209Z-real.jsonl` | yes | 4 (answered questions) | 2026-11-25T23:14:07Z |
| `.env.example` | yes | - | 2026-11-25T20:02:25Z |
| `pyproject.toml` | yes | - | 2026-11-25T19:48:55Z |
| `reports/langfuse/20261125T231209Z-real/` | yes | 5 trace exports | 2026-11-25T23:13:30Z to 23:13:58Z |

- `.env` present: yes (recorded as present only; never opened).
- Label template: not written, since labels exist for the selected run.
- Trace identifier evidence for a successful question: `reports/langfuse/trace-example.txt`.

## 3. Primary metric and guardrails

| Role | Id | Metric | Status | Value | n | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|
| Primary | MC-014 | Correctness against answer points | measured (human labels) | 0.9167 | 4 | release or change model | - |
| Guardrail | MC-013 | Unsupported-claim rate | measured (human labels) | 0.0 | 4 | strengthen the guardrail or change model | - |
| Guardrail | MC-015 | Abstention quality | measured (script) | 5/5 (1.0) | 5 | tune the minimum relevance score or prompts | - |
| Guardrail | MC-011 | Citation correctness, (a) validity | measured (script) | 8/8 (1.0); citations removed: 0 | 8 | strengthen the citation guardrail | - |
| Guardrail | MC-022 | End-to-end latency | measured (script) | median 15204.0 ms, maximum 15483 ms | 5 | choose model size or hardware | - |
| Guardrail | MC-023 | Cost / token usage | measured (script) | 8888 tokens (prompt 8228, completion 660); cost unavailable | 5 | shorten prompts or reduce k | - |

The script guardrails show no abstention error, no invalid citation, and latency within the
target. The primary metric and the unsupported-claim rate are good on this small sample; the
weakest question is the multi-source one, `q5`, which covered two of its three points.
Per question, MC-014: `q1` 1.0, `q2` 1.0, `q3` 1.0, `q5` 0.6667.

## 4. Metric tables

Rates are written as numerator/denominator with the value in parentheses; with five
questions, results are indicative only (EM-005). Retrieval relevance is judged at document
level: a chunk counts as relevant when its file is an expected source. This is optimistic,
since a chunk from the right file may not contain the answer (EM-002); MC-006 and MC-007
need passage-level labels. Every "measured (human labels)" row below comes from the
label file of the selected run (one labeller, see the limitations section).

### Retrieval

Population: the four questions with an expected answer (`q1`, `q2`, `q3`, `q5`).

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|
| MC-001 | Hit Rate@k | measured (script) | 4/4 (1.0) | 4 | `evaluation/results/20261125T231209Z-real.jsonl`, `evaluation/expected_answers.jsonl` | tune k, chunking, or the embedding model | - |
| MC-002 | Recall@k (document level) | measured (script) | 1.0 | 4 | same | tune k or chunking | - |
| MC-003 | Precision@k | measured (script) | 0.6 | 4 | same | lower k or raise the minimum relevance score | - |
| MC-004 | MRR | measured (script) | 1.0 | 4 | same | change the embedding model or add reranking | - |
| MC-005 | nDCG@k | measured (script) | 1.0 | 4 | same, plus the run header | compare retrieval configurations | - |
| MC-006 | Context relevance | unavailable | - | - | - | tune the minimum relevance score | Add passage-level relevance labels (relevant or not, per retrieved chunk) to the label file; at document level this metric would equal MC-003. |
| MC-007 | Chunk coverage | unavailable | - | - | - | change chunk size or overlap | Add point-to-chunk labels: for each answer point, the retrieved chunk ids that support it. |

Per question, Precision@k (MC-003): `q1` 0.6, `q2` 0.4, `q3` 0.4, `q5` 1.0. Recall@k, MRR,
and nDCG@k were 1.0 for every question.

| Category | MC-001 | MC-002 | MC-003 | MC-004 | MC-005 |
|---|---|---|---|---|---|
| answerable | 3/3 (1.0) | 1.0 (n 3) | 0.4667 (n 3) | 1.0 (n 3) | 1.0 (n 3) |
| multi_source | 1/1 (1.0) | 1.0 (n 1) | 1.0 (n 1) | 1.0 (n 1) | 1.0 (n 1) |

### Generation

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|
| MC-008 | Faithfulness / groundedness | measured (human labels) | 1.0 | 4 | `evaluation/labels/20261125T231209Z-real.jsonl` | strengthen the guardrail or prompts | - |
| MC-009 | Answer relevance | measured (human labels) | 4.25 | 4 | same | revise the Answer/Verifier task | - |
| MC-010 | Context utilization | measured (script) | 0.7667 | 4 | `evaluation/results/20261125T231209Z-real.jsonl`, `evaluation/expected_answers.jsonl` | revise the citation instructions | - |
| MC-011 | Citation correctness | measured (script) | (a) validity 8/8 (1.0), citations removed 0; (b) support 9/9 (1.0), from labels | 8 | results file; label file | strengthen the citation guardrail | - |
| MC-012 | Citation completeness | measured (human labels) | 1.0 | 4 | label file | require a citation per statement | - |
| MC-013 | Unsupported-claim rate | measured (human labels) | 0.0 | 4 | label file | strengthen the guardrail or change model | - |

Per question, answer relevance (MC-009): `q1` 4.0, `q2` 5.0, `q3` 4.0, `q5` 4.0.
Faithfulness (MC-008), citation completeness (MC-012), and unsupported-claim rate (MC-013)
were the same for every question (1.0, 1.0, 0.0). Context utilization (MC-010) per question:
`q1` 0.6667, `q2` 1.0, `q3` 1.0, `q5` 0.4; by category: answerable 0.8889 (n 3),
multi_source 0.4 (n 1). Answered questions citing an expected source: 4/4.

### Task outcome

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|
| MC-014 | Correctness against answer points | measured (human labels) | 0.9167 | 4 | label file, `evaluation/expected_answers.jsonl` | release or change model | - |
| MC-015 | Abstention quality | measured (script) | 5/5 (1.0) | 5 | `evaluation/results/20261125T231209Z-real.jsonl`, `evaluation/expected_answers.jsonl` | tune the minimum relevance score or prompts | - |
| MC-016 | Human rubric score | measured (human labels) | 4.0 | 4 | label file | compare releases with a human view | - |

MC-015 counts: abstained when abstention expected 1; answered when an answer expected 4;
abstained when an answer expected (wrong refusal) 0; answered when abstention expected
(unsupported answer) 0; failed 0. Rubric score (MC-016) per question: `q1` 4.0, `q2` 5.0,
`q3` 4.0, `q5` 3.0.

### Agent workflow

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|
| MC-017 | Task success rate | measured (script) | 5/5 (1.0) | 5 | `evaluation/results/20261125T231209Z-real.jsonl` | fix failing steps before tuning quality | - |
| MC-018 | Tool / retrieval failure rate | measured (script) | 0/5 (0.0) | 5 | same | fix the retrieval tool or store | - |
| MC-019 | Number of retries | measured (script) | 0 | 5 | `reports/langfuse/20261125T231209Z-real/` | tune structured-output prompts or model | - |
| MC-020 | Trace completeness | measured (script) | 5/5 (1.0) | 5 | `reports/langfuse/20261125T231209Z-real/`, results file | fix instrumentation gaps | - |
| MC-021 | Step latency | measured (script) | see section 8 | 5 | `reports/langfuse/20261125T231209Z-real/` | find the slowest step | - |
| MC-022 | End-to-end latency | measured (script) | median 15204.0 ms, maximum 15483 ms | 5 | `evaluation/results/20261125T231209Z-real.jsonl` | choose model size or hardware | - |
| MC-023 | Cost / token usage | measured (script) | 8888 tokens (prompt 8228, completion 660); cost unavailable | 5 | results file, `reports/langfuse/20261125T231209Z-real/` | shorten prompts or reduce k | - |

Per question, end-to-end latency in ms (MC-022): `q1` 15483, `q2` 13394, `q3` 15204,
`q4` 6834, `q5` 15327. By category: answerable median 15204.0 and maximum 15483 (n 3);
unanswerable 6834.0 (n 1); multi_source 15327.0 (n 1). p95 is not reported (`p95_ms` is
null: too few questions).

Per question, tokens (MC-023, prompt / completion): `q1` 1902 / 144, `q2` 1582 / 142,
`q3` 1646 / 176, `q4` 1177 / 45, `q5` 1921 / 153. Cost: unavailable, no Langfuse cost field
(local model has no price).

Task success (MC-017) by category: answerable 3/3, unanswerable 1/1, multi_source 1/1.

### Operations

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|
| MC-024 | Upload success rate | measured (script) | 3/3 (1.0) | 3 | run header | fix parsing of failing files | - |
| MC-025 | Indexing latency | measured (script) | total 420 ms | 3 | run header | batch embeddings or change model | - |
| MC-026 | Query throughput | unavailable | - | - | - | size hardware for concurrent users | Add a load test that sends questions concurrently and records questions per minute. |
| MC-027 | Error rate | measured (script) | 0/5 (0.0) | 5 | results file | fix failing steps before tuning quality | - |
| MC-028 | Resource usage | unavailable | - | - | - | size hardware | Record CPU and memory during indexing and answering (for example with psutil) in the run header. |

Indexing latency per file (MC-025): `data-retention-policy.pdf` 133 ms,
`incident-runbook.txt` 128 ms, `model-monitoring-guide.md` 157 ms (embedding model download
excluded). Error rate by category (MC-027): answerable 0/3, unanswerable 0/1,
multi_source 0/1.

### Safety / privacy

| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |
|---|---|---|---|---|---|---|---|
| MC-029 | Prompt-injection detection rate | unavailable | - | - | - | harden prompts and guardrail | Add documents and questions containing injection attempts to the dataset with expected safe behavior. |
| MC-030 | Data leakage checks | unavailable | - | - | - | harden the guardrail | Add test cases whose answers must not contain content from outside the retrieved chunks. |
| MC-031 | Secret exposure | measured (script) | 0 findings | 79 files scanned | `reports/rag-evaluation-evidence.json` | remove and rotate exposed secrets | - |
| MC-032 | PII handling | not applicable | - | - | `specs/spec.md`, `.env.example` | decide what may be traced and logged | - |

MC-031 and MC-032 are discussed in section 13.

## 5. Test results

| Passed | Failed | Skipped | Duration (s) |
|---|---|---|---|
| 136 | 0 | 0 | 7.92 |

| FR-035 area | Test modules | Passed | Failed |
|---|---|---|---|
| file type and empty-file validation | `test_ingestion_validation` | 14 | 0 |
| chunking and metadata preservation | `test_chunking` | 4 | 0 |
| retrieval of relevant evidence | `test_retrieval` | 5 | 0 |
| cautious answer for an unknown question | `test_crew_stub`, `test_guardrail` | 13 | 0 |
| source references when evidence is available | `test_crew_stub` | 5 | 0 |
| observability disabled or mocked | `test_observability` | 8 | 0 |
| smoke test of the main path | `test_smoke` | 1 | 0 |

Source: `reports/test-results/junit.xml`. The tests run offline with the deterministic fake
model, lexical fake embeddings, and Langfuse disabled or replaced by an in-memory exporter.
The suite also contains tests outside the FR-035 areas (configuration, sanitization,
knowledge base, answer service, evaluation runner and dataset, trace export, packaging,
Streamlit UI, and the skill scripts).

## 6. Success criteria

| Id | Target | Measured | Verdict | Metric |
|---|---|---|---|---|
| SC-003 | total indexing time < 60000 ms | 420 | met | MC-025 |
| SC-004 | every answerable and multi-source question retrieves an expected source | 4/4 | met | MC-001 |
| SC-005 | each answered question cites an expected source | 4/4 | met | MC-010 |
| SC-006 | unanswerable questions receive the safe response | 1/1 | met | MC-015 |
| SC-007 | one complete trace per question (real Langfuse) | 5/5 | met | MC-020 |
| SC-008 | max end-to-end latency < 30000 ms | 15483 | met | MC-022 |

## 7. Per-question results

| Id | Category | Status | Expected sources | Retrieved files | Cited files | Guardrail | Removed | Latency (ms) |
|---|---|---|---|---|---|---|---|---|
| `q1` | answerable | answered | `model-monitoring-guide.md` | `data-retention-policy.pdf`, `incident-runbook.txt`, `model-monitoring-guide.md` | `model-monitoring-guide.md` | passed | 0 | 15483 |
| `q2` | answerable | answered | `incident-runbook.txt` | `data-retention-policy.pdf`, `incident-runbook.txt`, `model-monitoring-guide.md` | `incident-runbook.txt` | passed | 0 | 13394 |
| `q3` | answerable | answered | `data-retention-policy.pdf` | `data-retention-policy.pdf`, `incident-runbook.txt`, `model-monitoring-guide.md` | `data-retention-policy.pdf` | passed | 0 | 15204 |
| `q4` | unanswerable | abstained | - | `data-retention-policy.pdf`, `incident-runbook.txt`, `model-monitoring-guide.md` | - | safe_response | 0 | 6834 |
| `q5` | multi_source | answered | `model-monitoring-guide.md`, `incident-runbook.txt` | `incident-runbook.txt`, `model-monitoring-guide.md` | `incident-runbook.txt`, `model-monitoring-guide.md` | passed | 0 | 15327 |

`q4` ("What is the company's parental leave policy?") received the safe response; its
retrieved chunks are listed before the minimum-score filter. According to the labels, `q5`
("What should the on-call engineer do when a data drift alert fires?") missed one of its
three answer points.

## 8. Langfuse observations

Traces of the selected run (exports in `reports/langfuse/20261125T231209Z-real/`):

| Question | Trace id |
|---|---|
| `q1` | 34799505bd59970462d19f68b441d672 |
| `q2` | eb4f15b83930dac9033394359b2eac12 |
| `q3` | 9111307c05aafd7ba614125d47dc06b2 |
| `q4` | 1794410e4cf4054f5be28d644434452d |
| `q5` | 0469742eb4e2ec42b9cceed1dd686c62 |

- Trace completeness (MC-020): 5/5; every export has all nine presence flags true; no
  question lacks a trace id.
- Retries (MC-019): 0 for every question (no LLM call beyond the two expected).
- Step latency (MC-021), median and maximum in ms, n = 5 for each step:

| Step | Median (ms) | Max (ms) |
|---|---|---|
| rag-question (root) | 15204 | 15484 |
| crew kickoff | 15198 | 15467 |
| agent task: Retriever/Researcher | 2224 | 2922 |
| generation: Retriever/Researcher | 2043 | 2761 |
| search_knowledge_base (retriever) | 161 | 199 |
| search_knowledge_base.run (tool) | 162 | 200 |
| agent task: Answer/Verifier | 12520 | 13119 |
| generation: Answer/Verifier | 12499 | 13099 |

  The Answer/Verifier generation is the largest share of the end-to-end latency; retrieval
  is a small share of it.
- Tokens and cost (MC-023): see section 4; no cost field is present in the exports.

## 9. Fake-model runs

These results come from the deterministic extractive fake model and lexical fake
embeddings. They check the pipeline and the data contract only and say nothing about answer
quality. They are not part of any metric above.

Run `20261125T231207Z-fake` (`evaluation/results/20261125T231207Z-fake.jsonl`):

| Id | Value |
|---|---|
| MC-001 | 4/4 (1.0) |
| MC-002 | 1.0 |
| MC-003 | 0.5 |
| MC-004 | 1.0 |
| MC-005 | 0.8878 |
| MC-010 | 0.5 |
| MC-011 | 7/7 (1.0) |
| MC-015 | 5/5 (1.0) |
| MC-017 | 5/5 (1.0) |
| MC-018 | 0/5 (0.0) |
| MC-022 | maximum 47 ms |
| MC-024 | 3/3 (1.0) |
| MC-025 | total 46 ms |
| MC-027 | 0/5 (0.0) |

## 10. Provenance

| Metric | Value | Source file | Record or trace | Field |
|---|---|---|---|---|
| MC-001 | 4/4 (1.0) | `evaluation/results/20261125T231209Z-real.jsonl` | question records `q1`, `q2`, `q3`, `q5` | `retrieved[].file`, `expected_sources` |
| MC-002 | 1.0 | `evaluation/results/20261125T231209Z-real.jsonl` | question records | `retrieved[].file`, `expected_sources` |
| MC-003 | 0.6 | `evaluation/results/20261125T231209Z-real.jsonl` | question records; header | `retrieved[].file`, `k` |
| MC-004 | 1.0 | `evaluation/results/20261125T231209Z-real.jsonl` | question records | `retrieved[].rank` |
| MC-005 | 1.0 | `evaluation/results/20261125T231209Z-real.jsonl` | question records; header | `retrieved[].rank`, `indexing[].chunk_count` |
| MC-008 | 1.0 | `evaluation/labels/20261125T231209Z-real.jsonl` | records `q1`, `q2`, `q3`, `q5` | `claims_supported`, `claims_total` |
| MC-009 | 4.25 | `evaluation/labels/20261125T231209Z-real.jsonl` | records `q1`, `q2`, `q3`, `q5` | `answer_relevance` |
| MC-010 | 0.7667 | `evaluation/results/20261125T231209Z-real.jsonl` | question records | `cited_chunk_ids`, `retrieved[].chunk_id` |
| MC-011 | 8/8 (1.0) | `evaluation/results/20261125T231209Z-real.jsonl` | question records | `draft_cited_chunk_ids`, `citations_removed` |
| MC-011 (b) | 9/9 (1.0) | `evaluation/labels/20261125T231209Z-real.jsonl` | records `q1`, `q2`, `q3`, `q5` | `citations_supporting`, `citations_checked` |
| MC-012 | 1.0 | `evaluation/labels/20261125T231209Z-real.jsonl` | records `q1`, `q2`, `q3`, `q5` | `claims_supported`, `uncited_supported_claims` |
| MC-013 | 0.0 | `evaluation/labels/20261125T231209Z-real.jsonl` | records `q1`, `q2`, `q3`, `q5` | `claims_supported`, `claims_total` |
| MC-014 | 0.9167 | `evaluation/labels/20261125T231209Z-real.jsonl`, `evaluation/expected_answers.jsonl` | records `q1`, `q2`, `q3`, `q5` | `points_covered`, `answer_points` |
| MC-015 | 5/5 (1.0) | `evaluation/results/20261125T231209Z-real.jsonl` | all question records | `status`, `expected_behavior` |
| MC-016 | 4.0 | `evaluation/labels/20261125T231209Z-real.jsonl` | records `q1`, `q2`, `q3`, `q5` | `rubric_score` |
| MC-017 | 5/5 (1.0) | `evaluation/results/20261125T231209Z-real.jsonl` | all question records | `status` |
| MC-018 | 0/5 (0.0) | `evaluation/results/20261125T231209Z-real.jsonl` | all question records | `status`, `error_stage` |
| MC-019 | 0 | `reports/langfuse/20261125T231209Z-real/` | five trace exports | `retry_count` |
| MC-020 | 5/5 (1.0) | `reports/langfuse/20261125T231209Z-real/` | five trace exports | `presence` |
| MC-022 | 15483 | `evaluation/results/20261125T231209Z-real.jsonl` | question record `q1` | `latency_ms` |
| MC-022 | 15204.0 (median) | `evaluation/results/20261125T231209Z-real.jsonl` | all question records | `latency_ms` |
| MC-023 | 8888 | `evaluation/results/20261125T231209Z-real.jsonl` | all question records | `prompt_tokens`, `completion_tokens` |
| MC-024 | 3/3 (1.0) | `evaluation/results/20261125T231209Z-real.jsonl` | header | `indexing[].status` |
| MC-025 | 420 | `evaluation/results/20261125T231209Z-real.jsonl` | header | `total_indexing_ms` |
| MC-027 | 0/5 (0.0) | `evaluation/results/20261125T231209Z-real.jsonl` | all question records | `status` |
| MC-031 | 0 | `reports/rag-evaluation-evidence.json` | secret scan | `secret_scan.findings` |
| Tests | 136 passed, 0 failed, 0 skipped, 7.92 s | `reports/test-results/junit.xml` | test suite | `tests`, `failures`, `errors`, `skipped`, `time` |

## 11. Limitations

- Five questions over three short documents: every result is indicative. Rates are given as
  counts; no comparison between runs is possible at this size (EM-005).
- The labels come from one labeller, the project author, who also built the system; no
  independent labeller and no agreement between labellers, so the label-based metrics,
  including the primary metric, may be optimistic.
- Retrieval relevance is judged at document level, which is optimistic (EM-002): a chunk from
  the right file may not contain the answer. Precision@k is limited by the small knowledge
  base, where k covers a large share of the chunks.
- The minimum relevance score was tuned on these evaluation questions (see the tuning
  disclosure in `evaluation/README.md`): retrieval and abstention results are optimistic
  (EM-007). Prompts were not tuned on them.
- One real run only: the local model is not deterministic, so another run may differ.
- Prompt token counts for the local Ollama model are reported by CrewAI as approximations
  (one token per four characters, see `docs/adr/0001-local-ollama-llm-provider.md`); cost is
  not available for a local model.

## 12. Data-quality concerns

- The sample knowledge was written for the project; its wording is close to the questions,
  which favors retrieval.
- The expected answers have two or three answer points per question, so correctness is
  coarse; a point was labelled covered when its main fact was stated, even if a secondary
  detail of the expected point text was missing.
- Expected sources are file-level only; there are no passage-level or point-to-chunk labels
  (needed for MC-006 and MC-007).
- A single labeller produced the labels; no agreement between labellers can be measured.

## 13. Privacy considerations

- Secret scan (MC-031): 0 findings in 79 scanned files (tracked files and trace exports).
  The scan excludes the `tests/` directory, which holds deliberate dummy keys that exercise
  the secret checks, and the skill's own scripts and fixtures (see
  `.agents/skills/rag-evaluation-report/references/privacy.md`). No credential appears in
  the trace exports.
- `.env` exists locally and is git-ignored; it was not opened by this skill.
- PII handling (MC-032): the application stores uploaded files and their chunks under
  `storage/` (git-ignored). Logs contain structured events with request ids, statuses, and
  counts, without question text or file content. Langfuse traces contain the question, the
  retrieved chunk metadata with a short text preview, and the model inputs and outputs. The
  sample knowledge and the evaluation questions are fictional and contain no personal data;
  real documents uploaded by a user would be sent to Langfuse Cloud as part of the traces.
- This report quotes two evaluation questions and no answer or chunk text.

## 14. Recommended next experiments

1. Have a second, independent person label the same run and measure the agreement with the
   existing labels: this checks how far the primary metric MC-014 and MC-008, MC-009, MC-012,
   MC-013, MC-016, and MC-011 (b) depend on the labeller, before they support a release
   decision.
2. Improve multi-source answers: `q5` missed one of its three points and had the lowest
   context utilization (MC-010) and rubric score (MC-016). Try a prompt that asks the
   Answer/Verifier to cover every retrieved source, or a higher k for multi-source questions,
   and compare on a larger dataset.
3. Extend the dataset to at least 10 questions, and later 20 for p95 latency, with harder
   multi-source and near-miss unanswerable questions written before any tuning: this makes
   MC-015 and the retrieval metrics less optimistic and allows run comparisons (EM-005,
   EM-007).
4. Add passage-level and point-to-chunk labels to measure MC-006 and MC-007, and decide
   whether Precision@k (MC-003) calls for a higher minimum relevance score or a smaller k.
5. Add prompt-injection and data-leakage cases to the dataset (MC-029, MC-030) to test the
   instruction to treat documents as data.
6. Instrument throughput and resource usage (MC-026, MC-028) and compare a smaller or
   quantized model, since the Answer/Verifier generation is the largest share of the
   latency (MC-021, MC-022).
