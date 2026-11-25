# Implementation Plan: Agentic RAG Knowledge Assistant

**Branch**: `main` (feature directory `specs/`) | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/spec.md`

## Summary

A local Streamlit application with two tabs: "Knowledge" validates, parses (pypdf), chunks,
and embeds uploaded `.txt`, `.pdf`, and `.md` files into a persistent ChromaDB collection
with citation metadata; "Ask" runs a sequential CrewAI crew (Retriever/Researcher agent with
a knowledge-base search tool, then Answer/Verifier agent with structured output) on a local
Ollama model, followed by a deterministic hallucination guardrail that validates citations
against the chunks actually retrieved. Every question is one Langfuse Cloud trace built from
OpenInference CrewAI and OpenAI instrumentation plus explicit root and retriever
observations. An evaluation runner, a trace export script, and the `rag-evaluation-report`
skill (instructions plus deterministic standard-library scripts and a self-check) produce an
honest evaluation report. Details: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13 (`>=3.13,<3.14`; CrewAI does not support 3.14)

**Primary Dependencies**: crewai 1.15, langfuse 5.2, openinference-instrumentation-crewai
1.1, streamlit 1.67, chromadb 1.5 (ONNX
`all-MiniLM-L6-v2` embeddings), pypdf 7.1, python-dotenv 1.2; LLM served by a local Ollama
(`llama3.1:8b`, ADR-0001). Resolved in `uv.lock` (2026-11-25): crewai 1.15.45, langfuse
5.2.0, openinference-instrumentation-crewai 1.1.30, streamlit 1.67.0, chromadb 1.5.9,
pypdf 7.1.1, python-dotenv 1.2.4, pytest 9.2.0, ruff 0.17.6, identical to research R2.
`llama3.1:8b` was validated by the T012 spike (ADR-0001, section "Validation"); the
fallback model was not needed. `MIN_RELEVANCE_SCORE` default tuned to 0.35 (T046).

**Storage**: ChromaDB persistent directory `storage/chroma/` and uploaded files in
`storage/uploads/` (both git-ignored); evaluation and report files as JSON Lines / JSON /
Markdown in the repository

**Testing**: pytest 9.2 (unit, integration, skill-script tests), StubLLM from the official
CrewAI testing skill, lexical fake embeddings, in-memory OpenTelemetry exporter for Langfuse;
ruff 0.17 for lint and format

**Target Platform**: local workstation, macOS arm64 (16 GB RAM verified) and Linux x86_64;
CPU or Apple Metal through Ollama

**Project Type**: single Python project: Streamlit web UI over a service layer, plus scripts
and an agent skill

**Performance Goals**: reported targets only (SC-003 indexing of the sample knowledge under
60 s; SC-008 maximum answer latency under 30 s on the real-model run)

**Constraints**: offline automated tests from a clean checkout; no secret in the repository,
traces, or reports; Langfuse failures never block answers; skill read-only outside
`reports/` and `evaluation/labels/`

**Scale/Scope**: one user, a handful of documents (sample set of three), five evaluation
questions, about 15 Python modules

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / Gate | Status | Evidence in this plan |
|---|---|---|
| I. Specification-first | pass | constitution, spec, plan, and tasks committed before code; 4 spec iterations in git and checklist |
| II. Fixed stack | pass with ADR | Python, CrewAI, Langfuse, Streamlit, local Chroma; Ollama default recorded in ADR-0001, Chroma and embeddings in ADR-0002; CrewAI and Langfuse skills in `.claude/skills/` with `SKILLS-SOURCES.md` |
| III. Separation of concerns | pass | module layout below; UI calls `app/service.py` only; only `app/observability.py` configures Langfuse and instrumentation |
| IV. Reproducibility | pass | `uv.lock`, `.python-version`, versions in Technical Context and Technology Baseline; run header records model, embedding model, parameters, commit |
| V. Configuration and secrets | pass | [contracts/configuration.md](contracts/configuration.md); `.env` ignored; `.env.example` names only |
| VI. Ingestion integrity | pass | validation order and chunk metadata in [data-model.md](data-model.md) |
| VII. Agentic workflow | pass | two agents, explicit tasks, sequential process, injectable LLM (research R6) |
| VIII. Grounded answers | pass | sufficiency by the Answer/Verifier plus minimum score; deterministic guardrail rules in data-model; exact safe response |
| IX. Langfuse observability | pass | one root observation per question, retriever observation, instrumentors, flush, disabled and in-memory modes, export script (research R7) |
| X. Testing discipline | pass | seven FR-035 tests mapped in `tasks.md`; offline; JUnit XML in `reports/test-results/` |
| XI. Error handling | pass | domain errors table in [contracts/app-service.md](contracts/app-service.md) |
| XII. Honest evaluation | pass | skill structure, metrics file, self-check, read-only rules in [contracts/evaluation-report-files.md](contracts/evaluation-report-files.md) |
| XIII. Security and privacy | pass | file-name sanitization, size limit, secret scan, no credentials in exports |
| XIV. Simplicity | pass | no Flow, no LLM judge, no web framework besides Streamlit; Docker Compose is optional and runs only the app (ADR-0003) |
| Scope: "self-managed LLM server" out of scope | pass with ADR | Ollama is an external prerequisite, not built or deployed by the project (ADR-0001); constitution amended to say so |

Re-check after Phase 1 design: all rows still pass; no Complexity Tracking entry needed.

## Project Structure

### Documentation (this feature)

```text
specs/
├── constitution.md      # project constitution (canonical)
├── spec.md              # feature specification
├── plan.md              # this file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── app-service.md
│   ├── configuration.md
│   ├── evaluation-data.md
│   ├── evaluation-report-files.md
│   └── ui.md
├── checklists/requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
docs/adr/                # 0001 Ollama, 0002 Chroma + ONNX embeddings, 0003 Docker Compose
```

### Source Code (repository root)

```text
app/
├── __init__.py
├── config.py            # frozen Config from environment (+ optional .env)
├── errors.py            # domain exceptions (FR-030)
├── ingestion.py         # validation, parsing (txt/md/pdf), chunking, fingerprint
├── knowledge_base.py    # Chroma wrapper: add, dedupe by sha256, search, list, clear
├── retrieval.py         # search -> RetrievedChunk list (k, scores, above_min_score)
├── crew.py              # agents, tasks, search tool (result_as_answer), AnswerDraft
├── guardrail.py         # deterministic FR-018/FR-020 rules -> Answer
├── observability.py     # Langfuse client, CrewAI instrumentor, LLM event listener, trace_question(), no-op tracer
├── service.py           # KnowledgeService, AnswerService, build_services()
└── ui.py                # Streamlit tabs (no direct Chroma/CrewAI/Langfuse calls)

Dockerfile, compose.yaml, .dockerignore   # optional container for the app (ADR-0003)

scripts/
├── run_evaluation.py    # EV-003 runner (isolated knowledge base per run)
├── export_traces.py     # EV-005 Langfuse export (read-only)
├── make_sample_pdf.py   # builds the sample PDF from its text (stdlib only)
├── sample_sources/      # source text of the sample PDF and of the test PDFs
└── package_submission.py# archive with dereferenced skill links, no secrets

data/sample-knowledge/   # 3 documents written for the project (.md, .txt, .pdf)
evaluation/
├── questions.jsonl
├── expected_answers.jsonl
├── results/             # runner output
└── labels/              # optional human labels and templates

.agents/skills/rag-evaluation-report/
├── SKILL.md
├── references/          # data-contract.md, metric-catalogue.md, methodology.md, privacy.md
├── templates/rag-evaluation-report.template.md
├── scripts/             # collect_evidence.py, compute_metrics.py, summarize_langfuse.py, check_report.py
└── fixtures/            # small dataset + expected metrics for script tests
.claude/skills/rag-evaluation-report -> ../../.agents/skills/rag-evaluation-report

tests/
├── conftest.py          # env vars, network block, fixtures
├── fakes/               # stub_llm.py (official CrewAI testing skill), fake_answerer.py (deterministic
│                        # extractive answers for the StubLLM), fake_embeddings.py, memory_tracer.py
├── data/                # small test files (empty.txt, image.png, invalid.pdf, ...)
├── unit/                # ingestion, knowledge base, retrieval, guardrail, config, observability
├── integration/         # crew with StubLLM, service end to end, smoke test
└── skill/               # tests of the evaluation skill scripts on fixtures

reports/
├── test-results/        # junit.xml
└── langfuse/            # trace id / screenshot and exports
```

**Structure Decision**: single Python project. `app/` holds the application with one module
per constitution III component; `scripts/` holds developer-run tools; the evaluation skill is
self-contained under `.agents/skills/` with its own scripts and fixtures, tested from
`tests/skill/`.

## Key design decisions

1. **Citations are verified against the tool's record, not model text** (R6): the search
   tool stores the retrieved chunks in a per-run context and returns them as the retrieval
   task's answer (`result_as_answer=True`); the guardrail uses that record.
2. **Local model risk is handled up front**: the first implementation task is a spike that
   runs the crew on `llama3.1:8b` for one sample question to confirm tool calling and
   structured output; fallback `qwen2.5:7b` (ADR-0001).
3. **One trace per question** (FR-024): `AnswerService.ask()` wraps the crew in
   `trace_question(request_id, question)`, which opens the root observation inside
   `propagate_attributes(session_id=request_id, trace_name="rag-question")`, adds the
   retriever child observation, receives generation observations from the CrewAI LLM event
   listener (research R7),
   records the guardrail decision and status, returns the trace id, and flushes.
4. **Tests never touch the network**: StubLLM, lexical fake embeddings, and either the no-op
   tracer or a Langfuse client with an in-memory span exporter (SC-007 test double).
5. **Fake-mode evaluation reuses the test doubles**: `scripts/run_evaluation.py --model-kind
   fake` imports the StubLLM and the lexical fake embeddings from `tests/fakes/` (a package
   of the repository, development only). No copy of the fakes lives in `app/`; the real
   mode never imports `tests/`.
6. **Configuration in tests never reads `.env`**: `Config.from_env(env=...)` with an
   explicit mapping skips the `.env` file; test fixtures always pass a mapping, with a
   minimum relevance score suited to the lexical fake embeddings.
7. **The evaluation skill does no arithmetic**: scripts produce the metrics file; the agent
   fills the template from it; `check_report.py` gates the hand-back.

## Complexity Tracking

No violation to justify.
