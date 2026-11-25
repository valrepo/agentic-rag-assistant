"""FR-035 test 3: retrieval of relevant evidence for a known question (T025)."""

from __future__ import annotations

import pytest

from app.config import Config
from app.knowledge_base import KnowledgeBase
from app.retrieval import retrieve
from app.service import KnowledgeService, UploadedFile
from tests.conftest import SAMPLE_DIR

SAMPLES = ["model-monitoring-guide.md", "incident-runbook.txt", "data-retention-policy.pdf"]


@pytest.fixture
def kb(tmp_config: Config, fake_embeddings) -> KnowledgeBase:
    knowledge_base = KnowledgeBase(tmp_config, embedding_function=fake_embeddings)
    service = KnowledgeService(tmp_config, knowledge_base)
    service.ingest([UploadedFile(n, (SAMPLE_DIR / n).read_bytes()) for n in SAMPLES])
    return knowledge_base


def test_known_question_retrieves_expected_source(kb: KnowledgeBase, tmp_config: Config) -> None:
    chunks = retrieve(kb, "Which PSI value fires a data drift alert?", tmp_config)
    assert chunks[0].source_file == "model-monitoring-guide.md"
    assert chunks[0].above_min_score is True
    assert chunks[0].rank == 1


def test_pdf_question_retrieves_pdf_with_page(kb: KnowledgeBase, tmp_config: Config) -> None:
    chunks = retrieve(kb, "How long are inference logs retained?", tmp_config)
    assert chunks[0].source_file == "data-retention-policy.pdf"
    assert chunks[0].page == 2


def test_unrelated_question_scores_below_threshold(kb: KnowledgeBase, tmp_config: Config) -> None:
    chunks = retrieve(kb, "Recipe for chocolate banana bread?", tmp_config)
    assert chunks, "the retriever still returns the top k before the minimum-score filter"
    assert not any(c.above_min_score for c in chunks)


def test_scores_ranks_and_k(kb: KnowledgeBase, tmp_config: Config) -> None:
    chunks = retrieve(kb, "rollback to the previous model version", tmp_config)
    assert len(chunks) == min(tmp_config.retrieval_k, kb.count())
    assert [c.rank for c in chunks] == list(range(1, len(chunks) + 1))
    scores = [c.score for c in chunks]
    assert scores == sorted(scores, reverse=True)
    for chunk in chunks:
        assert chunk.above_min_score == (chunk.score >= tmp_config.min_relevance_score)
        assert -1.0 <= chunk.score <= 1.0
    record = chunks[0].to_record()
    assert set(record) == {"rank", "file", "chunk_id", "score", "above_min_score"}


def test_empty_knowledge_base_returns_nothing(tmp_config: Config, fake_embeddings) -> None:
    kb = KnowledgeBase(tmp_config, embedding_function=fake_embeddings)
    assert retrieve(kb, "anything", tmp_config) == []
