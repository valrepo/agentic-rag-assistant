"""File-name sanitization and storage paths (T016, FR-033)."""

from __future__ import annotations

import re

import pytest

from app.config import Config
from app.ingestion import sanitize_name, storage_path


@pytest.mark.parametrize(
    "name",
    [
        "../../etc/passwd.txt",
        "..\\..\\windows\\system.ini.txt",
        "/absolute/path/notes.md",
        "réunion été (final) v2!.pdf",
        "..",
        ".",
        "",
        "a" * 300 + ".txt",
        "name\x00with\nnull.txt",
    ],
)
def test_sanitized_names_are_safe(name: str) -> None:
    safe = sanitize_name(name)
    assert re.fullmatch(r"[A-Za-z0-9._-]+", safe)
    assert safe not in {".", ".."}
    assert "/" not in safe and "\\" not in safe
    assert len(safe) <= 120


def test_extension_is_kept_when_truncating() -> None:
    assert sanitize_name("b" * 300 + ".pdf").endswith(".pdf")


@pytest.mark.parametrize("name", ["../../escape.txt", "/tmp/evil.md", "ok.txt"])
def test_storage_path_stays_inside_data_dir(tmp_config: Config, name: str) -> None:
    path = storage_path(name, "0123456789abcdef", tmp_config)
    uploads = tmp_config.uploads_dir.resolve()
    assert path.resolve().is_relative_to(uploads)
    assert path.name.startswith("0123456789ab-")
