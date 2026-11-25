"""FR-035 test 7: smoke test of the main path with the deterministic fake model (T034).

Upload -> index -> ask -> cited answer, through the same services the UI uses
(constitution Quality Gate 3).
"""

from __future__ import annotations

from app.config import Config
from app.observability import NoOpTracer
from app.service import UploadedFile, build_services
from tests.conftest import SAMPLE_DIR
from tests.fakes.fake_answerer import make_fake_llm

SAMPLES = ["model-monitoring-guide.md", "incident-runbook.txt", "data-retention-policy.pdf"]


def test_upload_index_ask_cited_answer(tmp_config: Config, fake_embeddings) -> None:
    services = build_services(
        tmp_config, llm=make_fake_llm(), embedding_function=fake_embeddings, tracer=NoOpTracer()
    )
    assert services.knowledge.is_empty()

    results = services.knowledge.ingest(
        [UploadedFile(n, (SAMPLE_DIR / n).read_bytes()) for n in SAMPLES]
    )
    assert [r.status for r in results] == ["indexed"] * 3

    run = services.answers.ask("How quickly must the on-call engineer acknowledge a SEV1 page?")
    assert run.status == "answered"
    assert run.answer is not None
    cited_files = {c.source_file for s in run.answer.statements for c in s.citations}
    assert "incident-runbook.txt" in cited_files
    retrieved_ids = {c.chunk_id for c in run.retrieved}
    assert set(run.answer.cited_chunk_ids) <= retrieved_ids
    assert "[incident-runbook.txt, chunk" in run.answer.text
