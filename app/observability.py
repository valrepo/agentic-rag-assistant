"""Observability: the only module that configures Langfuse and instrumentation (constitution III).

`Tracer.trace_question()` wraps one question run in one trace (FR-024, FR-025):

- root observation `rag-question` (question, request id as session id, status, guardrail
  decision), opened inside `propagate_attributes(session_id=request_id, trace_name=...)`;
- agent and task spans from the OpenInference CrewAI instrumentor;
- a `retriever` child observation per knowledge-base search (files, chunk ids, scores);
- one `generation` observation per LLM call, built from CrewAI LLM events (model, input and
  output messages, token usage, latency, errors). CrewAI runs event handlers later in a
  thread pool with a copy of the emitting context, so started and completed events are
  paired by `call_id` and the event bus is flushed before the root observation ends.

`NoOpTracer` is used when observability is disabled. Every Langfuse call is guarded:
a Langfuse failure is logged and never breaks question answering (FR-028).
"""

from __future__ import annotations

import contextvars
import logging
import threading
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, contextmanager
from typing import Any, Protocol

from app.config import Config

logger = logging.getLogger(__name__)

TRACE_NAME = "rag-question"
EVENT_FLUSH_TIMEOUT_S = 30.0


class RetrievalObservation(Protocol):
    def set_result(self, chunks: Sequence[dict[str, Any]]) -> None: ...


class QuestionTrace(Protocol):
    trace_id: str | None

    def retrieval(self, query: str) -> Any:
        """Context manager yielding a RetrievalObservation for one retrieval call."""
        ...

    def record_result(
        self,
        *,
        status: str,
        guardrail_decision: str | None = None,
        error_stage: str | None = None,
        error_type: str | None = None,
        output: dict[str, Any] | None = None,
    ) -> None: ...


class Tracer(Protocol):
    def trace_question(self, request_id: str, question: str) -> Any:
        """Context manager yielding a QuestionTrace."""
        ...

    def flush(self) -> None: ...


# --- No-op tracer -------------------------------------------------------------------------


class _NoOpRetrieval:
    def set_result(self, chunks: Sequence[dict[str, Any]]) -> None:
        return None


class _NoOpQuestionTrace:
    trace_id: str | None = None

    @contextmanager
    def retrieval(self, query: str) -> Iterator[_NoOpRetrieval]:
        yield _NoOpRetrieval()

    def record_result(self, **kwargs: Any) -> None:
        return None


class NoOpTracer:
    """Tracer that records nothing and never touches the network."""

    @contextmanager
    def trace_question(self, request_id: str, question: str) -> Iterator[_NoOpQuestionTrace]:
        yield _NoOpQuestionTrace()

    def flush(self) -> None:
        return None


# --- Langfuse tracer ----------------------------------------------------------------------


def _guard(action: str, func: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return func(*args, **kwargs)
    except Exception as exc:  # observability must never break answering
        logger.warning("langfuse %s failed: %s", action, type(exc).__name__)
        return None


class _LangfuseRetrieval:
    def __init__(self, observation: Any) -> None:
        self._observation = observation

    def set_result(self, chunks: Sequence[dict[str, Any]]) -> None:
        if self._observation is None:
            return
        _guard(
            "retrieval update",
            self._observation.update,
            output={"chunks": list(chunks)},
            metadata={
                "files": sorted({c["file"] for c in chunks}),
                "chunk_ids": [c["chunk_id"] for c in chunks],
                "scores": [c["score"] for c in chunks],
            },
        )


class _LangfuseQuestionTrace:
    def __init__(self, client: Any, root: Any, request_id: str) -> None:
        self._client = client
        self._root = root
        self.request_id = request_id
        self.trace_id: str | None = None
        self.generations: dict[str, Any] = {}
        self.pending_completions: dict[str, Any] = {}
        self.lock = threading.Lock()

    @contextmanager
    def retrieval(self, query: str) -> Iterator[Any]:
        observation = _guard(
            "retrieval start",
            self._root.start_observation,
            name="search_knowledge_base",
            as_type="retriever",
            input={"query": query},
        )
        try:
            yield _LangfuseRetrieval(observation)
        except Exception as exc:
            if observation is not None:
                _guard(
                    "retrieval error",
                    observation.update,
                    level="ERROR",
                    status_message=type(exc).__name__,
                )
            raise
        finally:
            if observation is not None:
                _guard("retrieval end", observation.end)

    def record_result(
        self,
        *,
        status: str,
        guardrail_decision: str | None = None,
        error_stage: str | None = None,
        error_type: str | None = None,
        output: dict[str, Any] | None = None,
    ) -> None:
        failed = status == "failed"
        _guard(
            "root update",
            self._root.update,
            output=output,
            level="ERROR" if failed else "DEFAULT",
            status_message=f"failed at {error_stage}: {error_type}" if failed else status,
            metadata={
                "request_id": self.request_id,
                "status": status,
                "guardrail_decision": guardrail_decision,
                "error_stage": error_stage,
                "error_type": error_type,
            },
        )

    # Generation events (called from CrewAI handler threads).

    def generation_started(self, event: Any) -> None:
        call_id = getattr(event, "call_id", None)
        if not call_id:
            return
        with self.lock:
            generation = _guard(
                "generation start",
                self._client.start_observation,
                name=f"llm-call: {getattr(event, 'agent_role', None) or 'crew'}",
                as_type="generation",
                model=getattr(event, "model", None),
                input=getattr(event, "messages", None),
                metadata={
                    "agent_role": getattr(event, "agent_role", None),
                    "task_name": getattr(event, "task_name", None),
                    "started_at": str(getattr(event, "timestamp", "")),
                },
            )
            if generation is None:
                return
            self.generations[call_id] = (generation, getattr(event, "timestamp", None))
            pending = self.pending_completions.pop(call_id, None)
        if pending is not None:
            self._finish(call_id, pending)

    def generation_finished(self, event: Any) -> None:
        call_id = getattr(event, "call_id", None)
        if not call_id:
            return
        with self.lock:
            if call_id not in self.generations:
                self.pending_completions[call_id] = event
                return
        self._finish(call_id, event)

    def _finish(self, call_id: str, event: Any) -> None:
        with self.lock:
            entry = self.generations.pop(call_id, None)
        if entry is None:
            return
        generation, started_at = entry
        update: dict[str, Any] = {"model": getattr(event, "model", None)}
        ended_at = getattr(event, "timestamp", None)
        metadata: dict[str, Any] = {}
        if started_at is not None and ended_at is not None:
            metadata["latency_ms"] = int((ended_at - started_at).total_seconds() * 1000)
        error = getattr(event, "error", None)
        if error is not None:
            update.update(level="ERROR", status_message=str(error)[:200])
        else:
            response = getattr(event, "response", None)
            update["output"] = (
                response.model_dump() if hasattr(response, "model_dump") else str(response)
            )
            usage = getattr(event, "usage", None) or {}
            if usage:
                update["usage_details"] = {
                    "input": int(usage.get("prompt_tokens", 0) or 0),
                    "output": int(usage.get("completion_tokens", 0) or 0),
                }
        update["metadata"] = metadata
        _guard("generation update", generation.update, **update)
        _guard("generation end", generation.end)

    def close_open_generations(self) -> None:
        with self.lock:
            leftovers = list(self.generations.items())
            self.generations.clear()
        for _, (generation, _) in leftovers:
            _guard(
                "generation close",
                generation.update,
                level="WARNING",
                status_message="no completion event received",
            )
            _guard("generation end", generation.end)


_ACTIVE_TRACE: contextvars.ContextVar[_LangfuseQuestionTrace | None] = contextvars.ContextVar(
    "active_question_trace", default=None
)
_LISTENER_LOCK = threading.Lock()
_LISTENER_REGISTERED = False
_INSTRUMENTED = False


def _register_llm_listener() -> None:
    """Register once the CrewAI LLM event handlers that feed generation observations."""
    global _LISTENER_REGISTERED
    with _LISTENER_LOCK:
        if _LISTENER_REGISTERED:
            return
        from crewai.events import (
            LLMCallCompletedEvent,
            LLMCallFailedEvent,
            LLMCallStartedEvent,
            crewai_event_bus,
        )

        @crewai_event_bus.on(LLMCallStartedEvent)
        def _on_started(source: Any, event: Any) -> None:
            trace = _ACTIVE_TRACE.get()
            if trace is not None:
                trace.generation_started(event)

        @crewai_event_bus.on(LLMCallCompletedEvent)
        def _on_completed(source: Any, event: Any) -> None:
            trace = _ACTIVE_TRACE.get()
            if trace is not None:
                trace.generation_finished(event)

        @crewai_event_bus.on(LLMCallFailedEvent)
        def _on_failed(source: Any, event: Any) -> None:
            trace = _ACTIVE_TRACE.get()
            if trace is not None:
                trace.generation_finished(event)

        _LISTENER_REGISTERED = True


def _instrument_crewai() -> None:
    global _INSTRUMENTED
    with _LISTENER_LOCK:
        if _INSTRUMENTED:
            return
        from openinference.instrumentation.crewai import CrewAIInstrumentor

        CrewAIInstrumentor().instrument()
        _INSTRUMENTED = True


def _flush_crewai_events() -> None:
    from crewai.events import crewai_event_bus

    completed = crewai_event_bus.flush(timeout=EVENT_FLUSH_TIMEOUT_S)
    if completed is False:
        logger.warning("crewai event handlers did not finish within %ss", EVENT_FLUSH_TIMEOUT_S)


class LangfuseTracer:
    def __init__(self, client: Any) -> None:
        self.client = client
        _register_llm_listener()

    @contextmanager
    def trace_question(self, request_id: str, question: str) -> Iterator[Any]:
        from langfuse import propagate_attributes

        stack = ExitStack()
        try:
            stack.enter_context(propagate_attributes(session_id=request_id, trace_name=TRACE_NAME))
            root = stack.enter_context(
                self.client.start_as_current_observation(
                    name=TRACE_NAME,
                    as_type="span",
                    input={"question": question, "request_id": request_id},
                    metadata={"request_id": request_id},
                )
            )
        except Exception as exc:
            logger.warning("langfuse trace start failed: %s", type(exc).__name__)
            _guard("cleanup", stack.close)
            yield _NoOpQuestionTrace()
            return

        trace = _LangfuseQuestionTrace(self.client, root, request_id)
        trace.trace_id = _guard("trace id", self.client.get_current_trace_id)
        token = _ACTIVE_TRACE.set(trace)
        try:
            yield trace
        finally:
            _guard("crewai event flush", _flush_crewai_events)
            trace.close_open_generations()
            _ACTIVE_TRACE.reset(token)
            _guard("trace end", stack.close)
            self.flush()

    def flush(self) -> None:
        _guard("flush", self.client.flush)


def init_observability(config: Config) -> Tracer:
    """Build the tracer from configuration; fall back to NoOpTracer when unavailable."""
    if not config.langfuse_enabled:
        return NoOpTracer()
    if not config.langfuse_configured:
        logger.warning("LANGFUSE_ENABLED=true but Langfuse keys are missing: tracing disabled")
        return NoOpTracer()
    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=config.langfuse_public_key,
            secret_key=config.langfuse_secret_key,
            base_url=config.langfuse_base_url,
        )
        _instrument_crewai()
        return LangfuseTracer(client)
    except Exception as exc:
        logger.warning("langfuse initialisation failed: %s; tracing disabled", type(exc).__name__)
        return NoOpTracer()
