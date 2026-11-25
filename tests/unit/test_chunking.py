"""FR-035 test 2: chunking and metadata preservation (T015)."""

from __future__ import annotations

import re

from app.config import Config
from app.ingestion import chunk_document, validate_and_parse
from tests.conftest import TEST_DATA_DIR, make_config


def _parse(name: str, config: Config):
    return validate_and_parse(name, (TEST_DATA_DIR / name).read_bytes(), config)


def test_chunks_respect_size_and_overlap(tmp_path) -> None:
    config = make_config(tmp_path, CHUNK_SIZE="400", CHUNK_OVERLAP="80")
    chunks = chunk_document(_parse("long.md", config), config)
    assert len(chunks) >= 7
    assert all(0 < len(c.text) <= 400 for c in chunks)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        tail = previous.text[-40:]
        assert tail.split()[-1] in current.text[:120], "consecutive chunks must overlap"


def test_chunk_metadata(tmp_config: Config) -> None:
    parsed = _parse("long.md", tmp_config)
    chunks = chunk_document(parsed, tmp_config)
    for index, chunk in enumerate(chunks):
        assert chunk.chunk_id == f"{parsed.sha256[:12]}-{index}"
        assert re.fullmatch(r"[0-9a-f]{12}-\d+", chunk.chunk_id)
        assert chunk.source_file == "long.md"
        assert chunk.file_sha256 == parsed.sha256
        assert chunk.index == index
        assert chunk.page is None
        assert chunk.text.strip()


def test_pdf_chunks_keep_pages_and_never_cross_them(tmp_config: Config) -> None:
    chunks = chunk_document(_parse("two_pages.pdf", tmp_config), tmp_config)
    assert [c.page for c in chunks] == [1, 2]
    assert "lighthouse" in chunks[0].text and "observatory" not in chunks[0].text
    assert "observatory" in chunks[1].text


def test_chunk_ids_are_stable(tmp_config: Config) -> None:
    first = chunk_document(_parse("long.md", tmp_config), tmp_config)
    second = chunk_document(_parse("long.md", tmp_config), tmp_config)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert [c.text for c in first] == [c.text for c in second]
