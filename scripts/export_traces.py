"""Export Langfuse trace summaries for one evaluation run (EV-005). Read-only.

    uv run python scripts/export_traces.py --run <run_id>

Reads the trace ids of evaluation/results/<run_id>.jsonl, fetches their observations with
the Langfuse public API, and writes reports/langfuse/<run_id>/<trace_id>.json. Exports keep
metadata only (names, types, status, durations, tokens, cost, presence flags): no question
or answer text, no metadata values, no credentials, no HTTP headers.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

EXPECTED_LLM_CALLS = 2  # one retriever call and one answer call per question
FIELDS = "core,basic,io,model,usage,metrics,metadata"


_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")


def normalize(observation: dict[str, Any]) -> dict[str, Any]:
    """The Langfuse API returns camelCase keys (usageDetails, sessionId): use snake_case."""
    return {_CAMEL.sub("_", key).lower(): value for key, value in observation.items()}


def _type(observation: dict[str, Any]) -> str:
    return str(observation.get("type") or "").lower()


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _duration_ms(observation: dict[str, Any]) -> int | None:
    latency = observation.get("latency")
    if latency is not None:
        return int(round(float(latency) * 1000))
    start, end = (
        _parse_time(observation.get("start_time")),
        _parse_time(observation.get("end_time")),
    )
    if start and end:
        return int((end - start).total_seconds() * 1000)
    return None


def _status(observation: dict[str, Any]) -> str:
    level = str(observation.get("level") or "DEFAULT").upper()
    if level == "ERROR":
        return "error"
    if observation.get("end_time") is None and observation.get("latency") is None:
        return "incomplete"
    return "ok"


def _usage(observation: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = observation.get("usage_details") or {}
    prompt = usage.get("input", usage.get("prompt_tokens"))
    completion = usage.get("output", usage.get("completion_tokens"))
    return prompt, completion


def _json_text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, default=str)


def build_export(
    observations: list[dict[str, Any]], trace_id: str, request_id: str, status: str
) -> dict[str, Any]:
    observations = [normalize(o) for o in observations]
    root = next((o for o in observations if o.get("name") == "rag-question"), None)
    generations = [o for o in observations if _type(o) == "generation"]
    retrievers = [o for o in observations if _type(o) == "retriever"]
    names = [str(o.get("name") or "") for o in observations]

    root_input = _json_text(root.get("input")) if root else ""
    retrieval_output = " ".join(_json_text(r.get("output")) for r in retrievers)

    presence = {
        "has_question": bool(root and "question" in root_input),
        "has_request_id": bool(
            root and (root.get("session_id") == request_id or request_id in root_input)
        ),
        "has_agent_task_spans": any("Retriever/Researcher" in n for n in names)
        and any("Answer/Verifier" in n for n in names),
        "has_retrieval_metadata": bool(retrievers)
        and all(key in retrieval_output for key in ('"chunk_id"', '"file"', '"score"')),
        "has_generation_io": bool(generations)
        and all(g.get("input") is not None and g.get("output") is not None for g in generations),
        "has_model_name": bool(generations) and all(g.get("model") for g in generations),
        "has_token_usage": bool(generations) and all(_usage(g)[0] is not None for g in generations),
        "has_latency_and_status": bool(observations)
        and all(_duration_ms(o) is not None and _status(o) != "incomplete" for o in observations),
        "has_error_if_failed": status != "failed"
        or any(str(o.get("level") or "").upper() == "ERROR" for o in observations),
    }
    exported = []
    for observation in observations:
        prompt, completion = _usage(observation)
        exported.append(
            {
                "name": str(observation.get("name") or ""),
                "type": _type(observation),
                "status": _status(observation),
                "duration_ms": _duration_ms(observation),
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "cost": observation.get("total_cost"),
            }
        )
    models = [g.get("model") for g in generations if g.get("model")]
    return {
        "trace_id": trace_id,
        "request_id": request_id,
        "model": models[0] if models else None,
        "observations": exported,
        "retry_count": max(0, len(generations) - EXPECTED_LLM_CALLS) if generations else None,
        "presence": presence,
        "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def fetch_settled(
    fetch: Callable[[str], list[dict[str, Any]]],
    trace_id: str,
    attempts: int = 12,
    wait_s: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[dict[str, Any]], bool]:
    """Fetch until the trace is fully ingested: the root observation is present and the
    number of observations is the same on two consecutive reads. Langfuse ingests
    asynchronously, so a trace read right after a run can be partial."""
    previous = -1
    observations: list[dict[str, Any]] = []
    for attempt in range(attempts):
        observations = fetch(trace_id)
        has_root = any(normalize(o).get("name") == "rag-question" for o in observations)
        if has_root and len(observations) == previous:
            return observations, True
        previous = len(observations)
        if attempt < attempts - 1:
            sleep(wait_s)
    return observations, False


def export_run(
    results_path: Path,
    output_root: Path,
    fetch: Callable[[str], list[dict[str, Any]]],
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[Path], list[str]]:
    lines = [json.loads(line) for line in results_path.read_text().splitlines() if line.strip()]
    header, records = lines[0], lines[1:]
    run_dir = output_root / header["run_id"]
    written: list[Path] = []
    missing: list[str] = []
    for record in records:
        trace_id = record.get("trace_id")
        if not trace_id:
            continue
        observations, settled = fetch_settled(fetch, trace_id, sleep=sleep)
        if not observations or not settled:
            missing.append(trace_id)
            continue
        export = build_export(observations, trace_id, record["request_id"], record["status"])
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / f"{trace_id}.json"
        path.write_text(json.dumps(export, indent=2) + "\n")
        written.append(path)
    return written, missing


def langfuse_fetcher() -> Callable[[str], list[dict[str, Any]]]:
    from langfuse import Langfuse

    from app.config import Config

    config = Config.from_env()
    if not config.langfuse_configured:
        raise SystemExit("Langfuse keys are missing: set them in .env (see .env.example)")
    client = Langfuse(
        public_key=config.langfuse_public_key,
        secret_key=config.langfuse_secret_key,
        base_url=config.langfuse_base_url,
    )

    def fetch(trace_id: str) -> list[dict[str, Any]]:
        observations: list[dict[str, Any]] = []
        cursor = None
        while True:
            page = client.api.observations.get_many(
                trace_id=trace_id, fields=FIELDS, limit=100, cursor=cursor
            )
            observations.extend(o.model_dump(mode="json") for o in page.data)
            cursor = page.meta.cursor if page.meta else None
            if not cursor or not page.data:
                return observations

    return fetch


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Langfuse trace summaries (EV-005).")
    parser.add_argument("--run", required=True, help="run id, file name without .jsonl")
    parser.add_argument("--results-dir", type=Path, default=REPO_ROOT / "evaluation" / "results")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "reports" / "langfuse")
    args = parser.parse_args()
    results = args.results_dir / f"{args.run}.jsonl"
    if not results.exists():
        raise SystemExit(f"no result file for run {args.run}")
    written, missing = export_run(results, args.output_dir, langfuse_fetcher())
    print(f"exported {len(written)} trace(s) to reports/langfuse/{args.run}/")
    if missing:
        print(
            "not found or not fully ingested in Langfuse yet (rerun the export): "
            + ", ".join(missing)
        )


if __name__ == "__main__":
    main()
