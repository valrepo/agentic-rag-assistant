# Quickstart: validation guide

Runnable scenarios that prove the feature works end to end. Commands are the intended
interface once implementation is done; details live in [contracts/](contracts/) and
[data-model.md](data-model.md). The README is the user-facing version of this guide.

## Prerequisites

- macOS arm64 or Linux x86_64, about 8 GB of free RAM, about 6 GB of free disk.
- `uv` installed; Ollama installed and running (`ollama --version`, `curl
  http://localhost:11434/api/version`).
- A Langfuse Cloud project with a public and a secret key.
- Claude Code, only to invoke the evaluation skill.

## 1. Setup

```sh
uv sync --locked
ollama pull llama3.1:8b
cp .env.example .env          # then fill LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY
```

Expected: `uv sync` succeeds without resolution changes; `.env` is listed in `.gitignore`.

## 2. Automated tests (offline)

```sh
uv run ruff check . && uv run ruff format --check .
uv run pytest --junitxml=reports/test-results/junit.xml
```

Expected: all tests pass with network blocked, using the stub LLM, fake embeddings, and the
in-memory tracer. The seven FR-035 areas are covered (see the traceability table in
`tasks.md`). Gate 2 and Gate 3 of the constitution.

## 3. Upload and index (US1)

```sh
uv run streamlit run app/ui.py
```

In the "Knowledge" tab, upload the three files of `data/sample-knowledge/` plus
`tests/data/empty.txt` and `tests/data/image.png`.

Expected: the three sample files show `indexed (N chunks)`; `empty.txt` shows
`rejected (empty file)`; `image.png` shows `rejected (unsupported file type)`; an overall
message is displayed. Uploading a sample file again shows "already present" and adds no
chunk.

## 4. Ask (US2)

In the "Ask" tab, ask question `q1` from `evaluation/questions.jsonl`, then `q4`
(unanswerable).

Expected: `q1` shows statements with citations to the expected file, the retrieved chunks
panel, and a request id. `q4` shows exactly "I could not find this in the uploaded
knowledge." A processing indicator is visible during each run.

## 5. Trace in Langfuse (US3)

Open the Langfuse Cloud project, filter traces by session id = the request id shown in the
UI.

Expected: one trace `rag-question` with the question, the retriever observation (files,
chunk ids, scores), agent and task spans, generations with model name and token usage, and
statuses. Save its trace id or a screenshot in `reports/langfuse/`.

## 6. Evaluation run and trace export (US4)

```sh
uv run python scripts/run_evaluation.py --model-kind fake
uv run python scripts/run_evaluation.py --model-kind real
uv run python scripts/export_traces.py --run <real run_id>
```

Expected: two files `evaluation/results/<run_id>.jsonl` (`model_kind` `fake` and `real`)
follow [contracts/evaluation-data.md](contracts/evaluation-data.md) (header plus five
question records; trace ids in the real run); `reports/langfuse/<run_id>/` contains one JSON file per trace with
presence flags. Optional: fill `evaluation/labels/<run_id>.jsonl` from the template written
by the skill.

## 7. Evaluation report (US5)

In Claude Code, type `/rag-evaluation-report`.

Expected: `reports/rag-evaluation-report.md`, `reports/rag-evaluation-metrics.json`, and
`reports/rag-evaluation-evidence.json` are written; the self-check passes; all 32 metrics are
listed with a status; label-based metrics are "unavailable" until labels exist.

## 8. Delivery check

```sh
uv run python scripts/package_submission.py
```

Expected: an archive with real files at `.agents/skills/rag-evaluation-report/` and
`.claude/skills/rag-evaluation-report/`, without `.env`, `storage/`, caches, or virtual
environments.
