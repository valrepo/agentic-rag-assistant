"""Evaluation dataset validation (T040, EV-002)."""

from __future__ import annotations

import json
from collections import Counter

from tests.conftest import REPO_ROOT, SAMPLE_DIR

EVAL = REPO_ROOT / "evaluation"


def _load(name: str) -> list[dict]:
    return [json.loads(line) for line in (EVAL / name).read_text().splitlines() if line.strip()]


def test_dataset_shape_and_joins() -> None:
    questions = _load("questions.jsonl")
    expected = {e["id"]: e for e in _load("expected_answers.jsonl")}
    ids = [q["id"] for q in questions]
    assert len(ids) == len(set(ids)) >= 5
    assert set(ids) == set(expected)
    categories = Counter(q["category"] for q in questions)
    assert categories["answerable"] >= 3
    assert categories["unanswerable"] >= 1
    assert categories["multi_source"] >= 1
    assert set(categories) <= {"answerable", "unanswerable", "multi_source"}
    for question in questions:
        assert question["question"].strip()


def test_expected_answers_follow_the_contract() -> None:
    questions = {q["id"]: q for q in _load("questions.jsonl")}
    sample_files = {p.name for p in SAMPLE_DIR.iterdir()} - {"README.md"}
    point_ids: set[str] = set()
    for item in _load("expected_answers.jsonl"):
        category = questions[item["id"]]["category"]
        if category == "unanswerable":
            assert item["expected_behavior"] == "abstain"
            assert item["answer_points"] == [] and item["expected_sources"] == []
            continue
        assert item["expected_behavior"] == "answer"
        assert 2 <= len(item["answer_points"]) <= 4
        for point in item["answer_points"]:
            assert point["text"].strip()
            assert point["point_id"].startswith(item["id"] + "-")
            assert point["point_id"] not in point_ids
            point_ids.add(point["point_id"])
        assert item["expected_sources"]
        assert set(item["expected_sources"]) <= sample_files
        if category == "multi_source":
            assert len(item["expected_sources"]) >= 2
