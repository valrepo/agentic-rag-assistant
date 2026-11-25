"""Trace export (T042, EV-005) on recorded Langfuse responses, offline."""

from __future__ import annotations

import json

from scripts.export_traces import build_export, export_run
from tests.conftest import TEST_DATA_DIR

FIXTURES = TEST_DATA_DIR / "langfuse"
FLAGS = {
    "has_question",
    "has_request_id",
    "has_agent_task_spans",
    "has_retrieval_metadata",
    "has_generation_io",
    "has_model_name",
    "has_token_usage",
    "has_latency_and_status",
    "has_error_if_failed",
}


def _observations(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text())


def test_complete_trace_has_every_flag() -> None:
    export = build_export(
        _observations("observations_ok.json"),
        trace_id="t-ok",
        request_id="req-ok",
        status="answered",
    )
    assert export["trace_id"] == "t-ok" and export["request_id"] == "req-ok"
    assert export["model"] == "ollama/llama3.1:8b"
    assert set(export["presence"]) == FLAGS
    assert all(export["presence"].values()), export["presence"]
    assert export["retry_count"] == 1, "three LLM calls where two are expected"
    retriever = next(o for o in export["observations"] if o["type"] == "retriever")
    assert retriever["duration_ms"] == 100
    generation = next(o for o in export["observations"] if o["name"].endswith("Answer/Verifier"))
    assert (generation["prompt_tokens"], generation["completion_tokens"]) == (1100, 150)
    assert generation["cost"] == 0.0
    for observation in export["observations"]:
        assert set(observation) == {
            "name",
            "type",
            "status",
            "duration_ms",
            "prompt_tokens",
            "completion_tokens",
            "cost",
        }


def test_export_contains_no_credentials_or_io() -> None:
    export = build_export(
        _observations("observations_ok.json"),
        trace_id="t-ok",
        request_id="req-ok",
        status="answered",
    )
    text = json.dumps(export)
    assert "sk-lf" not in text and "Bearer" not in text
    assert "What PSI value" not in text, "no raw question or answer text in exports"


def test_failed_trace_flags() -> None:
    export = build_export(
        _observations("observations_failed.json"),
        trace_id="t-fail",
        request_id="req-fail",
        status="failed",
    )
    presence = export["presence"]
    assert presence["has_error_if_failed"] is True
    assert presence["has_latency_and_status"] is False
    assert presence["has_retrieval_metadata"] is False
    assert presence["has_token_usage"] is False
    assert export["observations"][1]["status"] == "error"


def test_missing_root_error_flag_for_failed_run() -> None:
    observations = _observations("observations_failed.json")[:1]
    export = build_export(observations, trace_id="t-fail", request_id="req-fail", status="failed")
    assert export["presence"]["has_error_if_failed"] is False


def test_export_run_reports_missing_traces(tmp_path) -> None:
    results = tmp_path / "20261125T100000Z-real.jsonl"
    lines = [
        {"record": "header", "run_id": "20261125T100000Z-real", "model_kind": "real"},
        {
            "record": "question",
            "id": "q1",
            "request_id": "req-ok",
            "status": "answered",
            "trace_id": "t-ok",
        },
        {
            "record": "question",
            "id": "q2",
            "request_id": "req-x",
            "status": "answered",
            "trace_id": "t-missing",
        },
        {
            "record": "question",
            "id": "q3",
            "request_id": "req-y",
            "status": "answered",
            "trace_id": None,
        },
    ]
    results.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    store = {"t-ok": _observations("observations_ok.json")}

    written, missing = export_run(
        results, tmp_path / "langfuse", fetch=lambda t: store.get(t, []), sleep=lambda s: None
    )

    assert [p.name for p in written] == ["t-ok.json"]
    assert missing == ["t-missing"]
    data = json.loads(written[0].read_text())
    assert data["request_id"] == "req-ok"
    assert written[0].parent.name == "20261125T100000Z-real"


def test_camel_case_api_keys_are_understood() -> None:
    def camel(key: str) -> str:
        head, *rest = key.split("_")
        return head + "".join(part.title() for part in rest)

    observations = [
        {camel(k): v for k, v in o.items()} for o in _observations("observations_ok.json")
    ]
    assert "usageDetails" in observations[3]
    export = build_export(observations, trace_id="t-ok", request_id="req-ok", status="answered")
    assert all(export["presence"].values()), export["presence"]
    generation = next(o for o in export["observations"] if o["name"].endswith("Answer/Verifier"))
    assert (generation["prompt_tokens"], generation["cost"]) == (1100, 0.0)


def test_partial_trace_is_refetched_until_settled() -> None:
    from scripts.export_traces import fetch_settled

    full = _observations("observations_ok.json")
    partial = [o for o in full if o["name"] != "rag-question"][:3]
    reads = iter([partial, full[:5], full, full])
    observations, settled = fetch_settled(lambda t: next(reads), "t-ok", sleep=lambda s: None)
    assert settled and len(observations) == len(full)


def test_never_settled_trace_is_reported_missing() -> None:
    from scripts.export_traces import fetch_settled

    partial = _observations("observations_ok.json")[1:4]
    observations, settled = fetch_settled(
        lambda t: partial, "t-ok", attempts=3, sleep=lambda s: None
    )
    assert not settled
