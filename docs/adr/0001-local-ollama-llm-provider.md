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
