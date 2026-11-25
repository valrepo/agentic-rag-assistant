---
description: "Implementation tasks for the Agentic RAG Knowledge Assistant"
---

# Tasks: Agentic RAG Knowledge Assistant

**Input**: design documents in `specs/`: [plan.md](plan.md), [spec.md](spec.md),
[research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/),
[quickstart.md](quickstart.md); decision records in `docs/adr/`.

**Tests**: required. FR-035, FR-036, and constitution X list seven minimum automated tests,
and SK-004 requires tests for the skill scripts. Within each story, write the tests first and
check that they fail before implementing. The traceability table at the end maps the seven
FR-035 areas to task ids.

**Organization**: tasks are grouped by user story (US1 to US5 from spec.md) so that each
story is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task).
- **[Story]**: user story the task belongs to (US1 to US5). Setup, Foundational, and Polish
  tasks have no story label.
- Paths are relative to the repository root (single Python project, see plan.md).

## Conventions for every task

- Python 3.13, type hints, ruff-clean; no emojis in code, docs, or reports.
- No secret, `.env` content, or absolute user path in code, logs, traces, tests, or docs.
- Requirements come only from the documents in `specs/`.
- Tests never use the network, a real LLM, or the real embedding model (FR-036).
- Commit after each task or logical group; never commit `.env`, `storage/`, or
  untracked files at the repository root.

---

## Phase 1: Setup (shared infrastructure)

**Purpose**: project skeleton, pinned dependencies, tooling.

- [ ] T001 Create `pyproject.toml` (project name `agentic-rag-assistant`, `requires-python = ">=3.13,<3.14"`, dependencies with the ranges of research.md R2: crewai, langfuse, openinference-instrumentation-crewai, streamlit, chromadb, pypdf, python-dotenv; dev group: pytest, ruff), `.python-version` containing `3.13`, then run `uv lock` and `uv sync` to create `uv.lock`; record any version that differs from research.md R2 in plan.md Technical Context
- [ ] T002 Create the package and directory skeleton of plan.md "Source Code": `app/__init__.py`, `scripts/`, `data/sample-knowledge/`, `evaluation/results/.gitkeep`, `evaluation/labels/.gitkeep`, `reports/test-results/.gitkeep`, `reports/langfuse/.gitkeep`, `tests/__init__.py`, `tests/fakes/__init__.py`, `tests/unit/`, `tests/integration/`, `tests/skill/`, `tests/data/`
- [ ] T003 [P] After T001, configure ruff (line length 100, target py313, rules E, F, I, B, UP, SIM) and pytest (`testpaths = ["tests"]`, `addopts = "-ra"`, markers `integration`, `skill`) in `pyproject.toml`
- [ ] T004 [P] Create `.env.example` with every variable of contracts/configuration.md (names with empty or default placeholder values only; hosted-provider keys such as `ANTHROPIC_API_KEY` commented out) and check that `.gitignore` already ignores `.env`, `.env.*`, `storage/`, caches, and keeps `!.env.example`

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: configuration, errors, test doubles, tracer interface, and validation of the
local model. No user story can start before this phase is complete.

- [ ] T005 Implement `Config` in `app/config.py`: frozen dataclass with one field per variable of contracts/configuration.md and its default, `Config.from_env(env: Mapping[str, str] | None = None)`: when `env` is None it loads an optional `.env` with python-dotenv (without overriding existing variables) and reads `os.environ`; when a mapping is given it reads only that mapping and never opens `.env`; parses types, validates `CHUNK_OVERLAP < CHUNK_SIZE`, `RETRIEVAL_K >= 1`, `0 <= MIN_RELEVANCE_SCORE <= 1`, and a `redacted()` method returning a dict without `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, or any `*_API_KEY`
- [ ] T006 [P] Implement the domain exceptions of contracts/app-service.md in `app/errors.py`: base `AppError(user_message: str)` and `UnsupportedFileTypeError`, `EmptyFileError`, `FileTooLargeError`, `UnreadableFileError`, `IndexingError`, `EmptyKnowledgeBaseError`, `InvalidQuestionError`, `RetrievalError`, `ProviderError`, each with a fixed user message that contains no path, secret, or stack trace (FR-030)
- [ ] T007 [P] Copy the official StubLLM from `.claude/skills/test-crewai-project/references/stub_llm.py` to `tests/fakes/stub_llm.py`, keeping its license header and adding a one-line origin note
- [ ] T008 [P] Implement the deterministic lexical fake embedding function in `tests/fakes/fake_embeddings.py`: a Chroma `EmbeddingFunction` that lowercases, tokenizes on non-alphanumerics, hashes each token (sha256, stable across runs) into 384 buckets, and returns unit-normalized vectors (research R4)
- [ ] T009 Define the tracer interface in `app/observability.py`: a `Tracer` protocol with `trace_question(request_id, question)` (context manager yielding a `QuestionTrace` with `retrieval(chunks)`, `record_result(status, guardrail_decision, error_stage, error_type)`, and `trace_id`) and `flush()`; implement `NoOpTracer` (no network, `trace_id = None`); real Langfuse comes in US3
- [ ] T010 Create `tests/conftest.py`: set `CREWAI_DISABLE_TELEMETRY=true`, `CREWAI_TRACING_ENABLED=false`, `LANGFUSE_ENABLED=false` before any import of crewai; block network access by patching `socket.socket.connect` and `socket.create_connection` so any TCP or UDP connection fails the test (Unix-domain sockets stay allowed); fixtures `tmp_config` (built with `Config.from_env(env={...})`, an explicit mapping so a local `.env` is never read; `DATA_DIR` = tmp_path; `MIN_RELEVANCE_SCORE=0.05`, suited to the lexical fake embeddings), `fake_embeddings`, `stub_llm_factory`
- [ ] T011 [P] Unit tests for configuration and errors in `tests/unit/test_config.py`: defaults match contracts/configuration.md, env overrides parse, invalid values raise, `redacted()` hides secret keys, `from_env(env={})` ignores a `.env` file present in the working directory (create one in tmp_path and chdir), error messages contain no path or secret
- [ ] T012 Spike: pull `llama3.1:8b` with Ollama and write `scripts/spike_local_model.py`, a throwaway script that runs a two-agent sequential crew (tool with `result_as_answer=True`, then `output_pydantic` with a simple model) on one hard-coded question over two inline passages; record in `docs/adr/0001-local-ollama-llm-provider.md` (section "Validation") whether tool calling and structured output worked, latency, and, if it failed, the result with the fallback `qwen2.5:7b` and the chosen default; delete the script after recording (not delivered)

**Checkpoint**: configuration, errors, fakes, and the no-op tracer exist; the default local
model is validated or replaced.

---

## Phase 3: User Story 1 - Upload and index knowledge files (Priority: P1) MVP

**Goal**: the Knowledge tab accepts several files, rejects invalid ones with a reason, and
stores valid ones as chunks with citation metadata in a persistent knowledge base.

**Independent Test**: quickstart.md scenario 3: upload the three sample files plus
`tests/data/empty.txt` and `tests/data/image.png`; the samples show `indexed (N chunks)`,
the others `rejected (reason)`; re-upload shows "already present" with no new chunk.

### Tests for User Story 1 (write first, must fail)

- [ ] T013 [US1] Create test data in `tests/data/`: `empty.txt` (0 bytes), `blank.md` (whitespace only), `image.png` (a valid 1x1 PNG), `invalid.pdf` (bytes `%PDF-1.4 garbage`), `no_text.pdf` (valid PDF with one blank page) and `two_pages.pdf` (two pages with distinct known sentences), both generated once with `scripts/make_sample_pdf.py` and committed (this task therefore runs after T020), `long.md` (about 3,000 characters with paragraphs)
- [ ] T014 [P] [US1] FR-035 test 1 in `tests/unit/test_ingestion_validation.py`: unsupported type (`.png`, `.docx`) raises `UnsupportedFileTypeError` listing `.txt, .pdf, .md`; zero-byte, whitespace-only, and no-text PDF raise `EmptyFileError`; file above `MAX_UPLOAD_MB` raises `FileTooLargeError`; invalid PDF and non-UTF-8 text raise `UnreadableFileError`; validation order is type, size, readability, emptiness
- [ ] T015 [P] [US1] FR-035 test 2 in `tests/unit/test_chunking.py`: chunks respect `CHUNK_SIZE` and `CHUNK_OVERLAP`, never cross PDF pages, carry `chunk_id = <sha256[:12]>-<index>`, `source_file` (original name), `file_sha256`, `index`, `page` (1-based for PDF, None otherwise), non-empty `text`; same content gives the same ids
- [ ] T016 [P] [US1] Unit tests for file-name sanitization in `tests/unit/test_sanitize.py`: path separators, `..`, special characters, and names over 120 characters are sanitized; the resolved path always stays inside `DATA_DIR` (FR-033)
- [ ] T017 [P] [US1] Unit tests for the knowledge base in `tests/unit/test_knowledge_base.py` (fake embeddings, tmp `DATA_DIR`): add then count chunks; metadata round trip; duplicate sha256 returns `already_present=True` and adds nothing (FR-009); `list_files()` and `clear()`; `is_empty()`; creating the client and adding chunks attempts no network connection (the T010 socket block stays silent)
- [ ] T018 [P] [US1] Integration test of `KnowledgeService.ingest` in `tests/integration/test_knowledge_service.py`: a batch with valid and invalid files returns one `FileResult` per file, the bad file does not block the others, statuses and reasons match contracts/app-service.md, and an embedding failure yields `failed (indexing error)`

### Implementation for User Story 1

- [ ] T019 [P] [US1] Write the sample knowledge in `data/sample-knowledge/` (research R11, fictional company, written for the project, freely redistributable): `model-monitoring-guide.md`, `incident-runbook.txt`, and the source text of the PDF in `scripts/sample_sources/data-retention-policy.txt`; facts must allow three single-source questions, one multi-source question (needs the runbook and the monitoring guide), and contain nothing about parental leave (unanswerable question); add `data/sample-knowledge/README.md` stating they are fictional and redistributable
- [ ] T020 [P] [US1] Implement `scripts/make_sample_pdf.py` (standard library only: writes a minimal valid multi-page PDF with Helvetica text) from `scripts/sample_sources/data-retention-policy.txt`, generate and commit `data/sample-knowledge/data-retention-policy.pdf`, and check that pypdf extracts the text
- [ ] T021 [US1] Implement `app/ingestion.py` per data-model.md KnowledgeFile and Chunk: `sanitize_name()`, `validate_and_parse(name, data, config) -> ParsedDocument` (pages list), `chunk(parsed, config) -> list[Chunk]` (paragraph-aware, 800/120 characters, never across pages), `fingerprint(data)` (sha256); raises the errors of T006
- [ ] T022 [US1] Implement `app/knowledge_base.py`: Chroma `PersistentClient` in `DATA_DIR/chroma` created with `Settings(anonymized_telemetry=False)` (chromadb 1.5.9 enables telemetry by default; principles X and XIII), one collection with cosine distance, injectable embedding function (default Chroma ONNX `all-MiniLM-L6-v2`), `add(file, chunks) -> already_present`, `search(query, k) -> list[(chunk metadata, distance)]`, `list_files()`, `clear()`, `is_empty()`; wraps Chroma exceptions in `IndexingError` or `RetrievalError`
- [ ] T023 [US1] Implement `KnowledgeService` in `app/service.py` (contracts/app-service.md): `ingest(files)` stores the original bytes under `DATA_DIR/uploads/<stored_name>`, validates, chunks, adds, measures `duration_ms`, and returns one `FileResult` per file without raising; `list_files()`, `clear()` (also removes uploads), `is_empty()`; add `build_services(config, llm=None, embedding_function=None, tracer=None)` returning the knowledge service (answer service added in US2); log one structured line per file (no content)
- [ ] T024 [US1] Implement the Knowledge tab in `app/ui.py` (contracts/ui.md): `st.tabs(["Knowledge", "Ask"])`, multi-file uploader for `.txt`, `.pdf`, `.md`, "Index files" button, `st.status` with one line per file while running, result table (name, status, chunks, "already present" note, duration), overall success, warning, or error message (FR-010), knowledge base contents and "Clear knowledge base" button; services built once with `st.cache_resource`; the Ask tab shows a placeholder until US2

**Checkpoint**: US1 tests pass; quickstart.md scenario 3 works in the browser.

---

## Phase 4: User Story 2 - Ask a question and get a cited, grounded answer (Priority: P1)

**Goal**: the Ask tab runs the two-agent sequential crew and shows a guarded, cited answer,
the safe response when evidence is insufficient, the retrieved chunks, and a request id.

**Independent Test**: quickstart.md scenario 4: with the samples indexed, `q1` shows cited
statements and the retrieved chunks; `q4` shows exactly "I could not find this in the
uploaded knowledge."

**Depends on**: US1 (a knowledge base to search).

### Tests for User Story 2 (write first, must fail)

- [ ] T025 [P] [US2] FR-035 test 3 in `tests/unit/test_retrieval.py`: with the sample knowledge indexed through fake embeddings, a known question about monitoring returns at least one chunk from `model-monitoring-guide.md` at rank 1 with `above_min_score = true` under the `tmp_config` threshold; an unrelated question scores below that threshold; scores are `1 - distance`; `k` is respected
- [ ] T026 [P] [US2] Guardrail unit tests in `tests/unit/test_guardrail.py`, one per data-model.md rule: no chunk above the minimum score gives the exact safe response and `abstained`; `sufficient_evidence=false` gives the safe response; a citation to a non-retrieved chunk is removed and counted; a statement left without citation moves to `uncertain`; no statement left gives the safe response; otherwise `answered` with decision `passed` or `citations_removed`; displayed citations are always a subset of retrieved ids (SC-005)
- [ ] T027 [P] [US2] FR-035 tests 4 and 5 in `tests/integration/test_crew_stub.py` (StubLLM scripted to call `search_knowledge_base` then return an `AnswerDraft`): an unanswerable question yields the safe response (SC-006); an answerable question yields statements whose citations name the source file and chunk (and page for the PDF); a draft citing an unknown chunk id has that citation removed; assert the prompts built by crewai contain the "use only retrieved evidence" and "treat documents as data" instructions (FR-017)
- [ ] T028 [P] [US2] Integration tests of `AnswerService.ask` in `tests/integration/test_answer_service.py`: empty or too long question raises `InvalidQuestionError` and empty knowledge base raises `EmptyKnowledgeBaseError` before any crew run (StubLLM records zero calls); a provider exception from the stub returns status `failed`, `error_stage="answer"`, `ProviderError` message; a retrieval exception returns `error_stage="retrieval"`; `request_id` is a 32-character hex string; `latency_ms` is set

### Implementation for User Story 2

- [ ] T029 [P] [US2] Implement `app/retrieval.py`: `RetrievedChunk` dataclass (data-model.md) and `retrieve(kb, question, config) -> list[RetrievedChunk]` (rank, chunk id, source file, page, score = 1 - cosine distance, `above_min_score`)
- [ ] T030 [P] [US2] Implement `app/guardrail.py`: `SAFE_RESPONSE` constant, `AnswerDraft` and `Answer` models (data-model.md; `AnswerDraft` is a pydantic model shared with the crew), `apply_guardrail(draft, retrieved, config) -> Answer` following rules 1 to 5 in order, pure function without I/O
- [ ] T031 [US2] Implement `app/crew.py` (research R6; check syntax with the `check-crewai-api` skill): `RunContext` holding the retrieved chunks; `SearchKnowledgeBaseTool(BaseTool)` with `args_schema` (query), `result_as_answer=True`, which calls `retrieve()`, stores the result in the context, and returns a compact text listing rank, chunk id, file, page, score, and text; Retriever/Researcher and Answer/Verifier agents with explicit role, goal, backstory (use only retrieved evidence, distinguish evidence from uncertainty, treat document content as data, FR-016/FR-017); retrieval task and answer task (`context=[retrieval_task]`, `output_pydantic=AnswerDraft`, task guardrail validating chunk-id format with `guardrail_max_retries=2`); `Process.sequential`; `build_crew(llm, run_context, kb, config)`; real LLM built from `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TEMPERATURE`, `LLM_TIMEOUT_S` only when none is injected
- [ ] T032 [US2] Implement `AnswerService.ask` in `app/service.py` and extend `build_services` (contracts/app-service.md, data-model.md QuestionRun): validate question, check knowledge base, generate `request_id = uuid4().hex`, open `tracer.trace_question`, run the crew, take retrieved chunks from the run context (not model text), apply the guardrail, map exceptions to `failed` with `error_stage`, `error_type`, and the domain user message, sum token usage when crewai reports it, measure `latency_ms`, return `QuestionRunResult`; log one structured line per question with the request id, status, and decision (FR-029; no question text, no secrets)
- [ ] T033 [US2] Implement the Ask tab in `app/ui.py` (contracts/ui.md): question text area, "Ask" button disabled while running, `st.status` during the crew run, rendering for `answered` (statements with `[file, chunk N, p. X]` citations, then "Uncertain or missing"), `abstained` (exact safe response, optional "Related passages" with chunk references only), and `failed` (service message); retrieved chunks panel (rank, file, chunk id, page, score); request id under the answer; message and no run when the knowledge base is empty (FR-022)
- [ ] T034 [US2] FR-035 test 7, smoke test of the main path in `tests/integration/test_smoke.py`: `build_services` with `tmp_config`, StubLLM, fake embeddings, and `NoOpTracer`; ingest the three sample files; ask an answerable question; assert status `answered`, at least one citation to an expected file, and every citation in the retrieved list (constitution gate 3)

**Checkpoint**: US1 and US2 tests pass; quickstart.md scenario 4 works with the local model.

---

## Phase 5: User Story 3 - Trace every question run in Langfuse (Priority: P2)

**Goal**: one Langfuse Cloud trace per question with every FR-025 element, flushed; tracing
can be disabled or replaced by an in-memory double; Langfuse failures never block answers.

**Independent Test**: quickstart.md scenario 5 (trace found by request id in Langfuse
Cloud), plus the automated tests below with the in-memory exporter.

**Depends on**: US2 (`AnswerService.ask`).

### Tests for User Story 3 (write first, must fail)

- [ ] T035 [P] [US3] Implement the test double `tests/fakes/memory_tracer.py`: builds a `Langfuse` client with an OpenTelemetry `InMemorySpanExporter` as `span_exporter` (no network, dummy keys), wraps it in `LangfuseTracer`, and exposes `finished_spans()` grouped by trace id
- [ ] T036 [P] [US3] FR-035 test 6 and SC-007 in `tests/integration/test_observability.py`: with `NoOpTracer` and with the in-memory tracer, the same question gives the same answer and status (FR-027); with the in-memory tracer, exactly one trace per question containing the question, the request id as session id, agent and task spans, a retriever observation with file names, chunk ids, and scores, generation observations from the StubLLM's LLM events with model name, input and output, and token usage, statuses, and an error status on a failed run (StubLLM raising); every generation observation has the same trace id as the root observation and ends before it, over 20 repeated runs (no late or orphan generation); a tracer whose export raises does not change the answer and logs a warning (FR-028); no span attribute contains the configured dummy secret key (FR-026)

### Implementation for User Story 3

- [ ] T037 [US3] Implement `LangfuseTracer` in `app/observability.py` (research R7; check API with the `langfuse` skill): `init_observability(config)` creates the Langfuse client, instruments CrewAI with OpenInference once (idempotent), registers once a CrewAI `BaseEventListener` that turns `LLMCallStartedEvent` / `LLMCallCompletedEvent` / `LLMCallFailedEvent` into `generation` observations (model, input and output messages, `usage` tokens, latency, error status): handlers run later in CrewAI's thread pool with a copy of the emitting context, so the listener pairs started and completed events by `call_id`, takes the parent from the span current at emission, and never relies on the handler thread's own context; `trace_question` calls `crewai_event_bus.flush()` (verified in crewai 1.15.45, timeout 30 s) before ending the root observation and before `langfuse.flush()`, and logs a warning if it times out, and falls back to `NoOpTracer` with a warning when disabled or keys are missing; `trace_question` opens `propagate_attributes(session_id=request_id, trace_name="rag-question")` and a root observation `rag-question` with the question as input, exposes `retrieval(chunks)` as a child observation of type `retriever` (file names, chunk ids, scores, no chunk text beyond the first 200 characters), `record_result` sets output, status level, and guardrail metadata, reads `get_current_trace_id()`, and `flush()` is called at the end of every run; every Langfuse call is wrapped so exceptions are logged and swallowed
- [ ] T038 [US3] Wire observability in `app/service.py` and `app/ui.py`: `build_services` calls `init_observability` when no tracer is injected; `QuestionRunResult.trace_id` is filled; the Ask tab shows the trace id next to the request id when available
- [ ] T039 [US3] Manual check (quickstart.md scenario 5): with `.env` filled for Langfuse Cloud, ask `q1` in the UI, find the trace by session id, check every FR-025 element, and save the trace id and a screenshot as `reports/langfuse/trace-q1.txt` and `reports/langfuse/trace-q1.png` (constitution gate 7; no key visible in the screenshot)

**Checkpoint**: US3 tests pass; a real trace is stored in `reports/langfuse/`.

---

## Phase 6: User Story 4 - Evaluate the assistant against a reference dataset (Priority: P2)

**Goal**: an evaluation dataset over the sample knowledge, a runner that writes EV-003
result files, and a read-only Langfuse export (EV-005).

**Independent Test**: quickstart.md scenario 6: `run_evaluation.py --model-kind fake` and
`--model-kind real` each write a valid result file; `export_traces.py` writes one JSON per
trace with presence flags.

**Depends on**: US2 (answers); US3 for trace ids in real runs.

### Tests for User Story 4 (write first, must fail)

- [ ] T040 [P] [US4] Dataset validation test in `tests/unit/test_evaluation_dataset.py`: both JSONL files parse, ids are unique and joined, at least five questions with at least three `answerable`, one `unanswerable` (expected `abstain`, empty points and sources), one `multi_source` with at least two expected sources; every expected source exists in `data/sample-knowledge/`
- [ ] T041 [P] [US4] Runner test in `tests/integration/test_run_evaluation.py`: run the runner function with StubLLM, fake embeddings, `NoOpTracer`, and tmp output dirs; the file has one header and one record per question; every required field of contracts/evaluation-data.md is present with the right type; `model_kind` is `fake`; the knowledge base used is isolated (the default `DATA_DIR` is untouched)
- [ ] T042 [P] [US4] Export test in `tests/unit/test_export_traces.py`: given recorded `observations.get_many` responses (JSON fixtures in `tests/data/langfuse/`, no network), the export builds the EV-005 object, computes presence flags, and contains no key, header, or token field; a missing trace is reported, not invented

### Implementation for User Story 4

- [ ] T043 [P] [US4] Write `evaluation/questions.jsonl` and `evaluation/expected_answers.jsonl` (EV-002): `q1` to `q3` answerable (one per sample file), `q4` unanswerable (parental leave, `abstain`), `q5` multi-source (runbook plus monitoring guide); each answerable item has 2 to 4 `answer_points` with `point_id` like `q1-p1` and `expected_sources` with original file names
- [ ] T044 [US4] Implement `scripts/run_evaluation.py` (EV-003): options `--model-kind fake|real`, `--output-dir evaluation/results`; builds services on a fresh temporary `DATA_DIR` (fake: StubLLM scripted per question plus fake embeddings, both imported from `tests/fakes/` as decided in plan.md, and `NoOpTracer`; real: configured model, ONNX embeddings, Langfuse), indexes `data/sample-knowledge/`, asks every question, writes `evaluation/results/<YYYYMMDDTHHMMSSZ>-<model_kind>.jsonl` with the header (git commit with `-dirty` suffix, config values, indexing summary, `total_indexing_ms` measured after a warm-up embedding call) and one record per question; flushes Langfuse at the end; prints only the output path and a status count
- [ ] T045 [US4] Implement `scripts/export_traces.py` (EV-005): `--run <run_id>` reads trace ids from the result file, calls `Langfuse().api.observations.get_many(trace_id=...)` read-only, writes `reports/langfuse/<run_id>/<trace_id>.json` with observations, `retry_count` when visible, presence flags, and `exported_at`; never writes keys, headers, or raw inputs beyond what FR-025 needs; reports traces not found
- [ ] T046 [US4] Run the evaluation: `uv run python scripts/run_evaluation.py --model-kind fake`, then with Ollama and Langfuse configured `--model-kind real`, then `uv run python scripts/export_traces.py --run <real run_id>`; before the final real run, tune `MIN_RELEVANCE_SCORE` on the ONNX embeddings: run `scripts/run_evaluation.py --model-kind real` once, read the retrieved scores per question, choose the threshold that keeps an expected source above it for q1, q2, q3, q5 and leaves every q4 chunk below it when possible, set it as the default in `app/config.py`, `.env.example`, and specs/contracts/configuration.md, and rerun; commit the result files and exports; if `MIN_RELEVANCE_SCORE` or prompts are tuned on these questions, note it in `evaluation/README.md` (EM-007; the threshold tuning above always counts)
- [ ] T047 [P] [US4] Write `evaluation/README.md`: purpose of each file, categories, how to run the runner and the export, the fake versus real distinction, and how to fill optional labels from the template written by the skill (EV-006)

**Checkpoint**: a fake and a real result file and the real-run exports exist and validate.

---

## Phase 7: User Story 5 - Produce an honest evaluation report on demand (Priority: P3)

**Goal**: the `rag-evaluation-report` skill, packaged with references, a template,
standard-library scripts, fixtures, and a self-check, produces the report from evidence only.

**Independent Test**: quickstart.md scenario 7: invoking `/rag-evaluation-report` writes the
report, metrics, and evidence files; `check_report.py` passes; all 32 metrics are listed.

**Depends on**: US4 data contract (scripts are developed against fixtures, so this phase can
start once T043 fixes the dataset format).

### Tests for User Story 5 (write first, must fail)

- [ ] T048 [P] [US5] Create fixtures in `.agents/skills/rag-evaluation-report/fixtures/`: a three-question dataset, one real and one fake result file, two trace exports, one label file, a JUnit XML, and `expected_metrics.json` with hand-checked values for MC-001 to MC-005, MC-010, MC-011 (a and b), MC-014, MC-015, MC-017, MC-020, MC-022, MC-024, MC-027
- [ ] T049 [P] [US5] Tests in `tests/skill/test_compute_metrics.py`: computed metrics equal `expected_metrics.json`; all 32 ids appear once; missing labels make label metrics `unavailable` with a collection plan; a run without exports makes MC-019 to MC-021 `unavailable`; fake runs only appear in `fake_runs`; rates below 10 questions keep numerator and denominator
- [ ] T050 [P] [US5] Tests in `tests/skill/test_collect_and_check.py`: `collect_evidence.py` records path, size, sha256, record count, and `env_file_present` without opening `.env`; the secret scan reports file, line, and pattern name only; `check_report.py` passes on a correct fixture report and fails on each SK-006 violation (unknown number, unknown trace id, unavailable with a value, missing metric id, fake run id outside section 9, answer text copied into the report)

### Implementation for User Story 5

- [ ] T051 [P] [US5] Write the skill references in `.agents/skills/rag-evaluation-report/references/`: `data-contract.md` (EV-002 to EV-006, the list of SK-003 input paths read by `collect_evidence.py`, and the output files of contracts/evaluation-report-files.md), `metric-catalogue.md` (MC-001 to MC-032 with formula, evidence, default status, decision supported, collection plan), `methodology.md` (EM-001 to EM-007), `privacy.md` (SK-007, SK-011, secret patterns list)
- [ ] T052 [P] [US5] Write `.agents/skills/rag-evaluation-report/templates/rag-evaluation-report.template.md` with the 14 sections of contracts/evaluation-report-files.md, placeholder markers for values copied from the metrics file, and the provenance table header
- [ ] T053 [P] [US5] Implement `.agents/skills/rag-evaluation-report/scripts/collect_evidence.py` (standard library): evidence manifest of SK-004 to `reports/rag-evaluation-evidence.json` covering exactly the SK-003 sources: `specs/constitution.md`, `specs/spec.md`, `specs/plan.md`, `specs/tasks.md`, `reports/test-results/junit.xml`, `evaluation/questions.jsonl`, `evaluation/expected_answers.jsonl`, every `evaluation/results/*.jsonl` (header included), every `evaluation/labels/*.jsonl` except templates, `.env.example`, `pyproject.toml`, and every `reports/langfuse/**/*.json`; git commit and dirty flag via `git` subprocess, secret scan over `git ls-files` and `reports/langfuse/` with the fixed pattern list, label template writing to `evaluation/labels/<run_id>.template.jsonl` when labels are missing
- [ ] T054 [US5] Implement `.agents/skills/rag-evaluation-report/scripts/summarize_langfuse.py` (standard library): reads `reports/langfuse/<run_id>/*.json` and returns per-observation durations, token totals, cost when present, retry counts, and presence-flag completeness for `compute_metrics.py`
- [ ] T055 [US5] Implement `.agents/skills/rag-evaluation-report/scripts/compute_metrics.py` (standard library): run selection (SK-008), every formula of the metric catalogue and its conventions (population, missing positions, macro average, zero-denominator exclusion), per-category slices (EM-007), test summary from `reports/test-results/junit.xml`, success-criteria verdicts for SC-003 to SC-008 (EM-006), writes `reports/rag-evaluation-metrics.json` per contracts/evaluation-report-files.md (depends on T054)
- [ ] T056 [US5] Implement `.agents/skills/rag-evaluation-report/scripts/check_report.py` (standard library): every SK-006 rule plus an SK-011 copy check (fails when the report contains any run of 12 or more consecutive words taken from an `answer` field of the result files or from a chunk text in the Langfuse exports), exit code 0 only when all pass, prints each violation with its section and line
- [ ] T057 [US5] Rewrite `.agents/skills/rag-evaluation-report/SKILL.md` from the draft: keep frontmatter (`user-invocable: true`, `disable-model-invocation: true`) and the explicit-invocation and never-fabricate rules; steps: run `collect_evidence.py`, run `compute_metrics.py`, fill the template by copying values only (SK-005), run `check_report.py` and fix until it passes, hand back the path and counts; read-only and privacy rules of SK-007 and SK-011; links to `references/`; remove the "Draft" note; confirm `.claude/skills/rag-evaluation-report` still resolves

**Checkpoint**: skill tests pass; the self-check works on fixtures. The deliverable report is generated in T064, after the final test run.

---

## Phase 8: Polish and cross-cutting concerns

**Purpose**: documentation, delivery hygiene, and the final quality gates.

- [ ] T058 [P] Write `README.md` (FR-034, FR-038, constitution gate 6): purpose; supported platforms (macOS arm64, Linux x86_64, CPU only works); local or trusted use only, no authentication; prerequisites (uv, Ollama, Langfuse Cloud project, Claude Code for the skill); install with `uv sync --locked`; `ollama pull llama3.1:8b`; configuring `.env` from `.env.example` without committing it; installing the CrewAI and Langfuse skills from their official pages (pointing to `.claude/skills/SKILLS-SOURCES.md`); hosted-provider alternative; starting the UI; uploading samples; asking; confirming and exporting traces; running tests with JUnit output; running the evaluation; filling labels; invoking `/rag-evaluation-report`; manual test procedure covering every "verified manually" scenario (FR-037); troubleshooting (Ollama not running, model not pulled, Langfuse keys missing, first-run embedding download)
- [ ] T059 [P] Implement `scripts/package_submission.py` (standard library): builds `dist/submission.zip` from `git ls-files` plus generated reports, dereferences `.claude/skills/rag-evaluation-report` so real files exist at both skill paths, excludes `.env`, `storage/`, caches, virtual environments, and any untracked file, and fails if any excluded or secret-like file would be included; test in `tests/unit/test_package_submission.py` on a tmp git repository
- [ ] T060 Run the quality gates and save results: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest --junitxml=reports/test-results/junit.xml` with network disabled, `uv sync --locked`; commit `reports/test-results/junit.xml` (constitution gates 1 to 3 and 5; must run before T058)
- [ ] T061 Repository hygiene review (constitution gate 4, SC-011): `git ls-files` contains no `.env`, storage, uploads, or caches; grep tracked files and `reports/langfuse/` for key patterns; check logs written during the real run contain no question text beyond ids and no secret
- [ ] T062 Run every scenario of `specs/quickstart.md` from a fresh clone in a temporary directory (constitution gate 10, SC-001) and fix any README gap found
- [ ] T063 Update `specs/plan.md` Technical Context with the final resolved versions from `uv.lock` and the validated default model, update `docs/adr/0001-local-ollama-llm-provider.md` status if the default changed, and run `/speckit-analyze` for a final consistency check
- [ ] T064 Generate the deliverable report (US5): after T046 and the final test run (T060), invoke `/rag-evaluation-report` explicitly in Claude Code; check that `reports/rag-evaluation-report.md`, `reports/rag-evaluation-metrics.json`, and `reports/rag-evaluation-evidence.json` exist and the self-check passed (FR-040, constitution gate 8)

---

## Dependencies and execution order

### Phase dependencies

- Setup (Phase 1): no dependency.
- Foundational (Phase 2): depends on Setup; blocks every user story. T012 (spike) needs
  Ollama running and may change the default model before US2.
- US1 (Phase 3): after Foundational.
- US2 (Phase 4): after US1 (needs ingestion and the knowledge base).
- US3 (Phase 5): after US2 (wraps `AnswerService.ask`).
- US4 (Phase 6): T040, T043, T047 can start after Foundational; T041 and T044 need US2;
  T045 and the real run in T046 need US3.
- US5 (Phase 7): T048 to T057 need only the data format fixed by T043. The deliverable
  report (T064, Phase 8) needs T046 and T060.
- Polish (Phase 8): T060 before T064; T064 is the last task.

### User story dependencies

```text
Setup -> Foundational -> US1 -> US2 -> US3 -> US4 (real run) -> T060 -> T062, T063 -> T064 (report)
                                         \-> US4 dataset (T043) -> US5 scripts (T048-T057)
```

### Within each story

- Tests first (they must fail), then models and pure functions, then services, then UI.
- `app/service.py` and `app/ui.py` are edited by several stories: their tasks are never
  marked [P] and run in story order.

## Parallel opportunities

- Setup: T003 and T004.
- Foundational: T006, T007, T008, then T011 (T005 and T009 are shared dependencies).
- US1: tests T014 to T018 together; T019 and T020 alongside the tests; T013 after T020.
- US2: tests T025 to T028 together; T029 and T030 together.
- US4: T040, T042, T043, T047 together.
- US5: T048 to T053 together, while US3 and US4 are in progress.
- Polish: T058 and T059.

### Parallel example: User Story 1

```text
Task: "FR-035 test 1 in tests/unit/test_ingestion_validation.py"
Task: "FR-035 test 2 in tests/unit/test_chunking.py"
Task: "Unit tests for file-name sanitization in tests/unit/test_sanitize.py"
Task: "Unit tests for the knowledge base in tests/unit/test_knowledge_base.py"
Task: "Write the sample knowledge in data/sample-knowledge/"
```

### Parallel example: User Story 5

```text
Task: "Create fixtures in .agents/skills/rag-evaluation-report/fixtures/"
Task: "Write the skill references in .agents/skills/rag-evaluation-report/references/"
Task: "Write the report template in .agents/skills/rag-evaluation-report/templates/"
Task: "Implement collect_evidence.py"
```

## Implementation strategy

### MVP first (US1 and US2)

1. Phase 1 and Phase 2, including the local-model spike (T012).
2. US1: upload and index; validate quickstart.md scenario 3.
3. US2: ask with citations and safe response; validate scenario 4 and the smoke test.
4. Stop and demo: this is the minimum useful product (both P1 stories).

### Incremental delivery

1. Add US3: real Langfuse traces, store the trace evidence.
2. Add US4: dataset, fake and real runs, trace export.
3. Add US5: the skill and its scripts, then generate the report after the final test run.
4. Polish: README, packaging, gates, fresh-clone validation.

## Traceability: FR-035 minimum tests (constitution X)

| FR-035 area | Task | Test file |
|---|---|---|
| 1. File type and empty-file validation | T014 | `tests/unit/test_ingestion_validation.py` |
| 2. Chunking and metadata preservation | T015 | `tests/unit/test_chunking.py` |
| 3. Retrieval of relevant evidence for a known question | T025 | `tests/unit/test_retrieval.py` |
| 4. Cautious answer for an unknown question | T027 (also T026) | `tests/integration/test_crew_stub.py` |
| 5. Source references when evidence is available | T027 | `tests/integration/test_crew_stub.py` |
| 6. Observability disabled or mocked | T036 | `tests/integration/test_observability.py` |
| 7. Smoke test of the main path with a fake model | T034 | `tests/integration/test_smoke.py` |

## Traceability: deliverables

| Deliverable (constitution) | Tasks |
|---|---|
| Runnable repository, `pyproject.toml`, `uv.lock` | T001 to T038 |
| Four spec files and iteration evidence | existing in `specs/` and git history |
| Setup instructions | T058 |
| `.env.example` | T004 |
| Automated tests and saved results | test tasks of T011 to T057, T059, T060 |
| Evaluation dataset, rubric, results | T043, T046 |
| Langfuse trace id or screenshot | T039, T045 |
| Installed skills and `rag-evaluation-report` | existing `.claude/skills/`, T048 to T057 |
| Evaluation report | T064 |
