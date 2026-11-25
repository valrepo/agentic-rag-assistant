"""In-memory Langfuse test double (research R7, SC-007).

A real Langfuse client whose spans go to an OpenTelemetry InMemorySpanExporter instead of
the network. One client per test session (Langfuse and OpenTelemetry keep global state);
`reset()` clears the captured spans between tests.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

DUMMY_PUBLIC_KEY = "pk-lf-test-public-0000"
DUMMY_SECRET_KEY = "sk-lf-test-secret-0000"


class MemoryLangfuse:
    def __init__(self) -> None:
        from langfuse import Langfuse

        from app.observability import LangfuseTracer, _instrument_crewai

        self.exporter = InMemorySpanExporter()
        self.client = Langfuse(
            public_key=DUMMY_PUBLIC_KEY,
            secret_key=DUMMY_SECRET_KEY,
            base_url="http://127.0.0.1:9",
            span_exporter=self.exporter,
        )
        _instrument_crewai()
        self.tracer = LangfuseTracer(self.client)

    def reset(self) -> None:
        self.client.flush()
        self.exporter.clear()

    def spans(self) -> list[Any]:
        self.client.flush()
        return list(self.exporter.get_finished_spans())

    def spans_by_trace(self) -> dict[str, list[Any]]:
        grouped: dict[str, list[Any]] = defaultdict(list)
        for span in self.spans():
            grouped[format(span.context.trace_id, "032x")].append(span)
        return dict(grouped)
