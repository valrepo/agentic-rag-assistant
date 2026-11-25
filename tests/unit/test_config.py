"""Configuration and domain errors (T011)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import errors
from app.config import Config, ConfigError


def test_defaults_match_contract() -> None:
    config = Config.from_env(env={})
    assert config.llm_model == "ollama/llama3.1:8b"
    assert config.llm_base_url == "http://localhost:11434"
    assert config.llm_temperature == 0.1
    assert config.llm_timeout_s == 120
    assert config.data_dir == Path("storage")
    assert (config.chunk_size, config.chunk_overlap) == (800, 120)
    assert config.retrieval_k == 5
    assert config.min_relevance_score == 0.35
    assert config.max_upload_mb == 10
    assert config.max_question_chars == 1000
    assert config.langfuse_enabled is True
    assert config.langfuse_base_url == "https://cloud.langfuse.com"


def test_env_overrides_are_parsed() -> None:
    config = Config.from_env(
        env={"RETRIEVAL_K": "3", "LANGFUSE_ENABLED": "false", "MIN_RELEVANCE_SCORE": "0.5"}
    )
    assert config.retrieval_k == 3
    assert config.langfuse_enabled is False
    assert config.min_relevance_score == 0.5


@pytest.mark.parametrize(
    "env",
    [
        {"RETRIEVAL_K": "zero"},
        {"RETRIEVAL_K": "0"},
        {"CHUNK_OVERLAP": "900"},
        {"MIN_RELEVANCE_SCORE": "1.5"},
        {"LANGFUSE_ENABLED": "maybe"},
    ],
)
def test_invalid_values_raise(env: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        Config.from_env(env=env)


def test_redacted_hides_credentials() -> None:
    config = Config.from_env(
        env={"LANGFUSE_PUBLIC_KEY": "pk-lf-test", "LANGFUSE_SECRET_KEY": "sk-lf-test"}
    )
    redacted = config.redacted()
    assert "pk-lf-test" not in str(redacted)
    assert "sk-lf-test" not in str(redacted)
    assert redacted["retrieval_k"] == 5


def test_explicit_mapping_never_reads_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("RETRIEVAL_K=9\nLANGFUSE_SECRET_KEY=sk-from-dotenv\n")
    monkeypatch.chdir(tmp_path)
    config = Config.from_env(env={})
    assert config.retrieval_k == 5
    assert config.langfuse_secret_key == ""


@pytest.mark.parametrize(
    "error",
    [
        errors.UnsupportedFileTypeError(),
        errors.EmptyFileError(),
        errors.FileTooLargeError(10),
        errors.UnreadableFileError(),
        errors.IndexingError(),
        errors.EmptyKnowledgeBaseError(),
        errors.InvalidQuestionError(),
        errors.RetrievalError(),
        errors.ProviderError(),
    ],
)
def test_error_messages_are_safe(error: errors.AppError) -> None:
    message = error.user_message
    assert message
    assert "/" not in message.replace(".txt, .pdf, .md", "")
    assert "Traceback" not in message
    assert "key" not in message.lower()


def test_distinct_messages() -> None:
    classes = [
        errors.UnsupportedFileTypeError,
        errors.EmptyFileError,
        errors.UnreadableFileError,
        errors.IndexingError,
        errors.EmptyKnowledgeBaseError,
        errors.InvalidQuestionError,
        errors.RetrievalError,
        errors.ProviderError,
    ]
    messages = {cls().user_message for cls in classes}
    assert len(messages) == len(classes)
    assert "10 MB" in errors.FileTooLargeError(10).user_message
    assert ".txt, .pdf, .md" in errors.UnsupportedFileTypeError().user_message
