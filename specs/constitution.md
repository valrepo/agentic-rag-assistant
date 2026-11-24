<!--
Sync Impact Report
- Version change: 1.0.0 → 1.1.0 (MINOR: guidance materially expanded after two independent
  reviews of the requirements).
- Modified principles:
  - I. Specification-First Workflow: the four files live in top-level `specs/` before any
    implementation (canonical location, no copies).
  - II. Fixed Technology Stack: installed CrewAI and Langfuse skills are part of the repository.
  - VI. Ingestion & Knowledge Base Integrity: `.md` stays SHOULD.
  - VIII. Grounded Answers & Hallucination Guardrail: safe response when evidence is
    insufficient; unsupported claims removed or flagged (no blanket refusal).
  - IX. Langfuse Observability: generation input/output metadata, trace flushing, evidence
    location; structured logs downgraded to SHOULD.
  - X. Testing Discipline: results locations; fake vs real model runs.
  - XI. Explicit Error Handling: Langfuse unavailability is logged, not shown to the user.
  - XII. Honest Evaluation & Skill Boundaries: invocation path, no "invoked once", metric
    catalogue and methodology in the spec, script-produced numbers, self-check, read-only.
  - III. Separation of Concerns: observability owns Langfuse and CrewAI instrumentation setup.
  - XIII. Security & Privacy: trace content rule aligned (no secrets, minimal personal data).
- Added sections: none (Deliverables and Quality Gates expanded).
- Removed sections: none.
- Templates checked, no update needed: plan-template.md (generic Constitution Check),
  spec-template.md, tasks-template.md, .claude/skills/speckit-* (no outdated refs).
- Files moved: canonical constitution is now `specs/constitution.md`;
  `.specify/memory/constitution.md` is a symbolic link to it. `.specify/feature.json` points
  to `specs`.
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
needed to build, test, evaluate, and deliver the project MUST be stated in one of them.

## Core Principles

### I. Specification-First Workflow

- Before any implementation code is written, a top-level `specs/` directory MUST contain
  `constitution.md`, `spec.md` (product requirements and acceptance criteria), `plan.md`
  (technical design), and `tasks.md` (implementation tasks), and the plan's Constitution
  Check MUST pass. Skill helper scripts and their tests count as implementation code.
- These four files in `specs/` are the canonical versions (not copies). Spec Kit is
  configured to use `specs/` as the feature directory, and `.specify/memory/constitution.md`
  is a link to `specs/constitution.md`.
- Spec Kit is the specification workflow. At least one specification iteration (for example
  a `/speckit-clarify` session recorded in `spec.md`, or a reviewed spec revision visible in
  git history) MUST be kept as evidence.

*Verified by*: git history shows the four files committed before the first implementation
commit; `/speckit-analyze` before delivery.

### II. Fixed Technology Stack

- Application code and tests MUST be Python. Other languages are permitted only for
  supporting files (YAML, JSON, JSONL, TOML, Markdown, Dockerfile, Compose, Makefile, shell).
- The answer workflow MUST be implemented with CrewAI. Observability MUST use Langfuse.
- The CrewAI and Langfuse agent skills MUST be installed from their official pages,
  committed in the repository (`.claude/skills/`), with their origin and pinned version
  recorded in `.claude/skills/SKILLS-SOURCES.md`, and the README MUST document how to install
  and configure them.
- The UI MUST be Streamlit with at least two separate views: (A) knowledge upload and
  indexing, (B) question answering.
- The vector store and the embedding model MUST be local/embeddable (no managed vector
  database service). The LLM provider MUST be selectable through configuration. The concrete
  choices are made in `plan.md` and recorded in an ADR.
- Versions MUST stay within the Technology Baseline below. Adding or replacing a stack
  component requires an ADR.

*Verified by*: dependency review of `pyproject.toml`; presence of the skills and
`SKILLS-SOURCES.md`; Constitution Check in `plan.md`.

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
- **Observability**: Langfuse setup, CrewAI instrumentation setup, and tracing helpers. Other
  components MUST NOT configure Langfuse or instrumentation themselves.
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
- Every chunk MUST carry metadata sufficient for citation: source file name and chunk
  id/index, plus page number when available.
- Uploaded file names and a basic per-file processing status MUST be shown to the user.
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
- A hallucination guardrail MUST check every answer before it is shown:
  - evidence sufficiency is decided at answer level by the Answer/Verifier agent (plus a
    configurable minimum retrieval score); when the evidence is insufficient, the user MUST
    receive exactly the safe response "I could not find this in the uploaded knowledge.";
  - otherwise, statements not supported by the retrieved chunks MUST be removed or
    explicitly marked as uncertain, and the answer MUST NOT present them as facts.
- When evidence is available, the answer MUST include citations referencing source file and
  chunk. Citations MUST only reference chunks actually retrieved for that question.
- Agent instructions SHOULD state that retrieved document content is data, never
  instructions.

*Verified by*: tests for the unanswerable question, citation presence, and citation validity;
evaluation dataset results.

### IX. Langfuse Observability

- Each user question MUST produce one Langfuse trace containing: the question, a
  non-sensitive request/session identifier, CrewAI agent and task spans (or equivalent nested
  observations), the retrieval operation with retrieved document/chunk metadata, LLM
  generation input/output metadata with model name and token usage when available, latency
  and status of major steps, and errors for failed runs.
- Traces MUST be flushed so that they are persisted in Langfuse even for short-lived runs.
- Traces MUST NOT contain secrets and SHOULD avoid unnecessary personal data.
- Observability MUST be disableable or mockable (e.g., `LANGFUSE_ENABLED=false`) so tests
  and the app run without Langfuse; Langfuse failures MUST NOT break question answering.
- The real integration MUST be demonstrated with at least one trace id or screenshot from a
  successful run, stored in `reports/langfuse/` together with the exported trace summaries
  used by the evaluation.
- Application logs SHOULD be structured and include the same request identifier as the
  trace.

*Verified by*: unit tests with observability disabled/mocked; manual trace check documented
in the README.

### X. Testing Discipline

- Core services MUST have `pytest` tests that run from a clean checkout without network or
  real LLM calls (deterministic fake LLM and deterministic fake embeddings).
- Each of the following minimum automated tests MUST exist and be traceable to a task:
  1. file type and empty-file validation;
  2. document chunking and metadata preservation;
  3. retrieval returns relevant evidence for at least one known question;
  4. an unknown or unsupported question produces a cautious answer or classification;
  5. the answer contains source references when evidence is available;
  6. Langfuse instrumentation can be disabled or mocked without breaking the application;
  7. a health/smoke test exercises the main path with a deterministic fake LLM.
- An evaluation dataset of at least five questions (three answerable, one unanswerable, one
  requiring information from more than one chunk or document) MUST record, for each
  question, the expected answer points (the rubric) and the expected source document(s).
- A repeatable manual test procedure MUST be documented in the README.
- Automated test results MUST be saved in `reports/test-results/`. Evaluation dataset results
  MUST be saved in `evaluation/results/` following the evaluation data contract in the
  specification, and each result file MUST state whether it was produced with the fake LLM
  or a real model.

*Verified by*: Quality Gates 2–3; traceability table in `tasks.md` or `plan.md`.

### XI. Explicit Error Handling

- Invalid uploads, indexing failures, empty knowledge base, retrieval failures, and
  LLM/provider errors MUST each produce a distinct, user-readable message, without secrets or
  raw stack traces. Langfuse unavailability MUST be logged and MUST NOT block the answer.
- Services MUST raise typed domain exceptions; the UI translates them into messages.
- A visible processing state MUST be shown while the crew runs, and per-file status while
  indexing.

*Verified by*: unit tests for each upload rejection reason and for a model provider failure;
manual test procedure.

### XII. Honest Evaluation & Skill Boundaries

- The student-created skill MUST be named `rag-evaluation-report`, live at
  `.agents/skills/rag-evaluation-report/SKILL.md`, and declare `user-invocable: true` and
  `disable-model-invocation: true`. It MUST also be reachable from `.claude/skills/` so that
  the user can invoke it in Claude Code as `/rag-evaluation-report`. In the repository this
  MAY be a symbolic link; the delivered archive MUST contain real files at both paths.
- Its instructions MUST state that it is invoked only when the user explicitly requests an
  evaluation report. It MUST NOT run automatically during coding, upload, or question
  answering, and is meant to be invoked after implementation and testing.
- It MUST read the project specifications, test results, evaluation dataset and results,
  application configuration, and available Langfuse trace summaries, and MUST write a
  Markdown report to `reports/rag-evaluation-report.md`.
- It MUST identify which of the following metrics apply:
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
- It MUST follow the metric catalogue and the evaluation methodology defined in the
  specification. Not every metric has to be measured: every metric MUST be listed with a
  status (measured, unavailable, or not applicable) and a reason.
- Metrics and Langfuse data MUST NOT be fabricated: numbers MUST be produced by the skill's
  deterministic scripts or come from human labels, never computed or estimated by the agent;
  the report MUST pass a mechanical self-check before it is handed back. Any metric that
  cannot be measured MUST be labelled "unavailable" with an explanation of how to collect it.
  The report MUST include limitations, data-quality concerns, privacy considerations, and
  recommended next experiments.
- The skill MUST be read-only outside `reports/` and `evaluation/labels/`, MUST NOT run the
  application, tests, or evaluation runner, and MUST NOT read `.env` files or print
  credentials.

*Verified by*: skill frontmatter review; report review against available evidence.

### XIII. Security & Privacy

- Logs and traces MUST NOT contain credentials or tokens and SHOULD avoid unnecessary
  personal data. Logs SHOULD reference document content by chunk id/metadata rather than full
  text.
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

- Development: macOS on Apple Silicon (arm64) and Linux x86_64. Windows is not tested; the
  README MUST state the supported platforms.
- CPU-only execution MUST work; GPU MAY be used when available.

## Scope Boundaries

**In scope (v1)**

- Tab A: multi-file upload (`.txt`, `.pdf`, and `.md`), per-file status,
  parse/chunk/embed/store, clear success or error messages.
- Tab B: question input, processing state, cited answer, safe "not found" response.
- CrewAI sequential crew (Retriever + Answer/Verifier) with hallucination guardrail.
- Langfuse tracing with disable/mock mode for tests.
- Evaluation dataset (`evaluation/questions.jsonl`, `evaluation/expected_answers.jsonl`),
  sample knowledge, automated tests and saved results.
- Installed CrewAI and Langfuse skills; `rag-evaluation-report` skill and one generated
  report in `reports/`.
- README, `.env.example`, `pyproject.toml` + `uv.lock`.

**Out of scope (v1)**

- Authentication, multi-user or multi-tenant knowledge bases.
- Fine-tuning, model training, or hosting a self-managed LLM server.
- Managed/cloud vector databases, cloud deployment, high availability.
- File types beyond `.txt`, `.pdf`, `.md`; OCR of scanned PDFs.

## Quality Gates & Compliance

A change or the final delivery is complete only when all gates pass:

1. **Lint and format** checks pass (tooling defined in `plan.md`).
2. **Unit tests** pass without network access or real LLM calls.
3. **Smoke test** of upload → index → ask → cited answer passes with a fake LLM.
4. **Repository hygiene**: no secrets, `.env`, vector-store data, caches, or uploads tracked
   or included in the deliverables.
5. **Reproducibility**: `uv sync --locked` succeeds; configuration only from environment
   variables or documented config files.
6. **Documentation**: the README covers Python setup, CrewAI and Langfuse skill installation
   and configuration, LLM provider setup, configuring Langfuse locally without committing
   credentials, starting the UI, uploading, asking, confirming that traces arrive in
   Langfuse, running tests and the evaluation, invoking the evaluation skill, and
   troubleshooting.
7. **Observability evidence**: at least one real Langfuse trace id or screenshot is in
   `reports/langfuse/`.
8. **Evaluation**: the `rag-evaluation-report` skill was invoked explicitly after testing
   and its report is in `reports/`.
9. **Traceability**: `specs/` contained constitution, spec, plan, and tasks before the first
   implementation commit; the plan's Constitution Check passes; one specification iteration
   is evidenced.
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
5. Automated tests and saved test results (`reports/test-results/`).
6. The evaluation dataset and its expected-answer rubric, plus saved evaluation results
   (`evaluation/results/`).
7. At least one Langfuse trace id or screenshot from a successful question run
   (`reports/langfuse/`).
8. The skills: the installed CrewAI and Langfuse skills, and the user-invocable
   `rag-evaluation-report` skill.
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

**Version**: 1.1.0 | **Ratified**: 2026-11-24 | **Last Amended**: 2026-11-24
