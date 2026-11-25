"""collect_evidence.py and check_report.py on the fixture project (T050)."""

from __future__ import annotations

import json

import check_report
import collect_evidence
import compute_metrics
import pytest

from tests.skill.conftest import render_report

pytestmark = pytest.mark.skill


def _prepare(project) -> dict:
    evidence = collect_evidence.collect(project)
    (project / "reports" / "rag-evaluation-evidence.json").write_text(json.dumps(evidence))
    metrics = compute_metrics.compute(project)
    (project / "reports" / "rag-evaluation-metrics.json").write_text(json.dumps(metrics))
    return metrics


def _write(project, text: str) -> None:
    (project / "reports" / "rag-evaluation-report.md").write_text(text)


def test_evidence_manifest(project) -> None:
    (project / ".env").write_text("LANGFUSE_SECRET_KEY=sk-lf-must-never-be-read-0000\n")
    evidence = collect_evidence.collect(project)
    files = {f["path"]: f for f in evidence["files"]}
    results = files["evaluation/results/20261101T100000Z-real.jsonl"]
    assert results["exists"] and results["records"] == 4 and len(results["sha256"]) == 64
    assert results["size_bytes"] > 0 and results["modified_at"].endswith("Z")
    assert files["specs/spec.md"]["exists"] is False
    assert evidence["env_file_present"] is True
    assert ".env" not in files
    assert "sk-lf-must-never-be-read" not in json.dumps(evidence)
    assert "1" * 32 in evidence["trace_ids"]
    assert evidence["label_template"] is None, "labels exist for the latest real run"


def test_secret_scan_reports_location_and_pattern_only(project) -> None:
    leaked = project / "reports" / "langfuse" / "20261101T100000Z-real" / "leak.json"
    leaked.write_text('{"note": "key sk-lf-abcdef1234567890 here"}\n')
    scan = collect_evidence.collect(project)["secret_scan"]
    assert scan["findings"] == [
        {
            "file": "reports/langfuse/20261101T100000Z-real/leak.json",
            "line": 1,
            "pattern": "langfuse_secret_key",
        }
    ]
    assert "abcdef1234567890" not in json.dumps(scan)


def test_correct_report_passes(project) -> None:
    metrics = _prepare(project)
    _write(project, render_report(metrics))
    assert check_report.check(project) == []


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda t: t.replace("| 2500 |", "| 2400 |", 1), "number 2400"),
        (lambda t: t + "\nTrace " + "9" * 32 + "\n", "not in the evidence"),
        (
            lambda t: t.replace(
                "| MC-026 | Query throughput | unavailable | - |",
                "| MC-026 | Query throughput | unavailable | 12 |",
            ),
            "has a value",
        ),
        (lambda t: t.replace("MC-030", "MC-0XX"), "MC-030 is missing"),
        (
            lambda t: t.replace(
                "## 11. Limitations", "## 11. Limitations\n\nSee 20261101T090000Z-fake."
            ),
            "outside section 9",
        ),
        (
            lambda t: (
                t + "\nAlpha is the first stage of the fixture pipeline and it is checked every "
                "single day.\n"
            ),
            "copies answer text",
        ),
        (lambda t: t.replace("## 12. Data-quality concerns", "## 12. Data quality"), "section 12"),
    ],
)
def test_each_violation_fails(project, mutation, expected) -> None:
    metrics = _prepare(project)
    _write(project, mutation(render_report(metrics)))
    problems = check_report.check(project)
    assert any(expected in p for p in problems), problems


def test_unavailable_row_without_plan_fails(project) -> None:
    metrics = _prepare(project)
    text = render_report(metrics)
    line = next(row for row in text.splitlines() if row.startswith("| MC-026 "))
    cells = line.split("|")
    cells[-2] = " - "
    _write(project, text.replace(line, "|".join(cells)))
    assert any("no collection plan" in p for p in check_report.check(project))


def test_missing_files_fail(project) -> None:
    assert check_report.check(project) == ["missing reports/rag-evaluation-report.md"]


def test_assigned_secret_matches_literals_not_code(project) -> None:
    sample = project / "reports" / "langfuse" / "20261101T100000Z-real" / "sample.json"
    sample.write_text(
        "\n".join(
            [
                "token = _ACTIVE_TRACE.set(trace)",
                'api_key = "AbCdEfGh0123456789xyz"',
                "DB_PASSWORD=Zx9Zx9Zx9Zx9Zx9Zx9Zx9",
                "secret_key=config.langfuse_secret_key,",
            ]
        )
        + "\n"
    )
    findings = collect_evidence.collect(project)["secret_scan"]["findings"]
    lines = sorted(f["line"] for f in findings if f["file"].endswith("sample.json"))
    assert lines == [2, 3]
