"""Application configuration read from environment variables (contracts/configuration.md).

`Config.from_env()` reads `os.environ`, after loading an optional local `.env` file that never
overrides variables already set. `Config.from_env(env=mapping)` reads only the given mapping
and never opens `.env`; tests always use this form.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from dotenv import load_dotenv

_SECRET_FIELDS = {"langfuse_public_key", "langfuse_secret_key"}


class ConfigError(ValueError):
    """Raised when an environment variable has an invalid value."""


def _bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"not a boolean: {value!r}")


@dataclass(frozen=True)
class Config:
    llm_model: str = "ollama/llama3.1:8b"
    llm_base_url: str = "http://localhost:11434"
    llm_temperature: float = 0.1
    llm_timeout_s: float = 120.0
    data_dir: Path = Path("storage")
    chunk_size: int = 800
    chunk_overlap: int = 120
    retrieval_k: int = 5
    min_relevance_score: float = 0.35
    max_upload_mb: float = 10.0
    max_question_chars: int = 1000
    langfuse_enabled: bool = True
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            raise ConfigError("CHUNK_SIZE must be positive")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ConfigError("CHUNK_OVERLAP must be >= 0 and smaller than CHUNK_SIZE")
        if self.retrieval_k < 1:
            raise ConfigError("RETRIEVAL_K must be at least 1")
        if not 0 <= self.min_relevance_score <= 1:
            raise ConfigError("MIN_RELEVANCE_SCORE must be between 0 and 1")
        if self.max_upload_mb <= 0:
            raise ConfigError("MAX_UPLOAD_MB must be positive")
        if self.max_question_chars < 1:
            raise ConfigError("MAX_QUESTION_CHARS must be at least 1")
        if self.llm_timeout_s <= 0:
            raise ConfigError("LLM_TIMEOUT_S must be positive")

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        if env is None:
            load_dotenv(override=False)
            env = os.environ
        kwargs: dict[str, object] = {}
        for field in fields(cls):
            raw = env.get(field.name.upper())
            if raw is None or raw.strip() == "":
                continue
            default = getattr(cls, field.name)
            try:
                if isinstance(default, bool):
                    kwargs[field.name] = _bool(raw)
                elif isinstance(default, int):
                    kwargs[field.name] = int(raw)
                elif isinstance(default, float):
                    kwargs[field.name] = float(raw)
                elif isinstance(default, Path):
                    kwargs[field.name] = Path(raw)
                else:
                    kwargs[field.name] = raw.strip()
            except ValueError as exc:
                raise ConfigError(f"invalid value for {field.name.upper()}") from exc
        return cls(**kwargs)

    def redacted(self) -> dict[str, object]:
        """Configuration as a dict without credentials, safe for logs and run headers."""
        values = asdict(self)
        for name in _SECRET_FIELDS:
            values.pop(name, None)
        values["data_dir"] = str(self.data_dir)
        return values
