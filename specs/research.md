# Research: Agentic RAG Knowledge Assistant

Phase 0 output of `/speckit-plan`. Every decision below was checked on 2026-11-24 by
resolving and importing the packages with `uv` on macOS arm64 (Python 3.13.9), unless marked
otherwise.

## R1. Python version

- **Decision**: Python `>=3.13,<3.14` (`.python-version` = `3.13`).
- **Rationale**: crewai 1.15.45 declares `requires-python <3.14,>=3.10`; every other
  dependency supports 3.13.
- **Alternatives considered**: Python 3.14 (used in the previous project) is rejected because
  CrewAI does not install on it.

## R2. Dependency baseline

Resolved together with `uv` and imported successfully:

| Package | Range | Verified |
|---|---|---|
| crewai | `>=1.15,<2` | 1.15.45 |
| langfuse | `>=5.2,<6` | 5.2.0 |
| openinference-instrumentation-crewai | `>=1.1.30,<2` | 1.1.30 |
| openinference-instrumentation-openai | `>=0.1.77,<0.2` | 0.1.77 |
| streamlit | `>=1.67,<2` | 1.67.0 |
| chromadb | `>=1.5,<2` | 1.5.9 |
| pypdf | `>=7.1,<8` | 7.1.1 |
| python-dotenv | `>=1.2,<2` | 1.2.4 |
| pytest (dev) | `>=9.2,<10` | 9.2.0 |
| ruff (dev) | `>=0.17,<0.18` | 0.17.6 |

Transitive packages worth noting: openai 2.54.0 (used by CrewAI's OpenAI-compatible route),
onnxruntime 1.32.0 (Chroma's default embedding), opentelemetry-sdk 1.45.2.

## R3. LLM provider: local Ollama

- **Decision**: default provider is a local Ollama server (installed: Ollama 0.33.3) with the
  model `llama3.1:8b`, configured as `LLM_MODEL=ollama/llama3.1:8b` and
  `LLM_BASE_URL=http://localhost:11434`. The model string stays configurable, so a hosted
  provider (for example `anthropic/...` or `openai/...`) can be used by changing environment
  variables only. Recorded in ADR-0001.
- **Rationale**: chosen by the project owner (no API key, no cost). CrewAI 1.15 supports
  `ollama/...` natively in its core install through `OpenAICompatibleCompletion` (verified),
  so no extra package is needed. `llama3.1:8b` (about 5 GB) fits in 16 GB of RAM and supports
  tool calling and JSON output in Ollama.
- **Risk**: small local models are less reliable at tool calling and structured output than
  hosted models. Mitigations: the retrieval tool returns its result as the task answer
  (R6), a task-level guardrail validates the Answer/Verifier output format and retries, and
  a validation spike is the first implementation task. Fallback model if the spike fails:
  `qwen2.5:7b`.
- **Alternatives considered**: Anthropic Claude and OpenAI (hosted, need a paid key);
  rejected as default by the owner but supported by configuration.

## R4. Embeddings and vector store

- **Decision**: ChromaDB `PersistentClient` in `storage/chroma/` (git-ignored), one
  collection with cosine distance; relevance score = 1 - cosine distance. Embeddings with
  Chroma's default ONNX `all-MiniLM-L6-v2` (384 dimensions, CPU, about 80 MB downloaded on
  first use into `~/.cache/chroma`; verified working).
- **Rationale**: local, no service to run, no torch; CrewAI already depends on chromadb.
- **Tests**: a deterministic lexical fake embedding function (hashed bag of words, unit
  normalized) is injected, so tests need no download and retrieval tests stay meaningful
  (FR-036). The evaluation runner uses an isolated Chroma directory per run (EV-003).
- **Alternatives considered**: Ollama embeddings (`nomic-embed-text`) would add a second
  model pull and the `ollama` package; sentence-transformers pulls torch; FAISS has no
  metadata store.

## R5. Document parsing and chunking

- **Decision**: `.txt` and `.md` read as UTF-8 (rejected as unreadable if decoding fails);
  `.pdf` parsed page by page with pypdf. Chunking: paragraph-aware splitting with a target of
  800 characters and 120 characters of overlap, never across PDF pages, so each chunk keeps a
  page number. Chunk id = `<first 12 hex of the file SHA-256>-<index>`; the file SHA-256 is
  the duplicate key (FR-009).
- **Alternatives considered**: token-based splitters (need a tokenizer dependency);
  CrewAI knowledge sources (hide chunk ids and metadata needed for citations).

## R6. CrewAI workflow design

- **Decision**: one `Crew` with `Process.sequential` and two agents:
  1. Retriever/Researcher agent with one custom `BaseTool` `search_knowledge_base(query)`.
     The tool calls the retrieval service, records the retrieved chunks in a per-run
     context, and has `result_as_answer=True`, so the retrieval task output is exactly the
     tool output (no paraphrase by the model).
  2. Answer/Verifier agent, task `context=[retrieval_task]`, `output_pydantic=AnswerDraft`
     (sufficient_evidence, statements with chunk ids, uncertain items), with a task
     guardrail that validates the structure and retries up to 2 times.
  The deterministic hallucination guardrail (FR-018) then runs in plain Python on the draft,
  using the chunks recorded by the tool as ground truth, not the model's text.
- **Rationale**: keeps the two required agents and their tasks explicit, while making
  citations and evidence verifiable without trusting the model.
- **Alternatives considered**: a CrewAI Flow (more machinery than needed, YAGNI); running
  retrieval outside the crew (would remove the Retriever agent required by the spec).

## R7. Observability with Langfuse

- **Decision**: Langfuse Python SDK v5 (OpenTelemetry based) with Langfuse Cloud
  (`LANGFUSE_BASE_URL=https://cloud.langfuse.com`, keys in `.env`). Instrumentation:
  `CrewAIInstrumentor` (agent and task spans) and `OpenAIInstrumentor` (generation spans with
  model name and token usage, since CrewAI's Ollama route uses the OpenAI SDK). Both are
  OpenInference scopes, which Langfuse v5 exports by default (verified:
  `KNOWN_LLM_INSTRUMENTATION_SCOPE_PREFIXES` contains `openinference`).
- Per question: a root observation `rag-question` created with
  `start_as_current_observation`, inside `propagate_attributes(session_id=request_id,
  trace_name="rag-question")`; the retrieval is a child observation of type `retriever` with
  file names, chunk ids and scores; the guardrail decision is recorded as metadata; the
  trace id comes from `get_current_trace_id()`; `flush()` is called at the end of each run
  (FR-024).
- CrewAI's own telemetry and tracing are disabled with `CREWAI_DISABLE_TELEMETRY=true` and
  `CREWAI_TRACING_ENABLED=false` (exact spellings matter); `OTEL_SDK_DISABLED` is not set,
  since Langfuse needs OpenTelemetry.
- Disabled mode: `LANGFUSE_ENABLED=false` returns a no-op tracer. Test double: a Langfuse
  client built with an in-memory OpenTelemetry `span_exporter`, so tests can assert one
  trace per question and every FR-025 element without network (SC-007).
- Trace export (EV-005): `Langfuse().api.observations.get_many(trace_id=...)` (the v5 API has
  no `trace.get`; verified), written by `scripts/export_traces.py`.
- **Alternatives considered**: self-hosted Langfuse in Docker (rejected by the owner: heavy
  for the local Docker disk); LiteLLM instrumentation (CrewAI 1.15 does not route Ollama
  through LiteLLM).

## R8. UI

- **Decision**: Streamlit with `st.tabs(["Knowledge", "Ask"])`, `st.file_uploader` with
  `accept_multiple_files=True`, per-file status table, `st.status` while indexing and while
  the crew runs. The UI calls only the application service layer (constitution III).

## R9. Configuration

- **Decision**: a frozen dataclass built from environment variables, loading an optional
  `.env` with python-dotenv. No settings framework.

## R10. Testing and quality

- **Decision**: pytest with a `conftest.py` that sets the CrewAI telemetry variables, forces
  `LANGFUSE_ENABLED=false` unless a test injects the in-memory exporter, and blocks network
  access. The fake LLM is the `StubLLM` from the official CrewAI testing skill
  (`.claude/skills/test-crewai-project/references/stub_llm.py`, MIT), copied into
  `tests/fakes/`. JUnit XML is written to `reports/test-results/junit.xml`. ruff for lint
  and format.

## R11. Sample knowledge

- **Decision**: three short documents written for the project about a fictional company's
  MLOps practices (a `.md` model-monitoring guide, a `.txt` incident runbook, and a `.pdf`
  data-retention policy), so that one evaluation question needs two of them. The PDF is
  generated from its text by a small standard-library script and committed.

## R12. Evaluation skill packaging

- **Decision**: the skill keeps its instructions in `SKILL.md` and adds `references/`,
  `templates/`, `scripts/` (standard library only) and `fixtures/`, as required by SK-004.
  Its scripts are tested in `tests/skill/`. In the repository `.claude/skills/
  rag-evaluation-report` stays a symbolic link; `scripts/package_submission.py` builds the
  delivered archive with links dereferenced and checks that no secret file is included.
