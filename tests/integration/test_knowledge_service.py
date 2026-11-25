"""KnowledgeService.ingest end to end (T018, US1 scenarios 1 to 4)."""

from __future__ import annotations

import pytest

from app.config import Config
from app.service import UploadedFile, build_services
from tests.conftest import SAMPLE_DIR, TEST_DATA_DIR

SAMPLES = ["model-monitoring-guide.md", "incident-runbook.txt", "data-retention-policy.pdf"]


@pytest.fixture
def services(tmp_config: Config, fake_embeddings, stub_llm_factory):
    return build_services(tmp_config, llm=stub_llm_factory(), embedding_function=fake_embeddings)


def _upload(directory, name: str, as_name: str | None = None) -> UploadedFile:
    return UploadedFile(name=as_name or name, data=(directory / name).read_bytes())


def test_mixed_batch_is_processed_file_by_file(services) -> None:
    files = [_upload(SAMPLE_DIR, n) for n in SAMPLES] + [
        _upload(TEST_DATA_DIR, "empty.txt"),
        _upload(TEST_DATA_DIR, "image.png"),
        _upload(TEST_DATA_DIR, "invalid.pdf"),
    ]
    results = {r.original_name: r for r in services.knowledge.ingest(files)}
    assert len(results) == 6
    for name in SAMPLES:
        assert results[name].status == "indexed"
        assert results[name].chunk_count and results[name].chunk_count > 0
        assert results[name].already_present is False
        assert results[name].duration_ms >= 0
    assert (results["empty.txt"].status, results["empty.txt"].reason) == ("rejected", "empty file")
    assert results["image.png"].reason == "unsupported file type"
    assert results["invalid.pdf"].reason == "unreadable"
    assert results["image.png"].chunk_count is None
    assert results["image.png"].user_message and ".pdf" in results["image.png"].user_message
    listed = {f.source_file for f in services.knowledge.list_files()}
    assert listed == set(SAMPLES)


def test_reupload_reports_already_present(services) -> None:
    first = services.knowledge.ingest([_upload(SAMPLE_DIR, SAMPLES[1])])[0]
    second = services.knowledge.ingest([_upload(SAMPLE_DIR, SAMPLES[1])])[0]
    assert second.status == "indexed"
    assert second.already_present is True
    assert second.chunk_count == first.chunk_count
    assert sum(f.chunk_count for f in services.knowledge.list_files()) == first.chunk_count


def test_uploaded_file_is_stored_inside_data_dir(services, tmp_config: Config) -> None:
    services.knowledge.ingest([_upload(SAMPLE_DIR, SAMPLES[1], as_name="../../evil.txt")])
    stored = list(tmp_config.uploads_dir.iterdir())
    assert len(stored) == 1
    assert stored[0].resolve().is_relative_to(tmp_config.uploads_dir.resolve())


def test_embedding_failure_is_reported_as_failed(tmp_config: Config, stub_llm_factory) -> None:
    class BrokenEmbeddings:
        def __call__(self, input):  # noqa: A002
            raise RuntimeError("embedding backend down")

        @staticmethod
        def name() -> str:
            return "broken"

        def get_config(self):
            return {}

        def is_legacy(self) -> bool:
            return False

        def default_space(self) -> str:
            return "cosine"

        def supported_spaces(self):
            return ["cosine"]

        def embed_query(self, input):  # noqa: A002
            return self(input)

    services = build_services(
        tmp_config, llm=stub_llm_factory(), embedding_function=BrokenEmbeddings()
    )
    result = services.knowledge.ingest([_upload(SAMPLE_DIR, SAMPLES[1])])[0]
    assert (result.status, result.reason) == ("failed", "indexing error")
    assert "embedding backend down" not in (result.user_message or "")


def test_clear_empties_knowledge_and_uploads(services, tmp_config: Config) -> None:
    services.knowledge.ingest([_upload(SAMPLE_DIR, SAMPLES[0])])
    assert not services.knowledge.is_empty()
    services.knowledge.clear()
    assert services.knowledge.is_empty()
    assert not any(tmp_config.uploads_dir.iterdir())
