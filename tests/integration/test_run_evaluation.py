"""Evaluation runner (T041, EV-003) with the fake model, offline."""

from __future__ import annotations

import json
import re

from app.observability import NoOpTracer
from scripts.run_evaluation import build_fake_services, run_evaluation
from tests.conftest import REPO_ROOT, make_config

HEADER_FIELDS = {
    "record": str,
    "run_id": str,
    "started_at": str,
    "git_commit": str,
    "model": str,
    "model_kind": str,
    "embedding_model": str,
    "k": int,
    "chunk_size": int,
    "chunk_overlap": int,
    "min_relevance_score": float,
    "langfuse_enabled": bool,
    "indexing": list,
    "total_indexing_ms": int,
}
ALWAYS = {"record", "id", "request_id", "status", "retrieved", "latency_ms"}
WHEN_NOT_FAILED = {
    "answer",
    "draft_cited_chunk_ids",
    "cited_chunk_ids",
    "citations_removed",
    "guardrail_decision",
}


def test_fake_run_writes_a_valid_result_file(tmp_path) -> None:
    default_storage = REPO_ROOT / "storage" / "chroma"
    before = sorted(default_storage.rglob("*")) if default_storage.exists() else []
    config = make_config(tmp_path / "isolated")
    services = build_fake_services(config, tracer=NoOpTracer())

    path = run_evaluation(services, model_kind="fake", output_dir=tmp_path / "results")

    lines = [json.loads(line) for line in path.read_text().splitlines()]
    header, records = lines[0], lines[1:]
    assert re.fullmatch(r"\d{8}T\d{6}Z-fake", header["run_id"])
    assert path.name == header["run_id"] + ".jsonl"
    for field, kind in HEADER_FIELDS.items():
        assert isinstance(header[field], kind), field
    assert header["record"] == "header" and header["model_kind"] == "fake"
    assert header["model"] == "stub/deterministic"
    assert header["embedding_model"] == "lexical-fake"
    assert header["langfuse_enabled"] is False
    assert [i["status"] for i in header["indexing"]] == ["indexed"] * 3
    assert {i["file"] for i in header["indexing"]} == {
        "model-monitoring-guide.md",
        "incident-runbook.txt",
        "data-retention-policy.pdf",
    }

    assert [r["id"] for r in records] == ["q1", "q2", "q3", "q4", "q5"]
    for record in records:
        assert record["record"] == "question"
        assert set(record) >= ALWAYS
        assert record["status"] in {"answered", "abstained", "failed"}
        if record["status"] != "failed":
            assert set(record) >= WHEN_NOT_FAILED
            assert set(record["cited_chunk_ids"]) <= {r["chunk_id"] for r in record["retrieved"]}
        for chunk in record["retrieved"]:
            assert set(chunk) == {"rank", "file", "chunk_id", "score", "above_min_score"}
        assert record["trace_id"] is None
    by_id = {r["id"]: r for r in records}
    assert by_id["q4"]["status"] == "abstained"
    assert by_id["q1"]["status"] == "answered"

    after = sorted(default_storage.rglob("*")) if default_storage.exists() else []
    assert before == after, "the default knowledge base is untouched"
