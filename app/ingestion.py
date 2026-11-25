"""Validation, parsing, and chunking of uploaded knowledge files (data-model.md).

Validation order: type, emptiness of the raw bytes, size, readability (parse), emptiness of
the extracted text. Chunking is paragraph-aware, by characters, and never crosses PDF pages.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path, PurePath

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import Config
from app.errors import (
    SUPPORTED_EXTENSIONS,
    EmptyFileError,
    FileTooLargeError,
    UnreadableFileError,
    UnsupportedFileTypeError,
)

logger = logging.getLogger(__name__)

MAX_STORED_NAME = 120
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")
_BLANK_LINES = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class ParsedDocument:
    original_name: str
    file_type: str
    size_bytes: int
    sha256: str
    pages: list[tuple[int | None, str]]  # (1-based page or None, text)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_file: str
    file_sha256: str
    index: int
    page: int | None
    text: str


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_type_of(name: str) -> str | None:
    suffix = PurePath(name.replace("\\", "/")).suffix.lower()
    return suffix[1:] if suffix in SUPPORTED_EXTENSIONS else None


def sanitize_name(name: str) -> str:
    """Base name only, characters outside [A-Za-z0-9._-] replaced, at most 120 characters."""
    base = name.replace("\\", "/").split("/")[-1]
    safe = _UNSAFE.sub("_", base).strip(".")
    if not safe:
        safe = "file"
    if len(safe) > MAX_STORED_NAME:
        stem, dot, ext = safe.rpartition(".")
        if dot and 0 < len(ext) <= 10:
            safe = stem[: MAX_STORED_NAME - len(ext) - 1] + "." + ext
        else:
            safe = safe[:MAX_STORED_NAME]
    return safe


def storage_path(original_name: str, sha256: str, config: Config) -> Path:
    """Path of the stored upload, always inside the uploads directory (FR-033)."""
    uploads = config.uploads_dir.resolve()
    stored = f"{sha256[:12]}-{sanitize_name(original_name)}"[:MAX_STORED_NAME]
    path = (uploads / stored).resolve()
    if not path.is_relative_to(uploads):
        raise ValueError("resolved upload path escapes the data directory")
    return path


def _decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UnreadableFileError() from exc


def _parse_pdf(data: bytes) -> list[tuple[int | None, str]]:
    try:
        reader = PdfReader(io.BytesIO(data))
        return [(number, page.extract_text() or "") for number, page in enumerate(reader.pages, 1)]
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise UnreadableFileError() from exc
    except Exception as exc:  # pypdf raises many internal types on corrupted input
        logger.warning("pdf parsing failed", extra={"error_type": type(exc).__name__})
        raise UnreadableFileError() from exc


def validate_and_parse(name: str, data: bytes, config: Config) -> ParsedDocument:
    file_type = file_type_of(name)
    if file_type is None:
        raise UnsupportedFileTypeError()
    if len(data) == 0:
        raise EmptyFileError()
    if len(data) > config.max_upload_bytes:
        raise FileTooLargeError(config.max_upload_mb)
    pages = _parse_pdf(data) if file_type == "pdf" else [(None, _decode_text(data))]
    if not any(text.strip() for _, text in pages):
        raise EmptyFileError()
    return ParsedDocument(
        original_name=name,
        file_type=file_type,
        size_bytes=len(data),
        sha256=fingerprint(data),
        pages=pages,
    )


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [" ".join(p.split()) for p in _BLANK_LINES.split(text)]
    return "\n\n".join(p for p in paragraphs if p)


def _split_end(text: str, start: int, size: int) -> int:
    """End of a window starting at `start`, preferring paragraph, sentence, then word breaks."""
    hard_end = start + size
    if hard_end >= len(text):
        return len(text)
    window = text[start:hard_end]
    minimum = size // 2
    for separator in ("\n\n", ". ", "\n", " "):
        cut = window.rfind(separator)
        if cut >= minimum:
            return start + cut + (1 if separator == ". " else 0)
    return hard_end


def _split_page(text: str, size: int, overlap: int) -> list[str]:
    text = _normalize(text)
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = _split_end(text, start, size)
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        next_start = max(end - overlap, start + 1)
        # Move to the start of a word so the overlap does not begin mid-word.
        while next_start < end and not text[next_start - 1].isspace():
            next_start += 1
        start = next_start if next_start < end else end
    return pieces


def chunk_document(document: ParsedDocument, config: Config) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page, text in document.pages:
        for piece in _split_page(text, config.chunk_size, config.chunk_overlap):
            index = len(chunks)
            chunks.append(
                Chunk(
                    chunk_id=f"{document.sha256[:12]}-{index}",
                    source_file=document.original_name,
                    file_sha256=document.sha256,
                    index=index,
                    page=page,
                    text=piece,
                )
            )
    return chunks
