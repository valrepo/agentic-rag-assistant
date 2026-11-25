"""Knowledge base wrapper (T017): storage, metadata, duplicates, listing, clearing."""

from __future__ import annotations

import pytest

from app.config import Config
from app.ingestion import chunk_document, validate_and_parse
from app.knowledge_base import KnowledgeBase
from tests.conftest import TEST_DATA_DIR


@pytest.fixture
def kb(tmp_config: Config, fake_embeddings) -> KnowledgeBase:
    return KnowledgeBase(tmp_config, embedding_function=fake_embeddings)


def _doc(name: str, config: Config):
    parsed = validate_and_parse(name, (TEST_DATA_DIR / name).read_bytes(), config)
    return parsed, chunk_document(parsed, config)


def test_empty_at_start(kb: KnowledgeBase) -> None:
    assert kb.is_empty()
    assert kb.count() == 0
    assert kb.list_files() == []


def test_add_and_metadata_round_trip(kb: KnowledgeBase, tmp_config: Config) -> None:
    parsed, chunks = _doc("two_pages.pdf", tmp_config)
    assert kb.add(parsed, chunks) is False
    assert kb.count() == len(chunks)
    hits = kb.search("blue harbor lighthouse", k=2)
    top = hits[0]
    assert top.chunk_id == chunks[0].chunk_id
    assert top.source_file == "two_pages.pdf"
    assert top.page == 1
    assert top.index == 0
    assert "lighthouse" in top.text
    assert 0 <= top.distance <= 2


def test_duplicate_content_is_not_stored_twice(kb: KnowledgeBase, tmp_config: Config) -> None:
    parsed, chunks = _doc("long.md", tmp_config)
    kb.add(parsed, chunks)
    count = kb.count()
    assert kb.add(parsed, chunks) is True
    assert kb.count() == count


def test_list_files_and_clear(kb: KnowledgeBase, tmp_config: Config) -> None:
    for name in ("long.md", "two_pages.pdf"):
        kb.add(*_doc(name, tmp_config))
    files = {f.source_file: f.chunk_count for f in kb.list_files()}
    assert set(files) == {"long.md", "two_pages.pdf"}
    assert files["two_pages.pdf"] == 2
    kb.clear()
    assert kb.is_empty()
    assert kb.list_files() == []


def test_persistence_across_instances(tmp_config: Config, fake_embeddings) -> None:
    first = KnowledgeBase(tmp_config, embedding_function=fake_embeddings)
    first.add(*_doc("two_pages.pdf", tmp_config))
    second = KnowledgeBase(tmp_config, embedding_function=fake_embeddings)
    assert second.count() == 2


def test_no_network_connection_is_attempted(tmp_config: Config, fake_embeddings) -> None:
    # The autouse network block raises on any TCP/UDP connect; Chroma telemetry is off.
    kb = KnowledgeBase(tmp_config, embedding_function=fake_embeddings)
    kb.add(*_doc("long.md", tmp_config))
    assert kb.search("deployment checklist", k=3)
