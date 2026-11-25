# ADR-0003: Optional Docker Compose for the application

- **Status**: accepted
- **Date**: 2026-11-25
- **Principle affected**: II (Fixed Technology Stack: adding a stack component), XIV
  (Simplicity), Scope Boundaries (no LLM serving infrastructure)

## Context

The application runs natively with `uv sync --locked` and `uv run streamlit run app/ui.py`.
An evaluator may prefer to start it with one container command, without installing Python
3.13 and uv. The constitution excludes building or deploying LLM serving infrastructure:
Ollama is an external prerequisite (ADR-0001).

## Decision

- Add a `Dockerfile` (Python 3.13 slim, dependencies installed from `uv.lock` with uv) and
  a `compose.yaml` with a single service, `app`, that runs the Streamlit UI.
- Ollama is not part of the compose file. The container calls the Ollama server running on
  the host through `host.docker.internal:11434`.
- Secrets come from the local `.env` (`env_file`), never from the image; `.dockerignore`
  excludes `.env`, local storage, caches, and the evaluation artifacts.
- The knowledge base and the embedding model cache are kept in named volumes.
- The host port is configurable with `APP_PORT` (default 8501).
- Docker stays optional: the native setup remains the reference in the README, and the
  automated tests do not use Docker.

## Reason

One-command start for evaluators who already run Docker, with no change to the application
code and no LLM serving infrastructure in the project.

## Risks

- The image is about 2.2 GB (CrewAI, Chroma, ONNX runtime).
- The first indexing downloads the embedding model (about 80 MB) into the volume.
- On Linux, `host.docker.internal` relies on the `host-gateway` mapping (Docker 20.10 or
  later), and Ollama must listen on an address reachable from containers.

## Impact on reproducibility

The image installs exactly the versions of `uv.lock` (`uv sync --locked`); the base image
and uv version are pinned by tag. Validated on 2026-11-25 (macOS arm64, Docker 20.10.23,
Compose 2.15.1): the container answered a sample question with citations through the host
Ollama and sent its trace to Langfuse.
