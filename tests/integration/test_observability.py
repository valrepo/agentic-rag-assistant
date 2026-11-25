"""FR-035 test 6 and SC-007: observability disabled or mocked (T036)."""

from __future__ import annotations

import json
import logging

import pytest

from app.config import Config
from app.observability import NoOpTracer, init_observability
from app.service import UploadedFile, build_services
from tests.conftest import SAMPLE_DIR, make_config
from tests.fakes.fake_answerer import make_fake_llm
from tests.fakes.memory_tracer import DUMMY_SECRET_KEY, MemoryLangfuse

SAMPLES = ["model-monitoring-guide.md", "incident-runbook.txt", "data-retention-policy.pdf"]
QUESTION = "How quickly must the on-call engineer acknowledge a SEV1 page?"


@pytest.fixture(scope="session")
def memory_langfuse() -> MemoryLangfuse:
    return MemoryLangfuse()


@pytest.fixture
def langfuse(memory_langfuse: MemoryLangfuse) -> MemoryLangfuse:
    memory_langfuse.reset()
    return memory_langfuse


def _services(config: Config, embeddings, tracer, **llm_kwargs):
    services = build_services(
        config, llm=make_fake_llm(**llm_kwargs), embedding_function=embeddings, tracer=tracer
    )
    services.knowledge.ingest([UploadedFile(n, (SAMPLE_DIR / n).read_bytes()) for n in SAMPLES])
    return services


def _attr(span, key: str):
    return (span.attributes or {}).get(key)


def _types(spans) -> list[str]:
    return [_attr(s, "langfuse.observation.type") for s in spans]


def test_disabled_and_mocked_give_same_answers(tmp_path, fake_embeddings, langfuse) -> None:
    plain = _services(make_config(tmp_path / "a"), fake_embeddings, NoOpTracer())
    traced = _services(make_config(tmp_path / "b"), fake_embeddings, langfuse.tracer)
    for question in (QUESTION, "What is the parental leave policy?"):
        first, second = plain.answers.ask(question), traced.answers.ask(question)
        assert (first.status, first.answer.text) == (second.status, second.answer.text)
        assert first.answer.guardrail_decision == second.answer.guardrail_decision
        assert first.trace_id is None
        assert second.trace_id is not None


def test_disabled_tracer_by_configuration(tmp_path) -> None:
    assert isinstance(init_observability(make_config(tmp_path)), NoOpTracer)


def test_missing_keys_disable_tracing_with_warning(tmp_path, caplog) -> None:
    config = make_config(tmp_path, LANGFUSE_ENABLED="true")
    with caplog.at_level(logging.WARNING):
        assert isinstance(init_observability(config), NoOpTracer)
    assert "keys are missing" in caplog.text


def test_one_trace_per_question_with_every_element(tmp_config, fake_embeddings, langfuse) -> None:
    services = _services(tmp_config, fake_embeddings, langfuse.tracer)
    run = services.answers.ask(QUESTION)
    traces = langfuse.spans_by_trace()
    assert list(traces) == [run.trace_id], "exactly one trace for one question"
    spans = traces[run.trace_id]

    root = [s for s in spans if s.name == "rag-question"]
    assert len(root) == 1 and root[0].parent is None
    root_input = _attr(root[0], "langfuse.observation.input")
    assert QUESTION in root_input and run.request_id in root_input
    assert all(_attr(s, "session.id") == run.request_id for s in spans)
    root_meta = json.loads(_attr(root[0], "langfuse.observation.metadata.guardrail_decision"))
    assert root_meta == "passed"

    names = [s.name for s in spans]
    assert any("Retriever/Researcher" in n for n in names), "agent/task span"
    assert any("Answer/Verifier" in n for n in names), "agent/task span"

    retriever = [s for s in spans if _attr(s, "langfuse.observation.type") == "retriever"]
    assert len(retriever) == 1
    output = _attr(retriever[0], "langfuse.observation.output")
    for chunk in run.retrieved:
        assert chunk.chunk_id in output and chunk.source_file in output
    assert '"score"' in output

    generations = [s for s in spans if _attr(s, "langfuse.observation.type") == "generation"]
    assert len(generations) == 2, "one generation per LLM call"
    root_end = root[0].end_time
    for generation in generations:
        assert _attr(generation, "langfuse.observation.model.name") == "stub/deterministic"
        assert _attr(generation, "langfuse.observation.input")
        assert _attr(generation, "langfuse.observation.output")
        usage = json.loads(_attr(generation, "langfuse.observation.usage_details"))
        assert usage == {"input": 10, "output": 5}
        assert generation.end_time <= root_end
    for span in spans:
        assert span.end_time >= span.start_time


def test_generations_never_leak_across_traces(tmp_config, fake_embeddings, langfuse) -> None:
    services = _services(tmp_config, fake_embeddings, langfuse.tracer)
    runs = [services.answers.ask(QUESTION) for _ in range(20)]
    traces = langfuse.spans_by_trace()
    assert set(traces) == {r.trace_id for r in runs}
    for spans in traces.values():
        generations = [s for s in spans if _attr(s, "langfuse.observation.type") == "generation"]
        assert len(generations) == 2
        root = next(s for s in spans if s.name == "rag-question")
        assert all(g.end_time <= root.end_time for g in generations)


def test_failed_run_is_marked_as_error(tmp_config, fake_embeddings, langfuse) -> None:
    services = _services(
        tmp_config, fake_embeddings, langfuse.tracer, fail_with=ConnectionError("model down")
    )
    run = services.answers.ask(QUESTION)
    assert run.status == "failed"
    spans = langfuse.spans_by_trace()[run.trace_id]
    root = next(s for s in spans if s.name == "rag-question")
    assert _attr(root, "langfuse.observation.level") == "ERROR"
    assert "failed at answer" in _attr(root, "langfuse.observation.status_message")


def test_langfuse_failure_does_not_block_answer(
    tmp_config, fake_embeddings, langfuse, monkeypatch, caplog
) -> None:
    def broken(*args, **kwargs):
        raise RuntimeError("langfuse unreachable")

    monkeypatch.setattr(langfuse.client, "start_as_current_observation", broken)
    monkeypatch.setattr(langfuse.client, "flush", broken)
    services = _services(tmp_config, fake_embeddings, langfuse.tracer)
    with caplog.at_level(logging.WARNING):
        run = services.answers.ask(QUESTION)
    assert run.status == "answered"
    assert run.trace_id is None
    assert "langfuse" in caplog.text


def test_no_secret_in_any_span(tmp_config, fake_embeddings, langfuse) -> None:
    services = _services(tmp_config, fake_embeddings, langfuse.tracer)
    services.answers.ask(QUESTION)
    for span in langfuse.spans():
        assert DUMMY_SECRET_KEY not in json.dumps(dict(span.attributes or {}), default=str)
