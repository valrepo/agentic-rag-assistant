# Agentic RAG Knowledge Assistant

A small, local retrieval-augmented question-answering application. You upload knowledge
files (`.txt`, `.pdf`, `.md`); a two-agent CrewAI workflow answers questions using only
those files, with citations, and a deterministic guardrail replaces unsupported answers by
"I could not find this in the uploaded knowledge." Every question is traced in Langfuse,
and the `rag-evaluation-report` skill produces an evaluation report that never invents a
measurement.

- **Intended use: local development or trusted environments only.** There is no
  authentication: anyone who can reach the UI can read and change the knowledge base.
- **Supported platforms:** macOS arm64 (tested, 16 GB RAM) and Linux x86_64. CPU-only
  works; Ollama uses Apple Metal or a GPU when available. Windows is not tested.

Design documents: `specs/` (constitution, specification, plan, tasks) and `docs/adr/`.

## Architecture

```text
Streamlit UI (app/ui.py)          tabs "Knowledge" and "Ask"
  -> services (app/service.py)    the only entry point for the UI and the evaluation runner
       ingestion (app/ingestion.py)       validation, parsing (pypdf), chunking 800/120 chars
       knowledge base (app/knowledge_base.py)  local Chroma + ONNX all-MiniLM-L6-v2 embeddings
       crew (app/crew.py)                 Retriever/Researcher -> Answer/Verifier (sequential)
       guardrail (app/guardrail.py)       citations checked against the retrieved chunks
       observability (app/observability.py)  Langfuse traces, CrewAI instrumentation
```

## 1. Prerequisites

| Tool | Version | Check |
|---|---|---|
| uv | 0.13 or later | `uv --version` |
| Python | 3.13 (installed by uv if missing) | `uv python list` |
| Ollama | 0.33 or later, running | `ollama --version` and `curl http://localhost:11434/api/version` |
| Langfuse | a Langfuse Cloud project with a public and a secret key | https://cloud.langfuse.com |
| Claude Code | only to invoke the evaluation skill | `claude --version` |

Disk: about 6 GB (model about 5 GB, embedding model about 80 MB, dependencies). RAM: about
8 GB free while answering.

## 2. Install

```sh
uv sync --locked                 # exact versions from uv.lock
ollama pull llama3.1:8b          # about 4.9 GB, once
cp .env.example .env             # then edit .env (never commit it)
```

The first indexing downloads the ONNX embedding model (about 80 MB) into `~/.cache/chroma`.

## 3. Configure

All settings come from environment variables, optionally from `.env` (git-ignored).
`.env.example` lists every variable with its default; `specs/contracts/configuration.md`
explains each one.

### Model provider (CrewAI)

The default is a local Ollama model (`docs/adr/0001-local-ollama-llm-provider.md`):

```sh
LLM_MODEL=ollama/llama3.1:8b
LLM_BASE_URL=http://localhost:11434
```

`LLM_MODEL` is a CrewAI model string, so a hosted provider can be used instead, for example
`LLM_MODEL=anthropic/<model name>` with `ANTHROPIC_API_KEY` set in `.env` (the hosted
provider's extra may need to be added with `uv add "crewai[anthropic]"`). Keep
`CREWAI_DISABLE_TELEMETRY=true` and `CREWAI_TRACING_ENABLED=false`.

### Langfuse (locally, without committing credentials)

1. In Langfuse Cloud, create a project, then Settings, API Keys, Create new API keys.
2. Put the keys in `.env` only:

   ```sh
   LANGFUSE_ENABLED=true
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_BASE_URL=https://cloud.langfuse.com   # or https://us.cloud.langfuse.com
   ```

3. Check that `.env` is ignored: `git check-ignore .env` prints `.env`.

With `LANGFUSE_ENABLED=false`, or when a key is missing (a warning is logged), the
application runs without tracing. A Langfuse outage never blocks an answer.

### Agent skills (CrewAI, Langfuse)

The official CrewAI and Langfuse agent skills are already installed in `.claude/skills/`,
pinned to the commits listed in `.claude/skills/SKILLS-SOURCES.md`. To install or update
them from their official pages instead:

```sh
npx skills add crewaiinc/skills                       # https://docs.crewai.com/en/skills
npx skills add langfuse/skills --skill "langfuse"     # https://langfuse.com/docs/api-and-data-platform/features/agent-skill
```

The project's own skill, `rag-evaluation-report`, lives in
`.agents/skills/rag-evaluation-report/` and is linked from `.claude/skills/` so that Claude
Code can invoke it.

## 4. Use the application

```sh
uv run streamlit run app/ui.py
```

Open http://localhost:8501.

### Alternative: Docker Compose (optional)

If you prefer a container, the application (not Ollama) runs with Docker Compose
(`docs/adr/0003-docker-compose-for-the-app.md`). Ollama keeps running on the host, with the
model pulled, and `.env` must exist (step 2).

```sh
docker compose up --build -d          # first build: about 2.2 GB image
docker compose logs -f app            # optional
docker compose down                   # stop; the knowledge base stays in a named volume
```

Open http://localhost:8501, or set another host port with `APP_PORT=8510 docker compose up
--build -d`. The container reaches the host Ollama at `http://host.docker.internal:11434`;
on Linux, make Ollama listen on all interfaces (`OLLAMA_HOST=0.0.0.0`). Tests, the
evaluation runner, and the evaluation skill run natively, not in the container.

1. **Knowledge** tab: choose the three files of `data/sample-knowledge/`
   (`model-monitoring-guide.md`, `incident-runbook.txt`, `data-retention-policy.pdf`) and
   click "Index files". Each file shows `indexed (N chunks)`. Other file types and empty
   files are rejected with a reason. "Clear knowledge base" removes everything.
2. **Ask** tab: type a question, for example "What PSI value fires a data drift alert?",
   and click "Ask". While the agents run, a status box is shown. The answer lists
   statements with citations `[file, chunk N, p. X]`, an "Uncertain or missing" section when
   needed, the retrieved chunks with their scores, the request id, and the trace id.
3. A question the files cannot answer, for example "What is the company's parental leave
   policy?", returns exactly "I could not find this in the uploaded knowledge."

The knowledge base persists in `storage/` (git-ignored).

## 5. Confirm that traces arrive in Langfuse

1. Ask a question in the UI and note the request id shown under the answer.
2. In Langfuse Cloud, open Tracing, then filter on Session = that request id (or open the
   trace id shown in the UI). Traces can take a few seconds to appear.
3. The trace `rag-question` contains: the question and request id, the agent and task spans
   (`Retriever/Researcher`, `Answer/Verifier`), the `search_knowledge_base` retriever
   observation (files, chunk ids, scores), one generation per model call (model name, input,
   output, token usage), latency and status of each step, and the error for failed runs.

## 6. Run the automated tests

```sh
uv run ruff check . && uv run ruff format --check .
uv run pytest --junitxml=reports/test-results/junit.xml
```

The tests run offline: network connections are blocked, the model is a deterministic stub
(`tests/fakes/stub_llm.py`, from the official CrewAI testing skill), embeddings are a
lexical fake, and Langfuse is disabled or replaced by an in-memory exporter. The seven
minimum test areas are mapped to test files in the traceability table of `specs/tasks.md`.

## 7. Run the evaluation and export traces

```sh
uv run python scripts/run_evaluation.py --model-kind fake    # pipeline check, offline
uv run python scripts/run_evaluation.py --model-kind real    # Ollama + Langfuse
uv run python scripts/export_traces.py --run <run_id printed by the real run>
```

Each run indexes the sample knowledge into its own empty knowledge base and writes
`evaluation/results/<run_id>.jsonl`. The export writes one summary per trace to
`reports/langfuse/<run_id>/` (metadata only, no text, no credentials). See
`evaluation/README.md` for the dataset and the threshold tuning disclosure.

### Optional human labels

Metrics such as faithfulness and correctness against the expected answer points need human
judgement. After the first skill run, copy `evaluation/labels/<run_id>.template.jsonl` to
`evaluation/labels/<run_id>.jsonl`, fill one record per answered question (fields explained
in `evaluation/README.md`), and invoke the skill again.

## 8. Generate the evaluation report

After the tests and the real evaluation run, in Claude Code at the repository root, type:

```text
/rag-evaluation-report
```

The skill runs only when invoked explicitly. It runs its own scripts to collect evidence and
compute every metric, writes `reports/rag-evaluation-report.md` (with
`reports/rag-evaluation-metrics.json` and `reports/rag-evaluation-evidence.json`), and hands
it back only after its self-check passes. Metrics that cannot be measured are reported as
unavailable, with how to collect them.

## 9. Manual test procedure

Run these after `uv sync --locked` and with Ollama running. Each line is one check.

| # | Steps | Expected result |
|---|---|---|
| M1 | Start the UI; open the Ask tab before indexing anything | "The knowledge base is empty. Upload and index knowledge files first."; no Ask button |
| M2 | Knowledge tab: select the three sample files plus `tests/data/empty.txt` and `tests/data/image.png`; click "Index files" | while running, a status box lists each file as processing; then the samples show `indexed (N chunks)`, `empty.txt` shows `rejected (empty file)`, `image.png` shows `rejected (unsupported file type)`; a warning names the two rejected files |
| M3 | Index `incident-runbook.txt` again | `indexed (N chunks), already present`; the contents table still shows the same chunk count |
| M4 | Ask "How quickly must a SEV1 incident be acknowledged, and when is the post-mortem due?" | while running, a status box "The agents are searching and verifying..." is shown and the Ask button is disabled; the answer cites `incident-runbook.txt`; the retrieved chunks table and the request id are shown |
| M5 | Ask "What should the on-call engineer do when a data drift alert fires?" | statements cite both `model-monitoring-guide.md` and `incident-runbook.txt` |
| M6 | Ask "What is the company's parental leave policy?" | exactly "I could not find this in the uploaded knowledge." |
| M7 | Ask an empty question | "The question is empty or too long."; no model call |
| M8 | Stop Ollama (`ollama stop llama3.1:8b` and quit the Ollama app), ask a question | "The language model is unavailable or timed out..." after the timeout; no partial answer |
| M9 | With Langfuse configured, find the trace of M4 by its request id | one trace with every element listed in section 5 |
| M10 | Set `LANGFUSE_ENABLED=false`, restart, ask M4 again | same kind of answer; no trace id shown |

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| "The language model is unavailable or timed out" | start Ollama (`ollama serve` or the Ollama app), check `curl http://localhost:11434/api/version`, check `ollama list` shows `llama3.1:8b`; on slow machines raise `LLM_TIMEOUT_S` |
| `model "llama3.1:8b" not found` in logs | `ollama pull llama3.1:8b` |
| No trace in Langfuse | check `LANGFUSE_ENABLED=true` and both keys in `.env`; check the region in `LANGFUSE_BASE_URL`; look for a "langfuse" warning in the terminal; wait a few seconds and refresh |
| First indexing is slow or fails offline | the ONNX embedding model (about 80 MB) is downloaded on first use; connect once, it is then cached in `~/.cache/chroma` |
| Every answer is the safe response | the minimum relevance score may be too high for your documents: lower `MIN_RELEVANCE_SCORE` (default 0.35) |
| `uv sync --locked` fails | update uv; the lock file needs uv 0.13 or later |
| Reset everything | "Clear knowledge base" in the UI, or delete `storage/` |
| `/rag-evaluation-report` is not found | start Claude Code from the repository root; check `.claude/skills/rag-evaluation-report/SKILL.md` exists; on Windows, `.claude/skills/rag-evaluation-report` is a symbolic link: enable symlinks in git (`git config core.symlinks true`) or copy `.agents/skills/rag-evaluation-report/` there |
| The skill reports no commit and a short secret scan | the skill expects a git checkout; from an archive without `.git`, `git ls-files` is unavailable and only the trace exports are scanned |
| Docker: the app cannot reach the model | check Ollama runs on the host; on Linux set `OLLAMA_HOST=0.0.0.0` before starting it |

## Submitted evidence

| Deliverable | Where |
|---|---|
| Specification files and iterations | `specs/` (constitution, spec, plan, tasks); iterations in `specs/checklists/requirements.md`, the constitution's Sync Impact Report, and the git history (specification commits precede the implementation commits) |
| Automated test results | `reports/test-results/junit.xml` |
| Evaluation dataset and rubric | `evaluation/questions.jsonl`, `evaluation/expected_answers.jsonl` |
| Evaluation runs and human labels | `evaluation/results/`, `evaluation/labels/` |
| Langfuse trace identifier | `reports/langfuse/trace-example.txt`, trace exports in `reports/langfuse/<run_id>/` |
| Evaluation report | `reports/rag-evaluation-report.md`, with `reports/rag-evaluation-metrics.json` and `reports/rag-evaluation-evidence.json` |
| Skills | `.agents/skills/rag-evaluation-report/`, `.claude/skills/` (CrewAI, Langfuse) |

The evaluation run was produced on the commit just before the commit that adds the
evaluation evidence. The delivery archive is built from the committed files with
`uv run python scripts/package_submission.py` (writes `dist/submission.zip`).

## Repository layout

```text
app/                 application code
scripts/             evaluation runner, trace export, sample PDF generator, packaging
data/sample-knowledge/   three fictional sample documents
evaluation/          dataset, results, labels
reports/             test results, Langfuse evidence, evaluation report
tests/               unit, integration, and skill tests; fakes
specs/               constitution, specification, plan, tasks, contracts
docs/adr/            decision records
Dockerfile, compose.yaml   optional container for the application (ADR-0003)
.agents/skills/rag-evaluation-report/   the evaluation skill
.claude/skills/      installed CrewAI, Langfuse, and Spec Kit skills
```
