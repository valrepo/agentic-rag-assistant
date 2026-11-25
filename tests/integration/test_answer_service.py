"""AnswerService.ask (T028): validation, empty knowledge base, failures, run metadata."""

from __future__ import annotations

import re

import pytest

from app.config import Config
from app.errors import EmptyKnowledgeBaseError, InvalidQuestionError, RetrievalError
from app.service import UploadedFile, build_services
from tests.conftest import SAMPLE_DIR
from tests.fakes.fake_answerer import make_fake_llm

SAMPLES = ["model-monitoring-guide.md", "incident-runbook.txt", "data-retention-policy.pdf"]


def _services(config: Config, embeddings, llm):
    services = build_services(config, llm=llm, embedding_function=embeddings)
    services.knowledge.ingest([UploadedFile(n, (SAMPLE_DIR / n).read_bytes()) for n in SAMPLES])
    return services


@pytest.mark.parametrize("question", ["", "   \n\t", "x" * 1001])
def test_invalid_question_is_rejected_before_any_run(
    tmp_config: Config, fake_embeddings, question: str
) -> None:
    llm = make_fake_llm()
    services = _services(tmp_config, fake_embeddings, llm)
    with pytest.raises(InvalidQuestionError):
        services.answers.ask(question)
    assert llm.calls == []


def test_empty_knowledge_base_is_rejected_before_any_run(tmp_config: Config, fake_embeddings):
    llm = make_fake_llm()
    services = build_services(tmp_config, llm=llm, embedding_function=fake_embeddings)
    with pytest.raises(EmptyKnowledgeBaseError):
        services.answers.ask("What is the drift threshold?")
    assert llm.calls == []


def test_answered_run_metadata(tmp_config: Config, fake_embeddings) -> None:
    services = _services(tmp_config, fake_embeddings, make_fake_llm())
    result = services.answers.ask("  Which PSI value fires a data drift alert?  ")
    assert result.status == "answered"
    assert re.fullmatch(r"[0-9a-f]{32}", result.request_id)
    assert result.latency_ms >= 0
    assert result.retrieved and result.retrieved[0].rank == 1
    assert result.answer is not None and result.answer.cited_chunk_ids
    assert result.prompt_tokens and result.completion_tokens
    assert result.error_stage is None and result.user_message is None
    assert result.trace_id is None, "tracing is disabled in tests"


def test_request_ids_are_unique(tmp_config: Config, fake_embeddings) -> None:
    services = _services(tmp_config, fake_embeddings, make_fake_llm())
    ids = {services.answers.ask("What is the drift alert threshold?").request_id for _ in range(3)}
    assert len(ids) == 3


def test_provider_failure_is_reported(tmp_config: Config, fake_embeddings) -> None:
    llm = make_fake_llm(fail_with=TimeoutError("connection to model timed out"))
    services = _services(tmp_config, fake_embeddings, llm)
    result = services.answers.ask("What is the drift alert threshold?")
    assert result.status == "failed"
    assert result.error_stage == "answer"
    assert result.error_type == "TimeoutError"
    assert result.answer is None
    assert "language model" in result.user_message
    assert "timed out" not in result.user_message.replace("or timed out", "")


def test_retrieval_failure_is_reported(
    tmp_config: Config, fake_embeddings, monkeypatch: pytest.MonkeyPatch
) -> None:
    services = _services(tmp_config, fake_embeddings, make_fake_llm())

    def broken_search(*args, **kwargs):
        raise RetrievalError()

    monkeypatch.setattr(services.knowledge_base, "search", broken_search)
    result = services.answers.ask("What is the drift alert threshold?")
    assert result.status == "failed"
    assert result.error_stage == "retrieval"
    assert result.retrieved == []
    assert result.user_message == RetrievalError().user_message
