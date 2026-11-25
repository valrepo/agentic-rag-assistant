"""Local vector store wrapper around a persistent Chroma collection (ADR-0002).

One collection with cosine distance. Chroma telemetry is disabled. The embedding function is
injectable; the default is Chroma's local ONNX all-MiniLM-L6-v2 model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from app.config import Config
from app.errors import IndexingError, RetrievalError
from app.ingestion import Chunk, ParsedDocument

logger = logging.getLogger(__name__)

COLLECTION = "knowledge"
DEFAULT_EMBEDDING_MODEL = "chroma-onnx/all-MiniLM-L6-v2"


@dataclass(frozen=True)
class StoredChunk:
    chunk_id: str
    source_file: str
    file_sha256: str
    index: int
    page: int | None
    text: str
    distance: float


@dataclass(frozen=True)
class FileSummary:
    source_file: str
    file_sha256: str
    file_type: str
    chunk_count: int


class KnowledgeBase:
    def __init__(self, config: Config, embedding_function: Any | None = None) -> None:
        self._config = config
        self._embedding_function = embedding_function or DefaultEmbeddingFunction()
        if embedding_function is None:
            self.embedding_model = DEFAULT_EMBEDDING_MODEL
        else:
            name = getattr(embedding_function, "name", None)
            self.embedding_model = str(name()) if callable(name) else "custom"
        config.chroma_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(config.chroma_dir),
            settings=Settings(anonymized_telemetry=False, allow_reset=True),
        )
        self._collection = self._open_collection()

    def _open_collection(self):
        return self._client.get_or_create_collection(
            name=COLLECTION,
            configuration={"hnsw": {"space": "cosine"}},
            embedding_function=self._embedding_function,
        )

    def warm_up(self) -> None:
        """Embed one short text so a first-run model download is not timed as indexing."""
        self._embedding_function(["warm up"])

    def count(self) -> int:
        try:
            return self._collection.count()
        except Exception as exc:
            raise RetrievalError() from exc

    def is_empty(self) -> bool:
        return self.count() == 0

    def contains_file(self, sha256: str) -> bool:
        found = self._collection.get(where={"file_sha256": sha256}, limit=1, include=[])
        return bool(found["ids"])

    def add(self, document: ParsedDocument, chunks: list[Chunk]) -> bool:
        """Store the chunks of a document. Returns True when the same content was present."""
        try:
            if self.contains_file(document.sha256):
                return True
            self._collection.add(
                ids=[c.chunk_id for c in chunks],
                documents=[c.text for c in chunks],
                metadatas=[
                    {
                        "source_file": c.source_file,
                        "file_sha256": c.file_sha256,
                        "file_type": document.file_type,
                        "chunk_index": c.index,
                        "page": c.page if c.page is not None else -1,
                    }
                    for c in chunks
                ],
            )
            return False
        except Exception as exc:
            logger.warning("indexing failed", extra={"error_type": type(exc).__name__})
            raise IndexingError() from exc

    def search(self, query: str, k: int) -> list[StoredChunk]:
        try:
            total = self._collection.count()
            if total == 0:
                return []
            result = self._collection.query(
                query_texts=[query],
                n_results=min(k, total),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("retrieval failed", extra={"error_type": type(exc).__name__})
            raise RetrievalError() from exc
        hits: list[StoredChunk] = []
        for chunk_id, text, meta, distance in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
            strict=True,
        ):
            page = int(meta.get("page", -1))
            hits.append(
                StoredChunk(
                    chunk_id=chunk_id,
                    source_file=str(meta["source_file"]),
                    file_sha256=str(meta["file_sha256"]),
                    index=int(meta["chunk_index"]),
                    page=page if page > 0 else None,
                    text=text,
                    distance=float(distance),
                )
            )
        return hits

    def list_files(self) -> list[FileSummary]:
        data = self._collection.get(include=["metadatas"])
        summaries: dict[str, FileSummary] = {}
        for meta in data["metadatas"] or []:
            sha = str(meta["file_sha256"])
            current = summaries.get(sha)
            summaries[sha] = FileSummary(
                source_file=str(meta["source_file"]),
                file_sha256=sha,
                file_type=str(meta.get("file_type", "")),
                chunk_count=(current.chunk_count if current else 0) + 1,
            )
        return sorted(summaries.values(), key=lambda s: s.source_file)

    def clear(self) -> None:
        self._client.delete_collection(COLLECTION)
        self._collection = self._open_collection()
