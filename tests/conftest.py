"""Shared test setup: offline, deterministic, never reads the developer's `.env`.

- CrewAI telemetry and tracing are disabled before crewai is imported.
- Langfuse is disabled unless a test injects the in-memory tracer.
- Any TCP or UDP connection fails the test (Unix-domain sockets stay allowed).
"""

from __future__ import annotations

import os

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["CREWAI_TRACING_ENABLED"] = "false"
os.environ["LANGFUSE_ENABLED"] = "false"
os.environ["ANONYMIZED_TELEMETRY"] = "false"

import socket  # noqa: E402
from collections.abc import Callable  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from app.config import Config  # noqa: E402
from tests.fakes.fake_embeddings import LexicalFakeEmbeddingFunction  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = REPO_ROOT / "data" / "sample-knowledge"
TEST_DATA_DIR = Path(__file__).resolve().parent / "data"

# Threshold suited to the lexical fake embeddings (plan decision 6).
FAKE_MIN_RELEVANCE_SCORE = 0.05


class NetworkBlockedError(RuntimeError):
    pass


_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


def _guard(sock: socket.socket) -> None:
    if sock.family in (socket.AF_INET, socket.AF_INET6):
        raise NetworkBlockedError("network access is blocked in tests")


def _blocked_connect(self: socket.socket, address: object) -> None:
    _guard(self)
    return _real_connect(self, address)


def _blocked_connect_ex(self: socket.socket, address: object) -> int:
    _guard(self)
    return _real_connect_ex(self, address)


def _blocked_create_connection(*args: object, **kwargs: object) -> socket.socket:
    raise NetworkBlockedError("network access is blocked in tests")


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked_connect_ex)
    monkeypatch.setattr(socket, "create_connection", _blocked_create_connection)


def make_config(data_dir: Path, **overrides: str) -> Config:
    env = {
        "DATA_DIR": str(data_dir),
        "MIN_RELEVANCE_SCORE": str(FAKE_MIN_RELEVANCE_SCORE),
        "LANGFUSE_ENABLED": "false",
        "LLM_MODEL": "stub/deterministic",
    }
    env.update(overrides)
    return Config.from_env(env=env)


@pytest.fixture
def tmp_config(tmp_path: Path) -> Config:
    return make_config(tmp_path / "storage")


@pytest.fixture
def fake_embeddings() -> LexicalFakeEmbeddingFunction:
    return LexicalFakeEmbeddingFunction()


@pytest.fixture
def stub_llm_factory() -> Callable[..., object]:
    from tests.fakes.stub_llm import StubLLM

    def factory(**kwargs: object) -> StubLLM:
        return StubLLM(**kwargs)

    return factory
