"""compute_metrics.py on the fixture project (T049)."""

from __future__ import annotations

import json
import re
import shutil

import collect_evidence
import compute_metrics
import pytest

from tests.skill.conftest import SKILL_DIR

pytestmark = pytest.mark.skill


def _run(project):
    evidence = collect_evidence.collect(project)
    (project / "reports" / "rag-evaluation-evidence.json").write_text(json.dumps(evidence))
    return compute_metrics.compute(project)


def _by_id(result):
    return {m["id"]: m for m in result["metrics"]}


def test_metrics_match_hand_checked_values(project, expected) -> None:
    metrics = _by_id(_run(project))
    for metric_id, values in expected.items():
        if metric_id.startswith("_"):
            continue
        for field, value in values.items():
            assert metrics[metric_id][field] == value, (metric_id, field)


def test_details_and_success_criteria(project, expected) -> None:
    result = _run(project)
    metrics = _by_id(result)
    details = expected["_details"]
    assert metrics["MC-011"]["details"]["citations_removed_total"] == details["MC-011_removed"]
    assert metrics["MC-011"]["details"]["support"]["value"] == details["MC-011_support"]
    assert metrics["MC-022"]["details"]["median_ms"] == details["MC-022_median"]
    assert metrics["MC-023"]["details"]["cost_total"] == details["MC-023_cost"]
    for step, values in details["MC-021_steps"].items():
        for field, value in values.items():
            assert metrics["MC-021"]["details"][step][field] == value
    verdicts = {c["id"]: c["verdict"] for c in result["success_criteria"]}
    assert verdicts == details["SC"]
    tests = result["tests"]
    assert {k: tests[k] for k in details["tests"]} == details["tests"]
    assert tests["fr035_areas"]["2. chunking and metadata preservation"]["passed"] == 1


def test_every_catalogue_id_once_with_valid_status(project) -> None:
    result = _run(project)
    ids = [m["id"] for m in result["metrics"]]
    assert ids == [f"MC-{i:03d}" for i in range(1, 33)]
    allowed = {"measured (script)", "measured (human labels)", "unavailable", "not applicable"}
    for metric in result["metrics"]:
        assert metric["status"] in allowed
        if metric["status"] in ("unavailable", "not applicable"):
            assert metric["value"] is None and metric["reason"]
        if metric["status"] == "unavailable":
            assert metric["collection_plan"]
        if metric["numerator"] is not None:
            assert metric["denominator"] is not None


def test_run_selection(project) -> None:
    result = _run(project)
    assert result["run"]["run_id"] == "20261101T100000Z-real"
    assert result["run"]["other_runs"] == ["20261031T100000Z-real"]
    assert [f["run_id"] for f in result["fake_runs"]] == ["20261101T090000Z-fake"]
    text = json.dumps(result["metrics"])
    assert "20261101T090000Z-fake" not in text, "fake runs never feed the metrics"


def test_missing_labels_make_label_metrics_unavailable(project) -> None:
    (project / "evaluation" / "labels" / "20261101T100000Z-real.jsonl").unlink()
    metrics = _by_id(_run(project))
    for metric_id in ("MC-008", "MC-009", "MC-012", "MC-013", "MC-014", "MC-016"):
        assert metrics[metric_id]["status"] == "unavailable"
        assert "evaluation/labels" in metrics[metric_id]["collection_plan"]
    assert metrics["MC-011"]["status"] == "measured (script)"
    assert metrics["MC-011"]["details"]["support"]["status"] == "unavailable"
    template = project / "evaluation" / "labels" / "20261101T100000Z-real.template.jsonl"
    assert [json.loads(line)["id"] for line in template.read_text().splitlines()] == ["f1", "f3"]


def test_missing_exports_make_langfuse_metrics_unavailable(project) -> None:
    shutil.rmtree(project / "reports" / "langfuse")
    result = _run(project)
    metrics = _by_id(result)
    for metric_id in ("MC-019", "MC-020", "MC-021"):
        assert metrics[metric_id]["status"] == "unavailable"
        assert "export_traces.py" in metrics[metric_id]["collection_plan"] or metric_id == "MC-019"
    assert metrics["MC-023"]["status"] == "measured (script)"
    assert metrics["MC-023"]["details"]["cost_total"] is None
    sc007 = next(c for c in result["success_criteria"] if c["id"] == "SC-007")
    assert sc007["verdict"] == "not measurable"


def test_no_real_run_makes_everything_unavailable(project) -> None:
    for path in (project / "evaluation" / "results").glob("*-real.jsonl"):
        path.unlink()
    result = _run(project)
    assert result["run"]["run_id"] is None
    real_metrics = [m for m in result["metrics"] if m["id"] not in ("MC-031", "MC-032")]
    assert all(m["status"] == "unavailable" for m in real_metrics)
    assert result["fake_runs"], "fake runs are still reported separately"


def test_small_samples_keep_numerator_and_denominator(project) -> None:
    for metric in _run(project)["metrics"]:
        if metric["status"].startswith("measured") and metric["numerator"] is not None:
            assert isinstance(metric["numerator"], int)
            assert isinstance(metric["denominator"], int)


def test_reference_catalogue_matches_script() -> None:
    reference = (SKILL_DIR / "references" / "metric-catalogue.md").read_text()
    rows = dict(re.findall(r"^\| (MC-\d{3}) \| [^|]+ \| ([^|]+?) \|", reference, re.MULTILINE))
    assert len(rows) == 32
    for metric_id, _family, name, *_ in compute_metrics.CATALOGUE:
        assert rows[metric_id] == name
