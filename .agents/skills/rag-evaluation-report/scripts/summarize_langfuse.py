"""Summarize Langfuse trace exports of one run (standard library only).

Reads reports/langfuse/<run_id>/*.json written by scripts/export_traces.py (EV-005) and
returns per-trace presence, per-observation durations, tokens, cost, and retry counts.
Never queries Langfuse.

    python summarize_langfuse.py --root <project root> --run <run_id>
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any

_GENERATION_NAME = re.compile(r"^llm-call: (.+)$")
_TASK_SPAN = re.compile(r"^(Retriever/Researcher|Answer/Verifier)\..+$")


def step_name(name: str, obs_type: str) -> str:
    """Group observation names into stable step names (CrewAI span names carry uuids)."""
    if obs_type == "generation":
        match = _GENERATION_NAME.match(name)
        return f"generation: {match.group(1)}" if match else "generation"
    match = _TASK_SPAN.match(name)
    if match:
        return f"agent task: {match.group(1)}"
    if name.startswith("Crew_") or name.startswith("Crew."):
        return "crew kickoff"
    return name


def load_exports(root: Path, run_id: str) -> dict[str, dict[str, Any]]:
    directory = root / "reports" / "langfuse" / run_id
    if not directory.is_dir():
        return {}
    exports = {}
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        exports[str(data.get("trace_id") or path.stem)] = data
    return exports


def summarize(exports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    durations: dict[str, list[int]] = {}
    costs: list[float] = []
    retries: dict[str, int | None] = {}
    complete: dict[str, bool] = {}
    for trace_id, export in exports.items():
        presence = export.get("presence") or {}
        complete[trace_id] = bool(presence) and all(bool(v) for v in presence.values())
        retries[trace_id] = export.get("retry_count")
        for observation in export.get("observations") or []:
            name = step_name(str(observation.get("name") or ""), str(observation.get("type")))
            if observation.get("duration_ms") is not None:
                durations.setdefault(name, []).append(int(observation["duration_ms"]))
            if observation.get("cost") is not None:
                costs.append(float(observation["cost"]))
    steps = {
        name: {"median_ms": statistics.median(values), "max_ms": max(values), "n": len(values)}
        for name, values in sorted(durations.items())
    }
    return {
        "traces": sorted(exports),
        "complete": complete,
        "retry_count": retries,
        "steps": steps,
        "cost_total": round(sum(costs), 6) if costs else None,
        "cost_values": len(costs),
        "request_ids": {t: e.get("request_id") for t, e in exports.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(load_exports(args.root, args.run)), indent=2))


if __name__ == "__main__":
    main()
