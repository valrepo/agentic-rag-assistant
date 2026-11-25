"""Fixtures for the rag-evaluation-report skill scripts (SK-004)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

SKILL_DIR = Path(__file__).resolve().parents[2] / ".agents" / "skills" / "rag-evaluation-report"
FIXTURES = SKILL_DIR / "fixtures"
sys.path.insert(0, str(SKILL_DIR / "scripts"))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    shutil.copytree(FIXTURES / "project", root)
    return root


@pytest.fixture
def expected() -> dict[str, Any]:
    return json.loads((FIXTURES / "expected_metrics.json").read_text())


def _cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        return str(int(value)) if False else repr(value)
    return str(value)


def render_report(metrics: dict[str, Any]) -> str:
    """Minimal report that copies values only from the metrics file (used by check tests)."""
    run = metrics["run"]
    lines = [
        "# RAG evaluation report",
        "",
        "## 1. Summary",
        "",
        f"Run `{run['run_id']}` with model `{run['model']}`.",
        "",
        "## 2. Evidence inventory",
        "",
        "See `reports/rag-evaluation-evidence.json`.",
        "",
        "## 3. Primary metric and guardrails",
        "",
        "Primary metric: MC-014. Guardrails: MC-013, MC-015, MC-011, MC-022, MC-023.",
        "",
        "## 4. Metric tables",
        "",
        "| Id | Metric | Status | Value | n | Source | Decision supported | How to collect |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in metrics["metrics"]:
        plan = m["collection_plan"] or "-"
        source = ", ".join(f"`{i}`" for i in m["inputs"]) or "-"
        lines.append(
            f"| {m['id']} | {m['name']} | {m['status']} | {_cell(m['value'])} | {_cell(m['n'])} "
            f"| {source} | {m['decision']} | {plan} |"
        )
    tests = metrics["tests"]
    lines += [
        "",
        "## 5. Test results",
        "",
        "| Passed | Failed | Skipped | Duration (s) |",
        "|---|---|---|---|",
        f"| {tests['passed']} | {tests['failed']} | {tests['skipped']} | {tests['duration_s']} |",
        "",
        "## 6. Success criteria",
        "",
        "| Id | Measured | Verdict |",
        "|---|---|---|",
    ]
    for criterion in metrics["success_criteria"]:
        lines.append(
            f"| {criterion['id']} | {_cell(criterion['measured'])} | {criterion['verdict']} |"
        )
    traces = [q["trace_id"] for q in run.get("per_question", []) if q["trace_id"]]
    lines += [
        "",
        "## 7. Per-question results",
        "",
        ", ".join(f"`{q['id']}` {q['status']}" for q in run.get("per_question", [])),
        "",
        "## 8. Langfuse observations",
        "",
        "Traces: " + ", ".join(traces),
        "",
        "## 9. Fake-model runs",
        "",
        "Fake runs: " + ", ".join(f["run_id"] for f in metrics["fake_runs"]),
        "",
        "## 10. Provenance",
        "",
        "| Metric | Value | Source |",
        "|---|---|---|",
    ]
    for m in metrics["metrics"]:
        if m["value"] is not None:
            lines.append(f"| {m['id']} | {_cell(m['value'])} | `{m['inputs'][0]}` |")
    lines += [
        "",
        "## 11. Limitations",
        "",
        "Small sample.",
        "",
        "## 12. Data-quality concerns",
        "",
        "None noted.",
        "",
        "## 13. Privacy considerations",
        "",
        "No secrets found.",
        "",
        "## 14. Recommended next experiments",
        "",
        "Add labels.",
        "",
    ]
    return "\n".join(lines)
