"""Application services: the single entry point for the UI and the evaluation runner.

See contracts/app-service.md. The UI never calls Chroma, CrewAI, the LLM, or Langfuse
directly (constitution III).
"""

from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.config import Config
from app.errors import (
    AppError,
    EmptyKnowledgeBaseError,
    IndexingError,
    InvalidQuestionError,
    ProviderError,
    RetrievalError,
)
from app.guardrail import Answer, apply_guardrail
from app.ingestion import chunk_document, storage_path, validate_and_parse
from app.knowledge_base import FileSummary, KnowledgeBase
from app.observability import Tracer, init_observability
from app.retrieval import RetrievedChunk

logger = logging.getLogger("app")


def log_event(event: str, **fields: Any) -> None:
    """One structured log line; callers never pass question text, file content, or secrets."""
    logger.info(json.dumps({"event": event, **fields}, default=str, sort_keys=True))


@dataclass(frozen=True)
class UploadedFile:
    name: str
    data: bytes


@dataclass(frozen=True)
class FileResult:
    original_name: str
    status: str  # indexed | rejected | failed
    already_present: bool = False
    reason: str | None = None
    user_message: str | None = None
    chunk_count: int | None = None
    duration_ms: int = 0


class KnowledgeService:
    def __init__(self, config: Config, knowledge_base: KnowledgeBase) -> None:
        self._config = config
        self._kb = knowledge_base

    @property
    def embedding_model(self) -> str:
        return self._kb.embedding_model

    def ingest(self, files: list[UploadedFile]) -> list[FileResult]:
        return [self._ingest_one(f) for f in files]

    def _ingest_one(self, upload: UploadedFile) -> FileResult:
        started = time.perf_counter()
        try:
            document = validate_and_parse(upload.name, upload.data, self._config)
        except AppError as exc:
            result = FileResult(
                original_name=upload.name,
                status="rejected",
                reason=exc.reason,
                user_message=exc.user_message,
                duration_ms=_elapsed_ms(started),
            )
            log_event(
                "file_rejected", file_type=upload.name.rsplit(".", 1)[-1][:10], reason=exc.reason
            )
            return result
        try:
            chunks = chunk_document(document, self._config)
            already_present = self._kb.add(document, chunks)
            if not already_present:
                path = storage_path(upload.name, document.sha256, self._config)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(upload.data)
        except Exception as exc:
            error = exc if isinstance(exc, IndexingError) else IndexingError()
            log_event("file_failed", file_type=document.file_type, error_type=type(exc).__name__)
            return FileResult(
                original_name=upload.name,
                status="failed",
                reason=error.reason,
                user_message=error.user_message,
                duration_ms=_elapsed_ms(started),
            )
        result = FileResult(
            original_name=upload.name,
            status="indexed",
            already_present=already_present,
            chunk_count=len(chunks),
            duration_ms=_elapsed_ms(started),
        )
        log_event(
            "file_indexed",
            file_type=document.file_type,
            chunk_count=len(chunks),
            already_present=already_present,
            duration_ms=result.duration_ms,
        )
        return result

    def list_files(self) -> list[FileSummary]:
        return self._kb.list_files()

    def clear(self) -> None:
        self._kb.clear()
        uploads = self._config.uploads_dir
        if uploads.exists():
            shutil.rmtree(uploads)
        uploads.mkdir(parents=True, exist_ok=True)
        log_event("knowledge_cleared")

    def is_empty(self) -> bool:
        return self._kb.is_empty()


@dataclass
class QuestionRunResult:
    request_id: str
    status: str  # answered | abstained | failed
    answer: Answer | None = None
    retrieved: list[RetrievedChunk] = field(default_factory=list)
    error_stage: str | None = None  # retrieval | answer | guardrail | other
    error_type: str | None = None
    user_message: str | None = None
    latency_ms: int = 0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    trace_id: str | None = None


class AnswerService:
    def __init__(
        self, config: Config, knowledge_base: KnowledgeBase, llm: Any | None, tracer: Tracer
    ) -> None:
        self._config = config
        self._kb = knowledge_base
        self._llm = llm
        self._tracer = tracer

    @property
    def model_name(self) -> str:
        return str(getattr(self._llm, "model", None) or self._config.llm_model)

    def _get_llm(self) -> Any:
        if self._llm is None:
            from app.crew import build_llm

            self._llm = build_llm(self._config)
        return self._llm

    def validate_question(self, question: str) -> str:
        cleaned = question.strip()
        if not cleaned or len(cleaned) > self._config.max_question_chars:
            raise InvalidQuestionError()
        return cleaned

    def ask(self, question: str) -> QuestionRunResult:
        cleaned = self.validate_question(question)
        if self._kb.is_empty():
            raise EmptyKnowledgeBaseError()
        from app.crew import RunContext, run_crew

        request_id = uuid.uuid4().hex
        started = time.perf_counter()
        result = QuestionRunResult(request_id=request_id, status="failed")
        with self._tracer.trace_question(request_id, cleaned) as trace:
            context = RunContext(
                question=cleaned, knowledge_base=self._kb, config=self._config, trace=trace
            )
            stage = "answer"
            try:
                crew_result = run_crew(self._get_llm(), context)
                if context.retrieval_error is not None:
                    raise context.retrieval_error
                if context.retrieved is None:
                    stage = "retrieval"
                    raise RetrievalError("The retriever did not search the knowledge base.")
                stage = "guardrail"
                answer = apply_guardrail(crew_result.draft, context.retrieved)
                result.status = answer.status
                result.answer = answer
                result.prompt_tokens = crew_result.prompt_tokens
                result.completion_tokens = crew_result.completion_tokens
            except Exception as exc:
                failure = context.retrieval_error or exc
                if context.retrieval_error is not None:
                    stage = "retrieval"
                error = _user_error(failure, stage)
                result.error_stage = stage
                result.error_type = type(failure).__name__
                result.user_message = error.user_message
            result.retrieved = context.retrieved or []
            result.latency_ms = _elapsed_ms(started)
            trace.record_result(
                status=result.status,
                guardrail_decision=result.answer.guardrail_decision if result.answer else None,
                error_stage=result.error_stage,
                error_type=result.error_type,
                output=_trace_output(result),
            )
            result.trace_id = trace.trace_id
        log_event(
            "question_answered",
            request_id=request_id,
            status=result.status,
            guardrail_decision=result.answer.guardrail_decision if result.answer else None,
            error_stage=result.error_stage,
            error_type=result.error_type,
            latency_ms=result.latency_ms,
            retrieved=len(result.retrieved),
        )
        return result


def _user_error(exc: Exception, stage: str) -> AppError:
    if isinstance(exc, AppError):
        return exc
    if stage == "retrieval":
        return RetrievalError()
    if stage == "guardrail":
        return AppError()
    return ProviderError()


def _trace_output(result: QuestionRunResult) -> dict[str, Any]:
    answer = result.answer
    return {
        "status": result.status,
        "answer": answer.text if answer else None,
        "cited_chunk_ids": answer.cited_chunk_ids if answer else [],
        "citations_removed": answer.citations_removed if answer else 0,
        "error_stage": result.error_stage,
        "error_type": result.error_type,
    }


@dataclass
class Services:
    config: Config
    knowledge: KnowledgeService
    knowledge_base: KnowledgeBase
    tracer: Tracer
    answers: AnswerService


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def build_services(
    config: Config,
    llm: Any | None = None,
    embedding_function: Any | None = None,
    tracer: Tracer | None = None,
) -> Services:
    knowledge_base = KnowledgeBase(config, embedding_function=embedding_function)
    tracer = tracer or init_observability(config)
    return Services(
        config=config,
        knowledge=KnowledgeService(config, knowledge_base),
        knowledge_base=knowledge_base,
        tracer=tracer,
        answers=AnswerService(config, knowledge_base, llm, tracer),
    )
