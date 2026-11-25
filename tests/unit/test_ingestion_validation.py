"""FR-035 test 1: file type and empty-file validation (T014)."""

from __future__ import annotations

import pytest

from app import errors
from app.config import Config
from app.ingestion import validate_and_parse
from tests.conftest import TEST_DATA_DIR, make_config


def _read(name: str) -> bytes:
    return (TEST_DATA_DIR / name).read_bytes()


@pytest.mark.parametrize("name", ["image.png", "report.docx"])
def test_unsupported_type_is_rejected(tmp_config: Config, name: str) -> None:
    with pytest.raises(errors.UnsupportedFileTypeError) as excinfo:
        validate_and_parse(name, _read(name), tmp_config)
    assert ".txt, .pdf, .md" in excinfo.value.user_message


@pytest.mark.parametrize("name", ["empty.txt", "blank.md", "no_text.pdf"])
def test_empty_files_are_rejected(tmp_config: Config, name: str) -> None:
    with pytest.raises(errors.EmptyFileError):
        validate_and_parse(name, _read(name), tmp_config)


def test_zero_byte_pdf_is_empty_not_unreadable(tmp_config: Config) -> None:
    with pytest.raises(errors.EmptyFileError):
        validate_and_parse("nothing.pdf", b"", tmp_config)


def test_too_large_file_is_rejected(tmp_path) -> None:
    config = make_config(tmp_path, MAX_UPLOAD_MB="0.001")
    with pytest.raises(errors.FileTooLargeError) as excinfo:
        validate_and_parse("big.txt", b"x" * 2000, config)
    assert "0.001 MB" in excinfo.value.user_message


@pytest.mark.parametrize("name", ["invalid.pdf", "latin1.txt"])
def test_unreadable_files_are_rejected(tmp_config: Config, name: str) -> None:
    with pytest.raises(errors.UnreadableFileError):
        validate_and_parse(name, _read(name), tmp_config)


def test_validation_order_type_before_size(tmp_path) -> None:
    config = make_config(tmp_path, MAX_UPLOAD_MB="0.001")
    with pytest.raises(errors.UnsupportedFileTypeError):
        validate_and_parse("big.png", b"x" * 2000, config)


def test_validation_order_size_before_readability(tmp_path) -> None:
    config = make_config(tmp_path, MAX_UPLOAD_MB="0.001")
    with pytest.raises(errors.FileTooLargeError):
        validate_and_parse("big.pdf", b"garbage" * 500, config)


@pytest.mark.parametrize(
    ("name", "file_type"),
    [("incident-runbook.txt", "txt"), ("NOTES.MD", "md"), ("two_pages.pdf", "pdf")],
)
def test_supported_types_are_parsed(tmp_config: Config, name: str, file_type: str) -> None:
    data = _read("two_pages.pdf") if file_type == "pdf" else b"Some useful knowledge.\n\nMore text."
    parsed = validate_and_parse(name, data, tmp_config)
    assert parsed.file_type == file_type
    assert parsed.original_name == name
    assert parsed.size_bytes == len(data)
    assert len(parsed.sha256) == 64
    assert any(text.strip() for _, text in parsed.pages)
