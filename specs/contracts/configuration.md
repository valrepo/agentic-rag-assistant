# Contract: Configuration (environment variables)

Read once at startup into a frozen configuration object; optional local `.env` (never
committed). `.env.example` lists every name below with an empty or placeholder value
(FR-031, FR-032).

| Variable | Default | Purpose |
|---|---|---|
| LLM_MODEL | `ollama/llama3.1:8b` | CrewAI model string (ADR-0001) |
| LLM_BASE_URL | `http://localhost:11434` | Ollama server URL (ignored by hosted providers) |
| LLM_TEMPERATURE | `0.1` | low temperature for grounded answers |
| LLM_TIMEOUT_S | `120` | per-call timeout |
| DATA_DIR | `storage` | root for uploads and the vector store |
| CHUNK_SIZE | `800` | characters |
| CHUNK_OVERLAP | `120` | characters |
| RETRIEVAL_K | `5` | chunks returned by the retriever |
| MIN_RELEVANCE_SCORE | `0.35` | below this, a chunk does not count as evidence (tuned on the ONNX embeddings in task T046, see `evaluation/README.md`; recorded in the run header) |
| MAX_UPLOAD_MB | `10` | per file |
| MAX_QUESTION_CHARS | `1000` | |
| LANGFUSE_ENABLED | `true` | `false` gives a no-op tracer |
| LANGFUSE_PUBLIC_KEY | (empty) | Langfuse Cloud project key |
| LANGFUSE_SECRET_KEY | (empty) | Langfuse Cloud secret key |
| LANGFUSE_BASE_URL | `https://cloud.langfuse.com` | Langfuse region URL |
| CREWAI_DISABLE_TELEMETRY | `true` | disables CrewAI telemetry |
| CREWAI_TRACING_ENABLED | `false` | disables CrewAI's own tracing |

Provider keys for hosted alternatives (for example `ANTHROPIC_API_KEY`) are only needed when
`LLM_MODEL` points to that provider; they are listed, commented, in `.env.example`.

If `LANGFUSE_ENABLED=true` but a key is missing, the application starts with tracing
disabled and logs a warning (FR-028).
