# ADR-0001: Local Ollama as the default LLM provider

- **Status**: accepted
- **Date**: 2026-11-24
- **Review date**: at project delivery
- **Principle affected**: II (Fixed Technology Stack), Scope Boundaries (out of scope:
  self-managed LLM serving)

## Context

The answer workflow needs an LLM. The project owner chose a local model served by Ollama
over a hosted provider, to avoid API keys and costs. The constitution lists "hosting a
self-managed LLM server" as out of scope, which could be read as excluding Ollama.

## Decision

- The default provider is a local Ollama server (an external prerequisite installed by the
  user, like a database) with the model `llama3.1:8b`, referenced through CrewAI's native
  `ollama/` route.
- The project does not build, package, or deploy any LLM serving infrastructure: Ollama is
  installed and started by the user, as documented in the README.
- The model string and base URL are configuration (`LLM_MODEL`, `LLM_BASE_URL`), so a hosted
  provider can be used without code changes.

## Reason

No cost, no key to manage, runs offline after the model download; CrewAI supports Ollama in
its core install.

## Risks

- Small local models are less reliable for tool calling and structured output; mitigated by
  a validation spike, a format guardrail with retries, and deterministic citation checks.
- Answer latency depends on the machine (16 GB RAM, CPU/Metal); SC-008 is a reported target,
  not a gate.
- The evaluator must install Ollama and pull about 5 GB.

## Impact on reproducibility

The model name is recorded in each evaluation run header and the Ollama version in the
README prerequisites; outputs are
not bit-for-bit reproducible across machines, which is already handled by the fake model in
automated tests.

## Validation (spike, 2026-11-25)

Task T012 ran the real two-agent crew (`app/crew.py`) on `ollama/llama3.1:8b` (Ollama
0.33.3, macOS arm64, 16 GB RAM) over the three sample documents indexed with the ONNX
embeddings, for three questions: one single-source, one unanswerable, one multi-source.

| Check | Result |
|---|---|
| Tool calling (`search_knowledge_base`, `result_as_answer`) | called once in 3/3 runs |
| Structured output (`AnswerDraft`) on the first attempt | 3/3, no guardrail retry |
| Unanswerable question | exact safe response (top retrieval score 0.08) |
| Multi-source question | answered with citations to both expected files |
| Invalid citations removed by the guardrail | 0 |
| End-to-end latency, warm model | 2.7 s to 8.9 s (first cold run 24 s) |

Decision: `llama3.1:8b` stays the default; the fallback `qwen2.5:7b` was not needed.

Findings applied to the code:

- CrewAI rejects a task guardrail whose return annotation is a string (postponed
  annotations); the guardrail function has no return annotation.
- The LLM instance is shared across questions and its token counters are cumulative; the
  crew reports the per-run delta (`UsageMetrics.delta_since`).
- For Ollama, CrewAI logs that the input token count is approximated (one token per four
  characters); prompt token figures are therefore estimates, to be stated in the
  evaluation report.

The throwaway spike script was deleted after this record.
