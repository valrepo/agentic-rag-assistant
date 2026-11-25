# ADR-0002: ChromaDB with local ONNX embeddings

- **Status**: accepted
- **Date**: 2026-11-24
- **Review date**: at project delivery
- **Principle affected**: II (Fixed Technology Stack: local vector store and embedding model)

## Context

The knowledge base must be local, persistent, and keep chunk metadata for citations. The
embedding model must run locally on CPU.

## Decision

- Vector store: ChromaDB `PersistentClient` in `storage/chroma/` (git-ignored), cosine
  distance, chunk metadata stored with each vector.
- Embeddings: Chroma's default ONNX `all-MiniLM-L6-v2` (384 dimensions) through
  onnxruntime; downloaded once into `~/.cache/chroma`.
- Automated tests inject a deterministic lexical fake embedding function instead.

## Reason

No separate service, no torch, metadata filtering and persistence built in; chromadb is
already a CrewAI dependency.

## Risks

- First run downloads about 80 MB; the README states it and SC-003 excludes it.
- English-oriented embedding model; the sample knowledge is in English.

## Impact on reproducibility

The embedding model name is recorded in each evaluation run header; the chromadb version is
pinned in `uv.lock`.
