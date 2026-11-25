"""Evaluation runner (EV-003). Run by the developer, never by the evaluation skill (EV-004).

Indexes the sample knowledge into an isolated, initially empty knowledge base, asks every
question of evaluation/questions.jsonl, and writes evaluation/results/<run_id>.jsonl.

    uv run python scripts/run_evaluation.py --model-kind fake   # StubLLM + fake embeddings
    uv run python scripts/run_evaluation.py --model-kind real   # configured model + Langfuse

The fake mode imports the test doubles from tests/fakes/ (plan decision 5); the real mode
never imports tests/.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.config import Config  # noqa: E402
from app.observability import LangfuseTracer, Tracer  # noqa: E402
from app.service import QuestionRunResult, Services, UploadedFile, build_services  # noqa: E402

SAMPLE_DIR = REPO_ROOT / "data" / "sample-knowledge"
QUESTIONS = REPO_ROOT / "evaluation" / "questions.jsonl"
SAMPLE_SUFFIXES = {".txt", ".pdf", ".md"}


def git_commit() -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return commit + ("-dirty" if dirty else "")


def sample_files() -> list[Path]:
    return sorted(
        p for p in SAMPLE_DIR.iterdir() if p.suffix in SAMPLE_SUFFIXES and p.name != "README.md"
    )


def load_questions(path: Path = QUESTIONS) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def question_record(item: dict[str, Any], run: QuestionRunResult) -> dict[str, Any]:
    record: dict[str, Any] = {
        "record": "question",
        "id": item["id"],
        "request_id": run.request_id,
        "status": run.status,
        "retrieved": [chunk.to_record() for chunk in run.retrieved],
        "latency_ms": run.latency_ms,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "trace_id": run.trace_id,
    }
    if run.status == "failed":
        record["error_stage"] = run.error_stage
        record["error_type"] = run.error_type
    elif run.answer is not None:
        record.update(
            answer=run.answer.text,
            draft_cited_chunk_ids=run.answer.draft_cited_chunk_ids,
            cited_chunk_ids=run.answer.cited_chunk_ids,
            citations_removed=run.answer.citations_removed,
            guardrail_decision=run.answer.guardrail_decision,
        )
    return record


def run_evaluation(
    services: Services,
    model_kind: str,
    output_dir: Path,
    questions_path: Path = QUESTIONS,
) -> Path:
    if not services.knowledge.is_empty():
        raise RuntimeError("the evaluation knowledge base must start empty")
    started = datetime.now(UTC)
    run_id = f"{started:%Y%m%dT%H%M%SZ}-{model_kind}"
    config = services.config

    services.knowledge_base.warm_up()  # excludes the embedding model download from timings
    indexing_started = time.perf_counter()
    results = services.knowledge.ingest(
        [UploadedFile(p.name, p.read_bytes()) for p in sample_files()]
    )
    total_indexing_ms = int((time.perf_counter() - indexing_started) * 1000)

    header = {
        "record": "header",
        "run_id": run_id,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "git_commit": git_commit(),
        "model": services.answers.model_name,
        "model_kind": model_kind,
        "embedding_model": services.knowledge.embedding_model,
        "k": config.retrieval_k,
        "chunk_size": config.chunk_size,
        "chunk_overlap": config.chunk_overlap,
        "min_relevance_score": config.min_relevance_score,
        "langfuse_enabled": isinstance(services.tracer, LangfuseTracer),
        "indexing": [
            {
                "file": r.original_name,
                "status": r.status,
                "chunk_count": r.chunk_count,
                "duration_ms": r.duration_ms,
            }
            for r in results
        ],
        "total_indexing_ms": total_indexing_ms,
    }
    records = [header]
    for item in load_questions(questions_path):
        run = services.answers.ask(item["question"])
        records.append(question_record(item, run))
        print(f"{item['id']}: {run.status} ({run.latency_ms} ms)")
    services.tracer.flush()

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    return path


def build_fake_services(config: Config, tracer: Tracer | None = None) -> Services:
    from app.observability import NoOpTracer
    from tests.fakes.fake_answerer import make_fake_llm
    from tests.fakes.fake_embeddings import LexicalFakeEmbeddingFunction

    return build_services(
        config,
        llm=make_fake_llm(),
        embedding_function=LexicalFakeEmbeddingFunction(),
        tracer=tracer or NoOpTracer(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the evaluation dataset (EV-003).")
    parser.add_argument("--model-kind", choices=["fake", "real"], required=True)
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "evaluation" / "results")
    args = parser.parse_args()

    base = Config.from_env()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    isolated = base.data_dir / "eval-runs" / f"{stamp}-{args.model_kind}"
    overrides = {"data_dir": isolated}
    if args.model_kind == "fake":
        overrides["min_relevance_score"] = 0.05  # suited to the lexical fake embeddings
        overrides["llm_model"] = "stub/deterministic"
    from dataclasses import replace

    config = replace(base, **overrides)
    services = build_fake_services(config) if args.model_kind == "fake" else build_services(config)
    if args.model_kind == "real" and not isinstance(services.tracer, LangfuseTracer):
        print("warning: Langfuse is not enabled; the run will have no trace ids")
    path = run_evaluation(services, args.model_kind, args.output_dir)
    lines = path.read_text().splitlines()[1:]
    statuses = [json.loads(line)["status"] for line in lines]
    counts = {s: statuses.count(s) for s in sorted(set(statuses))}
    shown = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    print(f"wrote {shown} {counts}")


if __name__ == "__main__":
    main()
