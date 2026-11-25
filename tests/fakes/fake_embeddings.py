"""Deterministic lexical fake embeddings (research R4, FR-036).

Hashed bag of words over 384 buckets, unit normalized: texts that share words get a high
cosine similarity, so retrieval tests stay meaningful without downloading a model.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

DIMENSIONS = 384
_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "how",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "does",
        "do",
        "our",
        "we",
        "you",
        "your",
    ]
)


def _bucket(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % DIMENSIONS


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS and len(t) >= 2]


def content_words(text: str) -> set[str]:
    return set(tokens(text))


def embed_text(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for token in tokens(text):
        vector[_bucket(token)] += 1.0
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        vector[0] = 1.0
        return vector
    return [v / norm for v in vector]


class LexicalFakeEmbeddingFunction(EmbeddingFunction[Documents]):
    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        return [embed_text(text) for text in input]

    @staticmethod
    def name() -> str:
        return "lexical-fake"

    def get_config(self) -> dict[str, Any]:
        return {}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> LexicalFakeEmbeddingFunction:
        return LexicalFakeEmbeddingFunction()

    def default_space(self) -> str:
        return "cosine"
