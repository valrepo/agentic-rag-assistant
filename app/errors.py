"""Typed domain errors with fixed user-readable messages (FR-030, constitution XI).

Messages never contain file-system paths, secrets, or stack traces.
"""

from __future__ import annotations

SUPPORTED_EXTENSIONS = (".txt", ".pdf", ".md")


class AppError(Exception):
    """Base class for errors that carry a message safe to show to the user."""

    reason = "error"

    def __init__(self, user_message: str | None = None) -> None:
        self.user_message = user_message or self.default_message()
        super().__init__(self.user_message)

    @classmethod
    def default_message(cls) -> str:
        return "An unexpected error occurred."


class UnsupportedFileTypeError(AppError):
    reason = "unsupported file type"

    @classmethod
    def default_message(cls) -> str:
        return "Unsupported file type. Supported types: " + ", ".join(SUPPORTED_EXTENSIONS) + "."


class EmptyFileError(AppError):
    reason = "empty file"

    @classmethod
    def default_message(cls) -> str:
        return "Empty file: no text could be extracted."


class FileTooLargeError(AppError):
    reason = "too large"

    def __init__(self, max_mb: float) -> None:
        super().__init__(f"File too large: the limit is {max_mb:g} MB per file.")


class UnreadableFileError(AppError):
    reason = "unreadable"

    @classmethod
    def default_message(cls) -> str:
        return "The file could not be read (invalid or corrupted content)."


class IndexingError(AppError):
    reason = "indexing error"

    @classmethod
    def default_message(cls) -> str:
        return "The file could not be indexed. Try again or check the logs."


class EmptyKnowledgeBaseError(AppError):
    @classmethod
    def default_message(cls) -> str:
        return "The knowledge base is empty. Upload and index knowledge files first."


class InvalidQuestionError(AppError):
    @classmethod
    def default_message(cls) -> str:
        return "The question is empty or too long."


class RetrievalError(AppError):
    @classmethod
    def default_message(cls) -> str:
        return "The knowledge base is unavailable. Try again later."


class ProviderError(AppError):
    @classmethod
    def default_message(cls) -> str:
        return "The language model is unavailable or timed out. Check that it is running."
