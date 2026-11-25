"""Hallucination guardrail rules (T026, data-model.md rules 1 to 5, FR-018, FR-020)."""

from __future__ import annotations

from app.guardrail import SAFE_RESPONSE, AnswerDraft, DraftStatement, apply_guardrail
from app.retrieval import RetrievedChunk


def _chunk(rank: int, chunk_id: str, score: float, threshold: float = 0.3) -> RetrievedChunk:
    return RetrievedChunk(
        rank=rank,
        chunk_id=chunk_id,
        source_file="guide.md",
        index=int(chunk_id.split("-")[1]),
        page=None,
        score=score,
        above_min_score=score >= threshold,
        text="evidence text",
    )


RETRIEVED = [_chunk(1, "aaaaaaaaaaaa-0", 0.8), _chunk(2, "aaaaaaaaaaaa-1", 0.5)]


def _draft(*statements: tuple[str, list[str]], sufficient: bool = True, uncertain=None):
    return AnswerDraft(
        sufficient_evidence=sufficient,
        statements=[DraftStatement(text=t, chunk_ids=ids) for t, ids in statements],
        uncertain=uncertain or [],
    )


def test_rule1_no_chunk_above_threshold_gives_safe_response() -> None:
    low = [_chunk(1, "aaaaaaaaaaaa-0", 0.1)]
    answer = apply_guardrail(_draft(("A fact.", ["aaaaaaaaaaaa-0"])), low)
    assert answer.text == SAFE_RESPONSE
    assert answer.status == "abstained"
    assert answer.guardrail_decision == "safe_response"
    assert answer.statements == []
    assert answer.cited_chunk_ids == []


def test_rule1_no_retrieved_chunk_at_all() -> None:
    answer = apply_guardrail(_draft(("A fact.", ["x-0"])), [])
    assert (answer.text, answer.status) == (SAFE_RESPONSE, "abstained")


def test_rule1_insufficient_evidence_gives_safe_response_with_related_passages() -> None:
    answer = apply_guardrail(_draft(sufficient=False), RETRIEVED)
    assert answer.text == SAFE_RESPONSE
    assert answer.status == "abstained"
    assert [c.chunk_id for c in answer.related_passages] == ["aaaaaaaaaaaa-0", "aaaaaaaaaaaa-1"]


def test_rule2_invalid_citations_are_removed_and_counted() -> None:
    draft = _draft(("Fact one.", ["aaaaaaaaaaaa-0", "ffffffffffff-9"]))
    answer = apply_guardrail(draft, RETRIEVED)
    assert answer.status == "answered"
    assert answer.citations_removed == 1
    assert answer.draft_cited_chunk_ids == ["aaaaaaaaaaaa-0", "ffffffffffff-9"]
    assert answer.cited_chunk_ids == ["aaaaaaaaaaaa-0"]
    assert answer.guardrail_decision == "citations_removed"


def test_rule3_statement_without_valid_citation_moves_to_uncertain() -> None:
    draft = _draft(
        ("Supported.", ["aaaaaaaaaaaa-1"]), ("Invented.", ["ffffffffffff-1"]), ("Bare.", [])
    )
    answer = apply_guardrail(draft, RETRIEVED)
    assert [s.text for s in answer.statements] == ["Supported."]
    assert "Invented." in answer.uncertain and "Bare." in answer.uncertain
    assert answer.guardrail_decision == "citations_removed"
    assert "Uncertain or missing" in answer.text


def test_rule4_nothing_left_gives_safe_response() -> None:
    answer = apply_guardrail(_draft(("Invented.", ["ffffffffffff-1"])), RETRIEVED)
    assert answer.text == SAFE_RESPONSE
    assert answer.status == "abstained"
    assert answer.guardrail_decision == "safe_response"
    assert answer.citations_removed == 1


def test_rule5_clean_answer_passes() -> None:
    draft = _draft(
        ("Fact one.", ["aaaaaaaaaaaa-0"]),
        ("Fact two.", ["aaaaaaaaaaaa-1", "aaaaaaaaaaaa-0"]),
        uncertain=["The exact date is not stated."],
    )
    answer = apply_guardrail(draft, RETRIEVED)
    assert answer.status == "answered"
    assert answer.guardrail_decision == "passed"
    assert answer.citations_removed == 0
    assert answer.cited_chunk_ids == ["aaaaaaaaaaaa-0", "aaaaaaaaaaaa-1"]
    assert answer.uncertain == ["The exact date is not stated."]
    assert "[guide.md, chunk 0]" in answer.text


def test_displayed_citations_are_always_retrieved() -> None:
    draft = _draft(("A.", ["aaaaaaaaaaaa-0", "zzz"]), ("B.", ["bbbbbbbbbbbb-3", "aaaaaaaaaaaa-1"]))
    answer = apply_guardrail(draft, RETRIEVED)
    retrieved_ids = {c.chunk_id for c in RETRIEVED}
    assert set(answer.cited_chunk_ids) <= retrieved_ids
    for statement in answer.statements:
        assert {c.chunk_id for c in statement.citations} <= retrieved_ids
