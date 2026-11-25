"""Streamlit UI with the deterministic doubles (contracts/ui.md), via streamlit.testing."""

from __future__ import annotations

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import app.service
from app.guardrail import SAFE_RESPONSE
from app.observability import NoOpTracer
from app.service import UploadedFile, build_services
from tests.conftest import REPO_ROOT, SAMPLE_DIR
from tests.fakes.fake_answerer import make_fake_llm

SAMPLES = ["model-monitoring-guide.md", "incident-runbook.txt", "data-retention-policy.pdf"]


@pytest.fixture
def ui(tmp_config, fake_embeddings, monkeypatch):
    services = build_services(
        tmp_config, llm=make_fake_llm(), embedding_function=fake_embeddings, tracer=NoOpTracer()
    )
    states: list[bool] = []
    rendered: dict[str, bool] = {}
    original_ask = services.answers.ask
    original_button = st.button

    def recording_button(label, *args, **kwargs):
        rendered[label] = bool(kwargs.get("disabled", False))
        return original_button(label, *args, **kwargs)

    def observed_ask(question: str):
        # Was the "Ask" button of this script run rendered disabled?
        states.append(rendered.get("Ask", False))
        return original_ask(question)

    monkeypatch.setattr(st, "button", recording_button)

    services.answers.ask = observed_ask
    monkeypatch.setattr(app.service, "build_services", lambda config: services)
    st.cache_resource.clear()
    app_test = AppTest.from_file(str(REPO_ROOT / "app" / "ui.py"), default_timeout=60)
    yield app_test, services, states
    st.cache_resource.clear()


def _ask(app_test: AppTest, question: str) -> AppTest:
    app_test.text_area(key="question").input(question).run()
    return app_test.button[-1].click().run()


def test_empty_knowledge_base_shows_message_and_no_button(ui) -> None:
    app_test, _, _ = ui
    app_test.run()
    assert not app_test.exception
    assert any("empty" in i.value for i in app_test.info)
    assert [b.label for b in app_test.button] == ["Index files"]


def test_ask_runs_with_disabled_widgets_then_enables_them(ui) -> None:
    app_test, services, states = ui
    services.knowledge.ingest([UploadedFile(n, (SAMPLE_DIR / n).read_bytes()) for n in SAMPLES])
    app_test.run()
    _ask(app_test, "How quickly must the on-call engineer acknowledge a SEV1 page?")
    assert not app_test.exception
    assert states == [True], "the crew ran while the Ask button was rendered disabled"
    ask_button = app_test.button[-1]
    assert ask_button.label == "Ask" and not ask_button.disabled
    assert not app_test.text_area(key="question").disabled
    assert any("[incident-runbook.txt, chunk" in m.value for m in app_test.markdown)
    assert any("Request id" in c.value for c in app_test.caption)


def test_unknown_question_shows_safe_response(ui) -> None:
    app_test, services, _ = ui
    services.knowledge.ingest([UploadedFile(n, (SAMPLE_DIR / n).read_bytes()) for n in SAMPLES])
    app_test.run()
    _ask(app_test, "What is the parental leave policy?")
    assert [w.value for w in app_test.warning] == [SAFE_RESPONSE]


def test_empty_question_shows_error(ui) -> None:
    app_test, services, _ = ui
    services.knowledge.ingest([UploadedFile(n, (SAMPLE_DIR / n).read_bytes()) for n in SAMPLES])
    app_test.run()
    _ask(app_test, "   ")
    assert [e.value for e in app_test.error] == ["The question is empty or too long."]
    assert not app_test.button[-1].disabled
