# Feature Specification: Agentic RAG Knowledge Assistant

**Feature Branch**: `main` (feature directory: `specs/`)

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: "Agentic RAG Knowledge Assistant: a small, production-minded Python RAG application. Users upload knowledge files (.txt, .pdf, .md), the app parses, chunks, embeds and stores them with citation metadata, then answers natural-language questions through a CrewAI agentic workflow (Retriever/Researcher agent + Answer/Verifier agent, sequential) grounded only in the indexed knowledge, with citations and a hallucination guardrail. Every question run is traced in Langfuse. Includes an evaluation dataset and a user-invocable rag-evaluation-report skill."

## Overview

The Agentic RAG Knowledge Assistant lets a person build a small private knowledge base from
their own documents and ask questions about it. Answers are produced by a two-agent workflow
that uses only the uploaded knowledge, cites its sources whenever it answers, and says
plainly when the answer is not in the knowledge base. Every question run is observable end
to end in an observability platform (Langfuse), and the quality of the whole system can be
assessed on demand through an evaluation report skill that never invents measurements.

The goal is not a large product: it is a small, honest, testable application demonstrating
retrieval-augmented generation, agent orchestration, observability, testing, and evaluation
practices.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload and index knowledge files (Priority: P1)

A user opens the "Knowledge" view, selects one or more files (plain text, PDF, or Markdown),
and submits them. For each file the application shows its name and processing status. Valid
files are parsed, split into chunks, embedded, and stored in the knowledge base together with
the information needed to cite them later. Empty files and unsupported file types are
rejected with a clear reason; nothing is silently accepted.

**Why this priority**: Without indexed knowledge, no question can be answered. This is the
foundation of every other story.

**Independent Test**: Upload the provided sample files plus one empty file and one
unsupported file; verify the valid files are reported as indexed with a chunk count, the
invalid ones are rejected with a reason, and the knowledge base contains chunks traceable to
their source file.

**Acceptance Scenarios**:

1. **Given** an empty knowledge base, **When** the user uploads a valid `.txt` and `.pdf`
   file (and a `.md` file if supported), **Then** each file is listed with status "indexed"
   and its number of chunks, and a success message is shown.
2. **Given** the Knowledge view, **When** the user uploads an empty file (zero bytes,
   whitespace only, or a PDF with no extractable text), **Then** the file is listed as
   "rejected" with the reason "empty file" and nothing from it is stored.
3. **Given** the Knowledge view, **When** the user uploads a file with an unsupported type
   (for example `.docx` or `.png`), **Then** the file is listed as "rejected" with the reason
   "unsupported file type" and the list of supported types.
4. **Given** a batch with both valid and invalid files, **When** the batch is processed,
   **Then** valid files are indexed and invalid files are rejected individually; one bad file
   does not block the others.
5. **Given** indexing is in progress, **When** the user looks at the view, **Then** each file
   shows a processing status until it reaches a final status (verified manually).

---

### User Story 2 - Ask a question and get a cited, grounded answer (Priority: P1)

A user opens the "Ask" view, types a natural-language question, and submits it. While the
agentic workflow runs, a visible processing state is shown. The answer is based only on the
indexed knowledge and lists the sources it relied on (file name and chunk reference, plus
page when available). If the knowledge base does not contain enough evidence, the user
receives the safe response "I could not find this in the uploaded knowledge." instead of a
guess.

**Why this priority**: This is the core value of the product. Together with Story 1 it forms
the minimum viable product.

**Independent Test**: With the sample knowledge indexed, ask one answerable question and one
unanswerable question; verify the first answer contains the expected points and correct
citations, and the second returns the safe response without invented facts.

**Acceptance Scenarios**:

1. **Given** the sample knowledge is indexed, **When** the user asks a question whose answer
   is in one file, **Then** the answer states the expected points and cites that file and
   chunk.
2. **Given** the sample knowledge is indexed, **When** the user asks a question whose answer
   requires information from more than one chunk or document, **Then** the answer combines
   that information and cites every source used.
3. **Given** the sample knowledge is indexed, **When** the user asks a question that is not
   covered by the knowledge, **Then** the user sees "I could not find this in the uploaded
   knowledge." and no unsupported claims.
4. **Given** the evidence only partially covers the question, **When** the answer is
   produced, **Then** it clearly separates what is supported by evidence from what is
   uncertain or missing.
5. **Given** the knowledge base is empty, **When** the user asks a question, **Then** the
   user is told to upload and index knowledge first.
6. **Given** a question has been submitted, **When** the workflow is running, **Then** a
   visible processing state is shown (verified manually).
7. **Given** an answer is displayed, **When** the user inspects its citations, **Then** each
   citation refers to a chunk that was actually retrieved for this question, and the user can
   see the retrieved chunk references (file, chunk, relevance score).

---

### User Story 3 - Trace every question run in Langfuse (Priority: P2)

An operator (the developer or evaluator) configures Langfuse credentials locally, runs the
application, asks a question, and finds one trace for that question in Langfuse. The trace
shows the question, the non-sensitive request identifier, each agent and task step, the
retrieval step with the retrieved chunk metadata, the model generations with their
input/output metadata, model name and token usage when available, the latency and status of
each major step, and any error. For automated tests, observability can be turned off or
replaced by a test double without changing application behavior.

**Why this priority**: Observability is mandatory for the deliverable, but the product still
answers questions without it; it builds on Stories 1 and 2.

**Independent Test**: With Langfuse configured, ask one question from the UI and locate the
corresponding trace by its request identifier; then run the automated tests with
observability disabled and mocked, and confirm they pass.

**Acceptance Scenarios**:

1. **Given** Langfuse is configured, **When** the user asks a question, **Then** exactly one
   trace is created for that question, and the request identifier shown in the Ask view
   matches the trace.
2. **Given** a trace, **When** the operator opens it, **Then** it contains nested
   observations for the retriever agent/task, the answer/verifier agent/task, the retrieval
   operation (with file names, chunk ids, and scores), and each model generation (with model
   name and token usage when available), each with latency and status.
3. **Given** a run fails (for example the model provider is unreachable), **When** the
   operator opens the trace, **Then** the failed step is marked as an error with a readable
   message and the overall run is marked as failed.
4. **Given** observability is disabled, **When** the application or the automated tests
   run, **Then** they produce the same answers and statuses as with observability enabled,
   and no attempt is made to contact Langfuse.
5. **Given** Langfuse is enabled but unreachable, **When** the user asks a question, **Then**
   the user still receives the answer and the observability failure is only logged.
6. **Given** any trace, **When** it is inspected, **Then** it contains no credentials, API
   keys, or tokens.

---

### User Story 4 - Evaluate the assistant against a reference dataset (Priority: P2)

A developer runs the automated test suite and the evaluation dataset against the
application. The dataset contains at least five questions about the provided sample
knowledge, each with its expected answer points and expected source document(s). The
results are saved so that they can be inspected and used by the evaluation report.

Two kinds of runs exist and are never mixed: the automated tests run offline with a
deterministic fake model and fake embeddings; the evaluation dataset run that feeds the
evaluation report uses the real configured model with Langfuse enabled.

**Why this priority**: It proves the system works and provides the evidence needed for the
evaluation report.

**Independent Test**: Run the test suite from a clean checkout without network and verify
all tests pass and results are saved; then run the evaluation dataset with the real model
and verify a result file following the evaluation data contract is saved, with trace ids.

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** the developer runs the automated tests without
   network access, **Then** all tests pass using a deterministic fake model, fake embeddings,
   and disabled or mocked observability.
2. **Given** the evaluation dataset, **When** it is inspected, **Then** it contains at least
   three answerable questions, one unanswerable question, and one question requiring
   information from more than one chunk or document, each with expected answer points and
   expected sources (none for the unanswerable question, which expects the safe response).
3. **Given** the evaluation is run, **When** it completes, **Then** a result file following
   the evaluation data contract (EV-003) is saved in `evaluation/results/`, labelled with the
   model used and whether it is the fake or a real model.
4. **Given** the manual test procedure in the README, **When** a tester follows it step by
   step, **Then** they can reproduce upload, question answering, and trace verification.

---

### User Story 5 - Produce an honest evaluation report on demand (Priority: P3)

After implementation and testing, the user explicitly invokes the `rag-evaluation-report`
skill. The skill collects the evidence, computes metrics with deterministic scripts, and
writes a Markdown report. The report lists all metrics of the catalogue with a status,
reports only values that were actually measured, labels every other metric as "unavailable"
or "not applicable" with an explanation, and covers limitations, data quality, privacy, and
next experiments.

**Why this priority**: It is a required deliverable but depends on all previous stories
being complete.

**Independent Test**: Invoke the skill explicitly after the tests and the evaluation run;
verify the report is written to `reports/rag-evaluation-report.md`, the self-check passes,
every reported number appears in the metrics file with its source, and missing metrics are
labelled with a collection plan.

**Acceptance Scenarios**:

1. **Given** the skill exists, **When** its definition is inspected, **Then** it is named
   `rag-evaluation-report`, is user-invocable, has model (automatic) invocation disabled, and
   states that it runs only when the user explicitly requests an evaluation report.
2. **Given** the user is coding, uploading files, or asking questions, **When** those
   activities happen, **Then** the skill is never triggered automatically.
3. **Given** the user invokes the skill, **When** it finishes, **Then** a Markdown report is
   written to `reports/rag-evaluation-report.md` and the report self-check passes.
4. **Given** a metric cannot be computed from the available evidence (for example no
   Langfuse export or no human labels), **When** the report is written, **Then** that metric
   is marked "unavailable" with an explanation of how to collect it, and no value is
   invented.
5. **Given** only fake-model results exist, **When** the skill runs, **Then** the report says
   so first and reports no quality metric as if it came from a real model.

---

### Edge Cases

- A PDF that is scanned (image only) has no extractable text: it is rejected as empty, not
  indexed.
- A file name with path separators, special characters, or a very long name: it is sanitized
  before any storage and displayed safely.
- A file larger than the documented upload size limit: it is rejected with the limit stated.
- A file whose content cannot be parsed (for example an invalid PDF): it is rejected as
  unreadable with a clear message.
- An empty or whitespace-only question: it is rejected before running the workflow.
- The model provider is unavailable, times out, or returns an error: the user sees a
  readable error, the run is recorded as failed, and no partial answer is shown as final.
- The model returns an answer citing a chunk that was not retrieved: the invalid citation is
  removed; if no supported content remains, the safe response is shown.
- Retrieved chunks are on the same topic as the question but do not contain the answer: the
  Answer/Verifier agent reports insufficient evidence and the safe response is shown.

## Requirements *(mandatory)*

### Functional Requirements

**Knowledge upload and indexing (Knowledge view)**

- **FR-001**: The application MUST provide a user interface with at least two clearly
  separated views: "Knowledge" (upload and indexing) and "Ask" (question answering).
- **FR-002**: Users MUST be able to upload one or more files in a single action.
- **FR-003**: The system MUST accept `.txt` and `.pdf` files and SHOULD accept `.md` files;
  every other file type MUST be rejected with the message "unsupported file type" and the
  list of supported types.
- **FR-004**: The system MUST reject empty files: zero bytes, whitespace-only content, or no
  extractable text after parsing.
- **FR-005**: The system MUST reject files larger than a documented maximum size (default
  10 MB per file).
- **FR-006**: The system MUST show, for each uploaded file, its name and a status among
  "processing", "indexed (N chunks)", or "rejected (reason)".
- **FR-007**: The system MUST parse, chunk, embed, and store each valid file in a persistent
  knowledge base.
- **FR-008**: Each stored chunk MUST keep: source file name, a stable chunk identifier, chunk
  position within the file, page number when the source is paginated, and the chunk text.
- **FR-009**: Re-uploading a file with identical content SHOULD NOT create duplicate chunks.
- **FR-010**: The system MUST display a clear overall success or error message after each
  upload batch.
- **FR-011**: Users SHOULD be able to see which files are currently in the knowledge base and
  to clear the knowledge base.

**Question answering (Ask view)**

- **FR-012**: Users MUST be able to enter a natural-language question and submit it.
- **FR-013**: The system MUST reject empty or whitespace-only questions before running the
  workflow, and SHOULD reject questions longer than a documented maximum (default 1,000
  characters).
- **FR-014**: The system MUST show a visible processing state while the answer workflow runs.
- **FR-015**: The answer MUST be produced by an agentic workflow with two agents executed in
  sequence:
  1. a Retriever/Researcher agent that receives the question, queries the knowledge base,
     and returns the most relevant chunks (default top 5) with their source metadata and
     relevance scores;
  2. an Answer/Verifier agent that uses only the retrieved chunks to draft the answer,
     decides whether the evidence is sufficient to answer, identifies missing evidence, and
     attaches citations.
- **FR-016**: The workflow definition MUST make explicit, for each agent and task: its role,
  goal, inputs, expected output, and execution order.
- **FR-017**: The instructions given to the agents MUST require them to use only retrieved
  evidence and to distinguish evidence from uncertainty; they SHOULD also tell the agents to
  treat document content as data rather than instructions.
- **FR-018**: A hallucination guardrail MUST check every draft answer before display:
  - evidence sufficiency is decided at answer level: if the Answer/Verifier agent reports
    that the retrieved chunks do not contain enough evidence to answer, or if no chunk is
    retrieved above a configurable minimum relevance score, the system MUST return exactly
    the safe response "I could not find this in the uploaded knowledge." (optionally
    followed by any partial evidence, labelled as such);
  - otherwise, the answer MUST separate supported statements from uncertain or missing
    ones; statements presented as facts MUST carry at least one valid citation, and
    citations to chunks that were not retrieved MUST be removed; if no supported statement
    remains, the safe response is shown.
  The guardrail's decision (passed, citations removed, safe response) MUST be recorded with
  the question run.
- **FR-019**: When evidence is available, the displayed answer MUST include citations
  identifying the source file and chunk (and page when available) for each supported point.
- **FR-020**: Citations MUST only reference chunks that were retrieved for the current
  question.
- **FR-021**: The Ask view MUST show the retrieved chunk references (file, chunk, relevance
  score) alongside the answer.
- **FR-022**: If the knowledge base is empty, the system MUST tell the user to upload
  knowledge first instead of running the workflow.
- **FR-023**: Each question run MUST receive a non-sensitive request identifier (a random
  identifier, not derived from user data) that is shown in the Ask view and used in logs and
  traces; it serves as the request/session identifier.

**Observability (Langfuse)**

- **FR-024**: The system MUST create one Langfuse trace per user question, and MUST flush it
  so that it is persisted in Langfuse even when the run is short-lived.
- **FR-025**: Each trace MUST record: the user question; the request identifier; nested
  observations for each agent and task; the retrieval operation with retrieved file names,
  chunk ids, and scores; each model generation with input/output metadata, model name, and
  token usage when available; latency and status for each major step; and errors for failed
  runs.
- **FR-026**: Traces and logs MUST NOT contain secrets (API keys, tokens, credentials) and
  SHOULD avoid unnecessary personal data.
- **FR-027**: Observability MUST be switchable off (or replaceable by a test double) through
  configuration; with observability off, the same inputs MUST produce the same answers and
  statuses.
- **FR-028**: A failure to reach Langfuse MUST NOT prevent the user from getting an answer;
  it MUST be logged.
- **FR-029**: Application logs SHOULD be structured and include the request identifier of
  the corresponding trace.

**Errors**

- **FR-030**: The system MUST show distinct, user-readable messages, without secrets or raw
  stack traces, for: each upload rejection reason (unsupported type, empty, too large,
  unreadable), empty knowledge base, invalid question, and model provider failure or
  timeout.

**Configuration and security**

- **FR-031**: All environment-specific settings (model provider and model name, provider
  credentials, Langfuse keys and host, observability on/off, storage location, chunking and
  retrieval parameters, minimum relevance score, size limits) MUST be read from environment
  variables, optionally from a local `.env` file that is never committed.
- **FR-032**: A `.env.example` file MUST list every required variable name with empty or
  placeholder values only.
- **FR-033**: Uploaded file names MUST be sanitized before any storage use, and stored files
  MUST stay inside the configured data directory.
- **FR-034**: The application has no authentication; the README MUST state that it is
  intended for local development or trusted environments only, and MUST state the supported
  platforms.

**Testing**

- **FR-035**: Automated tests MUST cover at least:
  1. file type and empty-file validation;
  2. document chunking and metadata preservation;
  3. retrieval of relevant evidence for at least one known question;
  4. a cautious answer (safe response or abstention) for an unknown or unsupported question;
  5. presence of source references in the answer when evidence is available;
  6. the application working with observability disabled or mocked;
  7. a health/smoke test of the main path (upload, index, ask, cited answer) with a
     deterministic fake model.
- **FR-036**: Automated tests MUST run from a clean checkout without network access and
  without real model calls: a deterministic fake model and deterministic fake embeddings
  (lexical, so that test 3 above is meaningful) MUST be used.
- **FR-037**: The README MUST describe a repeatable manual test procedure, including the
  scenarios marked "verified manually", and automated test results MUST be saved in
  `reports/test-results/` (JUnit XML) for the deliverable.

**Evaluation dataset and runs**

- **EV-001**: The repository MUST include a small sample knowledge set (at least three
  documents, including at least one `.txt` and one `.pdf`) that is freely redistributable
  (written for the project or openly licensed), containing no private or copyrighted
  material the evaluator cannot access.
- **EV-002**: The repository MUST include an evaluation dataset of at least five questions
  over the sample knowledge: three answerable, one unanswerable, and one requiring
  information from more than one chunk or document. It is stored as JSON Lines:
  - `evaluation/questions.jsonl`, one record per question: `id`, `category` (one of
    `answerable`, `unanswerable`, `multi_source`), `question`;
  - `evaluation/expected_answers.jsonl`, one record per question: `id` (join key),
    `expected_behavior` (`answer` or `abstain`), `answer_points` (list of `{point_id,
    text}`; empty for the unanswerable question), `expected_sources` (list of file names;
    empty for the unanswerable question).
  The answer points form the expected-answer rubric.
- **EV-003**: The project MUST provide an evaluation runner that indexes the sample
  knowledge, asks every dataset question, and writes one result file per run to
  `evaluation/results/<run_id>.jsonl`:
  - a header record: `run_id`, `started_at`, `git_commit`, `model`, `model_kind` (`fake` or
    `real`), `embedding_model`, `k`, chunking parameters, minimum relevance score,
    `langfuse_enabled`, and an indexing summary (per file: status, chunk count, duration in
    ms; chunk count per file in the index);
  - one record per question: `id`, `status` (`answered`, `abstained`, `failed`),
    `error` (if failed), `retrieved` (ordered list of `{rank, file, chunk_id, score}`),
    `answer` text, `cited_chunk_ids`, `guardrail_decision`, `latency_ms`, token usage
    (`prompt_tokens`, `completion_tokens` when available), and `trace_id` when available.
- **EV-004**: The runner MUST NOT be run by the evaluation skill; it is run by the developer.
- **EV-005**: Langfuse trace summaries used by the evaluation MUST be exported to
  `reports/langfuse/` (one JSON file per trace with observation names, types, statuses,
  durations, token usage, and cost when Langfuse provides it), and at least one trace id or
  screenshot from a successful question run MUST be stored there.
- **EV-006**: Human labels for metrics that need judgement MAY be provided by the user in
  `evaluation/labels/<run_id>.jsonl`, one record per question: `id`, `points_covered` (list
  of `point_id`), `claims_total`, `claims_supported`, `uncited_supported_claims`,
  `answer_relevance` (1 to 5), `rubric_score` (1 to 5), `labeller`. The skill MUST generate
  an empty labelling template for the latest real run when none exists. No LLM judge is
  used in this version.

**Evaluation report skill**

- **SK-001**: The project MUST include a skill named `rag-evaluation-report` at
  `.agents/skills/rag-evaluation-report/SKILL.md` whose frontmatter declares
  `user-invocable: true` and `disable-model-invocation: true`. The skill MUST also be
  available under `.claude/skills/rag-evaluation-report/` so that the user invokes it in
  Claude Code by typing `/rag-evaluation-report` (a symbolic link in the repository; real
  files in the delivered archive).
- **SK-002**: The skill instructions MUST state that it is invoked only when the user
  explicitly requests an evaluation report, and it MUST NOT run during coding, upload, or
  question answering.
- **SK-003**: The skill MUST read the project specifications, test results, evaluation
  dataset, evaluation results, labels, application configuration (`.env.example`,
  `pyproject.toml`, the run header), and Langfuse trace summaries, and MUST write a Markdown
  report to `reports/rag-evaluation-report.md`.
- **SK-004**: The skill MUST be packaged as instructions plus helper files: reference files
  (data contract, metric catalogue, methodology, privacy rules), a report template, and
  Python standard-library scripts that: collect an evidence manifest (path, existence, size,
  modification time, SHA-256, record count, git commit, dirty working tree); compute every
  deterministic metric and write `reports/rag-evaluation-metrics.json` (metric id, status,
  value, numerator, denominator, n, run id, input files); summarize Langfuse exports; and
  check the final report. The scripts MUST have automated tests on a small fixture dataset.
- **SK-005**: All arithmetic MUST be done by the scripts; the agent running the skill MUST
  only copy values from `reports/rag-evaluation-metrics.json` and MUST NOT compute, estimate,
  or round values itself.
- **SK-006**: The report MUST contain a provenance table (metric, value, source file, record
  or trace id, field), and a self-check script MUST fail if a number in the report is absent
  from the metrics file, a trace id is absent from the evidence, an "unavailable" metric has
  a value or no collection plan, a catalogue metric is missing, or fake and real runs are
  mixed. The skill MUST NOT hand back a report whose self-check fails.
- **SK-007**: The skill MUST be read-only outside `reports/` and `evaluation/labels/`: it
  MUST NOT run the application, the tests, or the evaluation runner; MUST NOT write to
  Langfuse; MUST NOT commit; MUST NOT read `.env` files or print environment variables or
  credentials.
- **SK-008**: Run selection: the skill MUST report the latest real-model run (by header
  timestamp), list the other runs, and report fake-model runs only in a separate section. If
  no real-model run exists, the report MUST say so first and mark real-run metrics as
  unavailable. If the run's `git_commit` differs from the current commit or the working tree
  is dirty, the report MUST say so in its summary.
- **SK-009**: The report MUST list every metric of the catalogue (MC-001 to MC-032) with a
  status among "measured (script)", "measured (human labels)", "unavailable", and "not
  applicable"; unavailable and not applicable metrics MUST state why and, for unavailable
  ones, how to collect them. Metrics and Langfuse data MUST NOT be fabricated.
- **SK-010**: The report MUST include: run metadata; evidence inventory; the primary metric
  and its guardrails; one table per metric family; test results (passed, failed, skipped,
  duration, mapping to the FR-035 areas); comparison with the success criteria (target,
  measured value, met / not met / not measurable); per-question results using ids and file
  names only; Langfuse observations; provenance table; limitations; data-quality concerns;
  privacy considerations; and recommended next experiments, each tied to an unavailable or
  weak metric.
- **SK-011**: Privacy in the report: questions may be quoted (they come from the evaluation
  dataset), but answers and chunk text MUST NOT be copied; the secret scan MUST run on
  `git ls-files` and exported traces only, with a fixed list of patterns, and MUST report only
  file, line, and pattern name, never the matched value.

**Metric catalogue**

The report MUST consider all metrics below. "Default status" is the expected status for this
project with the evidence defined above; a metric becomes "measured" only if its evidence
exists.

| Id | Family | Metric | Definition / formula | Evidence | Default status |
|---|---|---|---|---|---|
| MC-001 | Retrieval | Hit Rate@k | share of answerable and multi-source questions with at least one retrieved chunk in the top k from an expected source | results + expected answers | measured (script) |
| MC-002 | Retrieval | Recall@k (document level) | expected source documents present in the top k / expected source documents, averaged per question | results + expected answers | measured (script) |
| MC-003 | Retrieval | Precision@k | chunks in the top k from an expected source / k, averaged per question | results + expected answers | measured (script) |
| MC-004 | Retrieval | MRR | mean of 1 / rank of the first chunk from an expected source (0 if none) | results + expected answers | measured (script) |
| MC-005 | Retrieval | nDCG@k | binary relevance; DCG@k = sum over ranks i of rel(i) / log2(i + 1); ideal DCG uses min(k, number of indexed chunks of the expected sources) relevant chunks, taken from the header's chunk counts | results + header + expected answers | measured (script) |
| MC-006 | Retrieval | Context relevance | share of retrieved chunks relevant to the question at passage level | needs passage labels | not applicable (equals MC-003 at document level; passage labels out of scope) |
| MC-007 | Retrieval | Chunk coverage | expected answer points supported by at least one retrieved chunk / expected answer points | needs point-to-chunk labels | unavailable |
| MC-008 | Generation | Faithfulness / groundedness | claims_supported / claims_total | human labels | measured (human labels) if labels exist |
| MC-009 | Generation | Answer relevance | mean answer_relevance (1 to 5) | human labels | measured (human labels) if labels exist |
| MC-010 | Generation | Context utilization | retrieved chunks from an expected source that are cited / retrieved chunks from an expected source | results | measured (script) |
| MC-011 | Generation | Citation validity (part of citation correctness) | cited chunk ids present in the retrieved list / cited chunk ids | results | measured (script) |
| MC-012 | Generation | Citation completeness | (claims_supported - uncited_supported_claims) / claims_supported | human labels | measured (human labels) if labels exist |
| MC-013 | Generation | Unsupported-claim rate | 1 - faithfulness | human labels | measured (human labels) if labels exist |
| MC-014 | Task outcome | Correctness against answer points (primary metric) | points_covered / answer_points, per question and overall | human labels + expected answers | measured (human labels) if labels exist |
| MC-015 | Task outcome | Abstention quality | four counts: abstained when expected (true abstention), answered when expected, abstained when an answer was expected (wrong refusal), answered when abstention was expected (unsupported answer) | results + expected answers | measured (script) |
| MC-016 | Task outcome | Human rubric score | mean rubric_score (1 to 5) | human labels | measured (human labels) if labels exist |
| MC-017 | Agent workflow | Task success rate | questions with status answered or abstained / questions | results | measured (script) |
| MC-018 | Agent workflow | Tool / retrieval failure rate | questions with a failed retrieval or tool step / questions | results + Langfuse exports | measured (script) |
| MC-019 | Agent workflow | Number of retries | retried LLM or tool calls per question | Langfuse exports | unavailable unless the exports show retries |
| MC-020 | Agent workflow | Trace completeness | traces containing every FR-025 element / traces | Langfuse exports | measured (script) if exports exist |
| MC-021 | Agent workflow | Step latency | median and maximum duration per agent/task step | Langfuse exports | measured (script) if exports exist |
| MC-022 | Agent workflow | End-to-end latency | median and maximum latency_ms; p95 only when n is at least 20 | results | measured (script) |
| MC-023 | Agent workflow | Cost / token usage | total and per-question tokens; cost only from Langfuse cost fields | results + Langfuse exports | measured (script) for tokens; cost unavailable without Langfuse cost |
| MC-024 | Operations | Upload success rate | sample files indexed / sample files submitted | run header | measured (script) |
| MC-025 | Operations | Indexing latency | per-file and total indexing duration | run header | measured (script) |
| MC-026 | Operations | Query throughput | questions per minute under load | not instrumented | unavailable |
| MC-027 | Operations | Error rate | questions with status failed / questions | results | measured (script) |
| MC-028 | Operations | Resource usage | CPU and memory during indexing and answering | not instrumented | unavailable |
| MC-029 | Safety / privacy | Prompt-injection detection rate | injection test cases handled safely / injection test cases | needs injection test cases | unavailable |
| MC-030 | Safety / privacy | Data leakage checks | answers containing content from outside the retrieved chunks or from other users | needs dedicated test cases | unavailable |
| MC-031 | Safety / privacy | Secret exposure | secret patterns found in tracked files and exported traces (count, file, pattern name) | secret scan | measured (script) |
| MC-032 | Safety / privacy | PII handling | description of what personal data is traced, logged, and stored | specs + configuration | not applicable as a number; reported qualitatively |

**Evaluation methodology**

- **EM-001 Metrics serve decisions**: the report MUST name the primary metric (MC-014) and
  its guardrails (MC-013 unsupported-claim rate, MC-015 abstention quality, MC-011 citation
  validity, MC-022 end-to-end latency, MC-023 tokens), and state for each reported metric the
  decision it supports (for example: change chunking, tune k or the minimum relevance score,
  strengthen the guardrail, change model).
- **EM-002 Relevance granularity**: retrieval relevance is judged at document level (a chunk
  is relevant if it comes from an expected source). The report MUST state that this is
  optimistic (a chunk from the right file may not contain the answer) and that MC-006 and
  MC-007 need passage labels.
- **EM-003 Correctness on answer points, not word overlap**: correctness is measured against
  the expected answer points; n-gram overlap scores (BLEU, ROUGE) MUST NOT be used, because
  they can reward an answer with the opposite meaning.
- **EM-004 Evaluation layers**: deterministic script metrics first; human labels for the
  metrics that need judgement. An LLM judge is out of scope for this version; if one is
  added later, its model, version, and prompt MUST be pinned, a model family different from
  the answering model SHOULD be used, and its scores MUST be labelled "uncalibrated" until
  agreement with human labels has been measured.
- **EM-005 Small samples**: every rate MUST show numerator and denominator; below 10
  questions, rates MUST be written as counts (for example "3/4"), not percentages, and
  results MUST be described as indicative. Latency is reported as median and maximum; p95
  only when n is at least 20, never a mean alone. Two runs MUST NOT be declared different on
  fewer than 10 questions; with more, they are compared question by question (paired).
- **EM-006 Objectives**: each success criterion with a target (SC-003 to SC-008) is reported
  as target, measured value, and met / not met / not measurable.
- **EM-007 Slices and pitfalls**: results MUST be reported per question category as well as
  overall. Fake-model and real-model runs MUST never be mixed in one metric. If the
  evaluation questions were used to tune prompts or parameters, the report MUST say so,
  since the scores are then optimistic.

**Documentation and deliverables**

- **FR-038**: The README MUST explain: installing Python dependencies; installing and
  configuring the CrewAI and Langfuse agent skills from their official pages; configuring
  CrewAI and the model provider; configuring Langfuse locally without committing
  credentials; starting the UI; uploading the sample files; asking a question; confirming
  that traces arrive in Langfuse and exporting trace summaries; running the automated tests
  and the evaluation runner; filling in the optional human labels; invoking the evaluation
  skill (prerequisite: Claude Code); and troubleshooting.
- **FR-039**: A top-level `specs/` directory MUST contain `constitution.md`, `spec.md`,
  `plan.md` (technical design), and `tasks.md` (implementation tasks) before any
  implementation code is written, and the deliverables MUST include it together with
  evidence of at least one specification iteration.
- **FR-040**: The deliverables MUST include the generated evaluation report produced by
  explicitly invoking the skill after testing.
- **FR-041**: The repository MUST include the CrewAI and Langfuse agent skills installed from
  their official pages (in `.claude/skills/`), with their origin and pinned version recorded
  in `.claude/skills/SKILLS-SOURCES.md`.

### Key Entities

- **Knowledge File**: a file submitted by the user. Attributes: original name, sanitized
  name, type, size, content fingerprint, upload time, status, rejection reason, chunk count.
- **Chunk**: a contiguous piece of text from a knowledge file. Attributes: chunk id, source
  file, position in file, page (when available), text, embedding.
- **Question Run**: one execution of the answer workflow. Attributes: request id, question,
  start/end time, status (answered, abstained, failed), guardrail decision, trace id.
- **Retrieved Evidence**: the chunks returned for a question run, with relevance scores and
  rank.
- **Answer**: the text shown to the user, its citations (chunk references), an
  evidence/uncertainty statement, and a flag indicating whether the safe response was used.
- **Evaluation Item**: a reference question with its category, expected behavior, expected
  answer points, and expected source documents (EV-002).
- **Evaluation Run**: a result file with its header and per-question results (EV-003).
- **Label Set**: optional human labels for one evaluation run (EV-006).
- **Evaluation Report**: the Markdown report, its metrics file, and its evidence manifest.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An evaluator starting from a clean environment can install the project,
  configure secrets, start the UI, upload the sample files, ask a question, see a cited
  answer, and find the matching trace by following the README alone, without help.
- **SC-002**: 100% of empty files and unsupported file types in the test set are rejected
  with a reason; 0 are indexed.
- **SC-003**: Target, reported by the evaluation: indexing the sample knowledge completes in
  under 60 seconds, embedding model download excluded.
- **SC-004**: Target, reported by the evaluation: for each answerable and multi-source
  question, at least one expected source document appears among the retrieved chunks.
- **SC-005**: 100% of displayed citations refer to chunks actually retrieved for that
  question (guardrail, verified by automated tests and by MC-011). Target, reported by the
  evaluation: each answer to an answerable question cites at least one expected source.
- **SC-006**: With the deterministic fake model, the unanswerable test question receives the
  safe response (automated test). Target, reported by the evaluation: the same holds with the
  real model.
- **SC-007**: With observability mocked, every question run produces exactly one trace with
  every FR-025 element (automated test); with real Langfuse, this is reported by MC-020.
- **SC-008**: Target, reported by the evaluation: maximum end-to-end latency on the real-model
  run is under 30 seconds per question (depends on the model provider).
- **SC-009**: The full automated test suite passes from a clean checkout without network
  access.
- **SC-010**: The evaluation report passes its self-check: no number without a source in the
  metrics file, every catalogue metric listed, every unavailable metric with a collection
  plan.
- **SC-011**: No secret, credential, `.env` file, knowledge base storage, or uploaded user
  file is present in version control or in the deliverables.

## Assumptions

- The users are a single developer/evaluator running the application locally; there is no
  multi-user access, authentication, or per-user knowledge base.
- The technology stack is fixed by the constitution: Python, CrewAI for the agent workflow,
  Langfuse for observability, Streamlit for the UI, with a local vector store and local
  embeddings; exact versions and the default model provider are decided in `plan.md`.
- A hosted model provider is reachable from the evaluator's machine for real runs, and the
  evaluator supplies their own API key; automated tests use a deterministic fake model.
- Langfuse is used either as Langfuse Cloud or a local self-hosted instance, chosen during
  planning; the README documents the chosen option.
- The evaluation skill is run with Claude Code; other agents may read
  `.agents/skills/rag-evaluation-report/` but are not tested.
- Scanned PDFs (images without text) are out of scope: no OCR is performed.
- The sample knowledge is written for the project (or taken from openly licensed sources)
  and its topic is chosen during planning; it must allow at least one question that needs
  information from more than one chunk or document.
- Default parameters (top 5 retrieved chunks, 10 MB per file, 1,000-character questions,
  minimum relevance score) are starting values that can be changed by configuration and are
  recorded in `plan.md`.
- With five questions, the evaluation is indicative; the dataset MAY be extended later
  without changing the data contract.
- The metric catalogue (MC-001 to MC-032) and the Evaluation Methodology (EM-001 to EM-007)
  are derived from the student's previous evaluation-metrics study, restricted to what
  applies to this project; they are the complete reference.
