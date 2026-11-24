<!--
Sync Impact Report
- Version change: (template) → 1.0.0
- Principles kept (adapted): Fixed Technology Stack, Separation of Concerns, Reproducibility,
  Configuration & Secrets, Testing Discipline, Explicit Error Handling, Security & Privacy,
  Simplicity (YAGNI).
- Principles replaced: "Model Lifecycle Management" → "Ingestion & Knowledge Base Integrity";
  "MinIO Is the System of Record" → "Grounded Answers & Hallucination Guardrail";
  "Observability" (structured logs) → "Langfuse Observability".
- Principles added: Specification-First Workflow, Agentic Workflow (CrewAI),
  Honest Evaluation & Skill Boundaries.
- Templates checked, no update needed: plan-template.md (generic Constitution Check),
  spec-template.md, tasks-template.md, .claude/skills/speckit-* (no outdated refs).
- Sections added: Deliverables. The constitution and the spec are
  self-contained (no external requirements document is normative).
- Deferred TODOs: TODO(BASELINE_VERSIONS) — exact versions are resolved and recorded during
  /speckit-plan, then this table is amended (PATCH).
-->

# Agentic RAG Knowledge Assistant Constitution

## Project Purpose

Build a small, production-minded Retrieval-Augmented Generation (RAG) application in Python. 
A user uploads knowledge files, the application indexes them, and the
user asks questions answered by a CrewAI agentic workflow using only the indexed evidence,
with citations. Every question-answer run is traced in Langfuse. After implementation and
testing, the user explicitly invokes the `rag-evaluation-report` skill to produce an honest
evaluation report.

This constitution is the highest-level project agreement. The specification, plan, data
model, tasks, and code MUST comply with it; where they conflict, this document wins.
It states *what* must hold. *How* belongs in `plan.md`.

## Conventions

The keywords MUST, MUST NOT, SHOULD, SHOULD NOT, and MAY are to be interpreted as
described in RFC 2119.

This constitution and the feature specification are self-contained: every requirement
needed to build, test, evaluate, and submit the project MUST be stated in one of them.

## Core Principles

### I. Specification-First Workflow

- No implementation code MUST be written before `spec.md`, `plan.md`, and `tasks.md` exist
  for the feature and the plan's Constitution Check passes.
- Spec Kit is the specification workflow. At least one documented specification iteration
  (e.g., a `/speckit-clarify` session or a recorded spec revision) MUST be kept as evidence.
- The submission MUST contain a top-level `specs/` directory with `constitution.md`,
  `spec.md`, `plan.md`, and `tasks.md` (copied or exported from `.specify/memory/` and
  `specs/NNN-<feature>/`).

*Verified by*: presence and dates of spec artifacts before the first implementation commit;
`/speckit-analyze` before submission.

### II. Fixed Technology Stack

- Application code and tests MUST be Python. Other languages are permitted only for
  supporting files (YAML, JSON, JSONL, TOML, Markdown, Dockerfile, Compose, Makefile, shell).
- The answer workflow MUST be implemented with CrewAI. Observability MUST use Langfuse.
  Both MUST be installed and configured from the agent skills published on their official
  pages, and the README MUST document how.
- The UI MUST be Streamlit with at least two separate views: (A) knowledge upload and
  indexing, (B) question answering.
- The vector store and the embedding model MUST be local/embeddable (no managed vector
  database service). The LLM provider MUST be selectable through configuration. The concrete
  choices are made in `plan.md` and recorded in an ADR.
- Versions MUST stay within the Technology Baseline below. Adding or replacing a stack
  component requires an ADR.

*Verified by*: dependency review of `pyproject.toml`; Constitution Check in `plan.md`.

### III. Separation of Concerns

The UI, ingestion, retrieval, agentic workflow, observability, configuration, and
evaluation MUST be separate components with these boundaries:

- **UI (Streamlit)**: rendering, input, and progress state only. MUST NOT call the vector
  store, embedding model, LLM, CrewAI, or Langfuse APIs directly.
- **Ingestion**: file validation, parsing, chunking, embedding, and storage with metadata.
  MUST NOT generate answers.
- **Retrieval**: vector search returning chunks with source metadata and scores. MUST NOT
  call the LLM.
- **Crew (agentic workflow)**: agents, tasks, orchestration, guardrail. MUST access the
  knowledge base only through the retrieval component.
- **Observability**: Langfuse setup and helpers; MUST be the only module importing the
  Langfuse SDK directly.
- **Configuration**: shared settings with no business logic.

Services MUST be importable and testable without starting Streamlit and without network.

*Verified by*: unit tests importing services without Streamlit; code review against the
module layout in `plan.md`.

### IV. Reproducibility

- Python, all dependencies, the embedding model, the LLM model name, and chunking parameters
  MUST be pinned or documented so a clean evaluator environment can reproduce the
  application from the repository and README alone.
- Exact dependency pins MUST live in `uv.lock`; `pyproject.toml` declares the Baseline
  ranges. `plan.md` (Technical Context) MUST record the resolved versions.
- The evaluation dataset (`evaluation/`) and sample knowledge (`data/sample-knowledge/`)
  MUST be versioned in the repository and MUST be freely accessible to the evaluator (no
  private or copyrighted material).

*Verified by*: `uv sync --locked` on a clean checkout; README walkthrough in a clean
environment.

### V. Configuration & Secrets

- Environment-specific settings (LLM provider keys, Langfuse keys and host, model names,
  storage paths) MUST come from environment variables, optionally a local `.env`.
- `.env.example` MUST contain variable names only (empty or placeholder values).
- Secrets, `.env`, vector-store data, model caches, and uploaded user files MUST be
  git-ignored and MUST NOT be committed or included in the deliverables.

*Verified by*: `git ls-files` hygiene check; review of `.gitignore` and `.env.example`.

### VI. Ingestion & Knowledge Base Integrity

- Supported file types MUST be at least `.txt` and `.pdf`; `.md` SHOULD be supported.
- Empty files (including whitespace-only or no extractable text) and unsupported types MUST
  be rejected with a clear message; they MUST NOT be silently accepted or indexed.
- Every chunk MUST carry metadata sufficient for citation: source file name, chunk id/index,
  and, when available, page number and character offsets.
- Per-file processing status (accepted, indexed with chunk count, or rejected with reason)
  MUST be shown to the user.
- Re-uploading the same file SHOULD NOT create duplicate chunks.

*Verified by*: unit tests for validation, chunking, and metadata preservation.

### VII. Agentic Workflow (CrewAI)

- The answer workflow MUST be a CrewAI crew with at least: a Retriever/Researcher agent
  (queries the vector store, returns chunks with metadata) and an Answer/Verifier agent
  (answers from retrieved context only, flags missing evidence, cites sources).
- Agents, tasks, inputs, expected outputs, and execution order MUST be explicit. Sequential
  process is sufficient; a more complex process requires justification in Complexity
  Tracking.
- The LLM MUST be injectable so the crew runs with a deterministic fake LLM in tests.

*Verified by*: crew unit/smoke tests with a fake LLM; code review of agent/task definitions.

### VIII. Grounded Answers & Hallucination Guardrail (NON-NEGOTIABLE)

- System prompts and task descriptions MUST instruct agents to use only retrieved evidence
  and to distinguish evidence from uncertainty.
- A hallucination guardrail MUST run before an answer is shown: when evidence is
  insufficient or a claim is unsupported by retrieved chunks, the user MUST receive a safe
  response such as "I could not find this in the uploaded knowledge."
- When evidence is available, the answer MUST include citations referencing source file and
  chunk. Citations MUST only reference chunks actually retrieved for that question.
- Retrieved document content MUST be treated as data, never as instructions (prompt-injection
  resistance).

*Verified by*: tests for the unanswerable question, citation presence, and citation validity;
evaluation dataset results.

### IX. Langfuse Observability

- Each user question MUST produce one Langfuse trace containing: the question, a
  non-sensitive request/session id, CrewAI agent and task spans (or equivalent nested
  observations), the retrieval operation with chunk metadata, LLM generation metadata
  (model name, token usage when available), latency and status of major steps, and errors
  for failed runs.
- Traces MUST NOT contain secrets and SHOULD minimize personal data.
- Observability MUST be disableable or mockable (e.g., `LANGFUSE_ENABLED=false`) so tests
  and the app run without Langfuse; Langfuse failures MUST NOT break question answering.
- The real integration MUST be demonstrated with at least one trace id or screenshot from a
  successful run, included in the submission.
- Application logs MUST be structured and include the same request id as the trace.

*Verified by*: unit tests with observability disabled/mocked; manual trace check documented
in the README.

### X. Testing Discipline

- Core services MUST have `pytest` tests that need neither network nor real LLM calls
  (fakes, mocks, deterministic embeddings or a small local model).
- Each of the following minimum automated tests MUST exist and be traceable to a task:
  1. file type and empty-file validation;
  2. document chunking and metadata preservation;
  3. retrieval returns relevant evidence for at least one known question;
  4. an unknown or unsupported question produces a cautious answer or classification;
  5. the answer contains source references when evidence is available;
  6. Langfuse instrumentation can be disabled or mocked without breaking the application;
  7. a health/smoke test exercises the main path with a deterministic fake LLM.
- An evaluation dataset of at least five questions (three answerable, one unanswerable, one
  multi-chunk/multi-document) MUST record expected answer points and expected sources.
- A repeatable manual test procedure MUST be documented, and test results MUST be saved for
  the submission.

*Verified by*: Quality Gates 2–3; traceability table in `tasks.md` or `plan.md`.

### XI. Explicit Error Handling

- Invalid uploads, indexing failures, empty knowledge base, retrieval failures, LLM/provider
  errors, and Langfuse unavailability MUST each produce a distinct, user-readable message,
  without secrets or raw stack traces.
- Services MUST raise typed domain exceptions; the UI translates them into messages.
- A visible processing state MUST be shown while indexing and while the crew runs.

*Verified by*: unit tests for each error case; manual test procedure.

### XII. Honest Evaluation & Skill Boundaries

- The student-created skill MUST be named `rag-evaluation-report`, live at
  `.agents/skills/rag-evaluation-report/SKILL.md` (or `skills/rag-evaluation-report/`), and
  declare `user-invocable: true` and `disable-model-invocation: true`.
- Its instructions MUST state that it is invoked only when the user explicitly requests an
  evaluation report. It MUST NOT run automatically during coding, upload, or question
  answering, and MUST be invoked once, explicitly, after implementation and testing.
- It MUST read the project specifications, test results, evaluation dataset, application
  configuration, and available Langfuse trace summaries, and MUST write a Markdown report to
  `reports/rag-evaluation-report.md`.
- It MUST identify which of the following metrics apply, building on the student's
  previous evaluation-metrics report:
  - **Retrieval**: Recall@k, Precision@k, Hit Rate@k, MRR, nDCG, context relevance, chunk
    coverage.
  - **Generation / RAG quality**: faithfulness/groundedness, answer relevance, context
    utilization, citation correctness, citation completeness, unsupported-claim rate.
  - **Task outcome**: correctness against expected answer points, abstention quality,
    human preference or rubric score.
  - **Agent workflow**: task success rate, tool/retrieval failure rate, number of retries,
    trace completeness, step latency, end-to-end latency, cost/token usage.
  - **Operations**: upload success rate, indexing latency, query throughput, error rate,
    resource usage.
  - **Safety / privacy**: prompt-injection detection rate, data leakage checks, secret
    exposure, PII handling.
- Metrics and Langfuse data MUST NOT be fabricated: any metric that cannot be measured MUST
  be labelled "unavailable" with an explanation of how to collect it. The report MUST include
  limitations, data-quality concerns, privacy considerations, and recommended next
  experiments.

*Verified by*: skill frontmatter review; report review against available evidence.

### XIII. Security & Privacy

- Logs and traces MUST NOT contain credentials or tokens. Full user questions MAY be traced
  (required by Principle IX) but uploaded document contents SHOULD be logged only as
  chunk ids/metadata or truncated excerpts.
- Uploaded file names MUST be sanitized before any filesystem use; paths MUST NOT resolve
  outside the configured data directory. Upload size MUST be bounded by a documented limit.
- The app has no authentication in v1; the README MUST state it is for local development or
  trusted environments only.

*Verified by*: path-safety and validation tests; README review.

### XIV. Simplicity (YAGNI)

- Build only what the specification requires. Optional features MUST NOT be started before
  all acceptance criteria and deliverables are met.
- Any added complexity (extra service, agent, framework, or infrastructure) MUST be
  justified in the plan's Complexity Tracking table; unjustified complexity fails the
  Constitution Check.

*Verified by*: Constitution Check and Complexity Tracking in `plan.md`.

## Technology Baseline

Ranges below are binding once filled; exact versions live in `uv.lock`.
TODO(BASELINE_VERSIONS): resolve and verify each component during `/speckit-plan` (install
the full stack, check CrewAI's supported Python range), then amend this table (PATCH).

| Component | Constraint | Verified version |
|---|---|---|
| Python | `.python-version`; within CrewAI's supported range | TODO |
| crewai | major line chosen at plan | TODO |
| langfuse (Python SDK) | major line chosen at plan | TODO |
| streamlit | major line chosen at plan | TODO |
| Vector store (local) | chosen at plan, ADR | TODO |
| Embedding model | pinned id + revision, ADR | TODO |
| PDF parser | chosen at plan | TODO |
| LLM provider / model | configurable; default recorded at plan | TODO |
| pytest | major line chosen at plan | TODO |
| ruff | minor line chosen at plan | TODO |

**Upgrade policy**

- Within a major line: refresh `uv.lock`, then all Quality Gates MUST pass.
- New major line, a new Python minor version, or a stack change: ADR required, then a MINOR
  constitution amendment.

## Supported Platforms

- Development: macOS on Apple Silicon (arm64) and Linux x86_64.
- CPU-only execution MUST work; GPU MAY be used when available.

## Scope Boundaries

**In scope (v1)**

- Tab A: multi-file upload (`.txt`, `.pdf`, `.md`), per-file status, parse/chunk/embed/store,
  clear success or error messages.
- Tab B: question input, processing state, cited answer, safe "not found" response.
- CrewAI sequential crew (Retriever + Answer/Verifier) with hallucination guardrail.
- Langfuse tracing with disable/mock mode for tests.
- Evaluation dataset (`evaluation/questions.jsonl`, `evaluation/expected_answers.jsonl`),
  sample knowledge, automated tests and saved results.
- `rag-evaluation-report` skill and one generated report in `reports/`.
- README, `.env.example`, `pyproject.toml` + `uv.lock`.

**Out of scope (v1)**

- Authentication, multi-user or multi-tenant knowledge bases.
- Fine-tuning, model training, or hosting a self-managed LLM server.
- Managed/cloud vector databases, cloud deployment, high availability.
- File types beyond `.txt`, `.pdf`, `.md`; OCR of scanned PDFs.

## Quality Gates & Compliance

A change or the final submission is complete only when all gates pass:

1. **Lint and format** checks pass (tooling defined in `plan.md`).
2. **Unit tests** pass without network access or real LLM calls.
3. **Smoke test** of upload → index → ask → cited answer passes with a fake LLM.
4. **Repository hygiene**: no secrets, `.env`, vector-store data, caches, or uploads tracked
   or included in the deliverables.
5. **Reproducibility**: `uv sync --locked` succeeds; configuration only from environment
   variables or documented config files.
6. **Documentation**: the README covers Python setup, CrewAI and Langfuse skill installation
   and configuration, LLM provider setup, starting the UI, uploading, asking, confirming
   traces in Langfuse, running tests, invoking the evaluation skill, and troubleshooting.
7. **Observability evidence**: at least one real Langfuse trace id or screenshot is included.
8. **Evaluation**: the `rag-evaluation-report` skill was invoked explicitly after testing
   and its report is in `reports/`.
9. **Traceability**: `specs/` contains constitution, spec, plan, and tasks; the plan's
   Constitution Check passes; one specification iteration is evidenced.
10. **Definition of done**: in a clean evaluator environment, one can install the documented
    dependencies, configure the required secrets, start the UI, upload the sample files, ask
    a question, see a cited answer, find the corresponding Langfuse trace, then explicitly
    invoke the evaluation skill and obtain a report that is honest about which metrics can
    be measured and which require additional instrumentation.

## Deliverables

The deliverables MUST include:

1. A runnable source repository.
2. The four specification files in `specs/` and evidence of one specification iteration.
3. Setup instructions for Python dependencies, CrewAI, Langfuse, the selected model
   provider, and the UI.
4. `.env.example` with variable names only.
5. Automated tests and saved test results.
6. The evaluation dataset and its expected-answer rubric.
7. At least one Langfuse trace id or screenshot from a successful question run.
8. The user-invocable `rag-evaluation-report` skill.
9. The evaluation report generated by explicitly invoking that skill after testing.

## Governance

- The specification, plan, data model, and tasks MUST be reviewed against this
  constitution before implementation. Every plan MUST include a Constitution Check mapping
  to these principles and gates.
- **Decision records**: any exception to a principle or stack choice MUST be an ADR in
  `docs/adr/NNNN-<slug>.md` with: status, date, principle affected, context, decision,
  reason, risks, and impact on reproducibility. An exception without an ADR is a violation.
- **Amendments** are made via `/speckit-constitution`, MUST update the Sync Impact Report,
  and MUST re-check dependent templates and artifacts.
- **Versioning** (semantic): MAJOR = principle removed or redefined; MINOR = principle or
  section added, or guidance materially expanded (including Baseline major changes);
  PATCH = clarifications, wording, and filling Baseline versions.
- **Compliance review**: before delivery, run
  `/speckit-analyze` and confirm every Quality Gate.

**Version**: 1.0.0 | **Ratified**: 2026-11-24 | **Last Amended**: 2026-11-24
