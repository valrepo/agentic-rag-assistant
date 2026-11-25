"""Vector search returning ranked chunks with source metadata and scores (constitution III)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Config
from app.knowledge_base import KnowledgeBase


@dataclass(frozen=True)
class RetrievedChunk:
    rank: int
    chunk_id: str
    source_file: str
    index: int
    page: int | None
    score: float  # 1 - cosine distance
    above_min_score: bool
    text: str

    def reference(self) -> str:
        page = f", p. {self.page}" if self.page is not None else ""
        return f"[{self.source_file}, chunk {self.index}{page}]"

    def to_record(self) -> dict[str, Any]:
        """EV-003 `retrieved` entry (no chunk text)."""
        return {
            "rank": self.rank,
            "file": self.source_file,
            "chunk_id": self.chunk_id,
            "score": self.score,
            "above_min_score": self.above_min_score,
        }

    def to_trace(self) -> dict[str, Any]:
        """Retriever observation entry: metadata plus a short preview."""
        return {**self.to_record(), "page": self.page, "preview": self.text[:200]}


def retrieve(kb: KnowledgeBase, question: str, config: Config) -> list[RetrievedChunk]:
    """Top k chunks before the minimum-score filter, best first."""
    hits = kb.search(question, config.retrieval_k)
    chunks = []
    for rank, hit in enumerate(hits, start=1):
        score = round(1.0 - hit.distance, 4)
        chunks.append(
            RetrievedChunk(
                rank=rank,
                chunk_id=hit.chunk_id,
                source_file=hit.source_file,
                index=hit.index,
                page=hit.page,
                score=score,
                above_min_score=score >= config.min_relevance_score,
                text=hit.text,
            )
        )
    return chunks
