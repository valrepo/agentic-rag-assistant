"""Deterministic hallucination guardrail (FR-018, FR-020, data-model.md).

Citations are checked against the chunks recorded by the retrieval tool, never against the
model's own text. Rules, in order:

1. No retrieved chunk above the minimum score, or the Answer/Verifier reports insufficient
   evidence: safe response, status abstained.
2. Remove citations whose chunk id was not retrieved; count them.
3. Move statements left without any valid citation to "Uncertain or missing".
4. No statement left: safe response, status abstained.
5. Otherwise answered; decision citations_removed if rule 2 or 3 changed anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.retrieval import RetrievedChunk

SAFE_RESPONSE = "I could not find this in the uploaded knowledge."


class DraftStatement(BaseModel):
    text: str = Field(description="One statement presented as fact, in your own words.")
    chunk_ids: list[str] = Field(
        default_factory=list, description="Ids of the retrieved chunks supporting the statement."
    )


class AnswerDraft(BaseModel):
    """Structured output of the Answer/Verifier task."""

    sufficient_evidence: bool = Field(
        description="True only if the retrieved chunks contain enough evidence to answer."
    )
    statements: list[DraftStatement] = Field(default_factory=list)
    uncertain: list[str] = Field(
        default_factory=list, description="What is uncertain or missing from the evidence."
    )


@dataclass(frozen=True)
class Statement:
    text: str
    citations: list[RetrievedChunk]


@dataclass
class Answer:
    status: str  # answered | abstained
    text: str
    guardrail_decision: str  # passed | citations_removed | safe_response
    statements: list[Statement] = field(default_factory=list)
    uncertain: list[str] = field(default_factory=list)
    related_passages: list[RetrievedChunk] = field(default_factory=list)
    draft_cited_chunk_ids: list[str] = field(default_factory=list)
    cited_chunk_ids: list[str] = field(default_factory=list)
    citations_removed: int = 0

    @property
    def safe_response_used(self) -> bool:
        return self.status == "abstained"


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _safe(
    retrieved: list[RetrievedChunk], draft_ids: list[str], removed: int, uncertain: list[str]
) -> Answer:
    return Answer(
        status="abstained",
        text=SAFE_RESPONSE,
        guardrail_decision="safe_response",
        uncertain=uncertain,
        related_passages=[c for c in retrieved if c.above_min_score],
        draft_cited_chunk_ids=draft_ids,
        citations_removed=removed,
    )


def render_text(statements: list[Statement], uncertain: list[str]) -> str:
    lines = [f"{s.text} {' '.join(c.reference() for c in s.citations)}" for s in statements]
    if uncertain:
        lines.append("")
        lines.append("Uncertain or missing:")
        lines.extend(f"- {item}" for item in uncertain)
    return "\n".join(lines)


def apply_guardrail(draft: AnswerDraft, retrieved: list[RetrievedChunk]) -> Answer:
    draft_ids = _unique([cid for s in draft.statements for cid in s.chunk_ids])
    uncertain = [u.strip() for u in draft.uncertain if u.strip()]

    # Rule 1
    if not any(c.above_min_score for c in retrieved) or not draft.sufficient_evidence:
        return _safe(retrieved, draft_ids, 0, uncertain)

    by_id = {c.chunk_id: c for c in retrieved}
    removed = 0
    kept: list[Statement] = []
    moved = False
    for statement in draft.statements:
        text = statement.text.strip()
        if not text:
            continue
        ids = _unique(statement.chunk_ids)
        valid = [by_id[cid] for cid in ids if cid in by_id]  # Rule 2
        removed += len(ids) - len(valid)
        if valid:
            kept.append(Statement(text=text, citations=valid))
        else:  # Rule 3
            uncertain.append(text)
            moved = True

    if not kept:  # Rule 4
        return _safe(retrieved, draft_ids, removed, uncertain)

    cited = _unique([c.chunk_id for s in kept for c in s.citations])
    return Answer(  # Rule 5
        status="answered",
        text=render_text(kept, uncertain),
        guardrail_decision="citations_removed" if removed or moved else "passed",
        statements=kept,
        uncertain=uncertain,
        draft_cited_chunk_ids=draft_ids,
        cited_chunk_ids=cited,
        citations_removed=removed,
    )
