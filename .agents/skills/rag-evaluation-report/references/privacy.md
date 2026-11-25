# Privacy and safety rules for the skill (SK-007, SK-011)

## What the skill may read and write

- Read: the SK-003 sources listed in `data-contract.md`, the skill's own files, and the
  files it wrote under `reports/`.
- Write: only `reports/rag-evaluation-evidence.json`, `reports/rag-evaluation-metrics.json`,
  `reports/rag-evaluation-report.md`, and `evaluation/labels/<run_id>.template.jsonl`.
- Never: run the application, the tests, `scripts/run_evaluation.py`, or
  `scripts/export_traces.py`; query or write to Langfuse; commit; open `.env` or any
  `.env.*` file other than `.env.example`; print environment variables or credentials.

## What may appear in the report

- Questions may be quoted: they come from the evaluation dataset.
- Answers and chunk text must not be copied. Refer to questions by id and to sources by file
  name. `check_report.py` fails if 12 or more consecutive words of an answer appear in the
  report.
- Trace ids and request ids may appear (they are random, not derived from user data).
- Model and embedding names may appear; keys, tokens, and HTTP headers never.

## Secret scan

`collect_evidence.py` scans the files tracked by git (`git ls-files`) and the trace
exports in `reports/langfuse/`, with this fixed list of patterns:

| Pattern name | Matches |
|---|---|
| `langfuse_secret_key` | `sk-lf-` followed by at least 8 key characters |
| `langfuse_public_key` | `pk-lf-` followed by at least 8 key characters |
| `openai_api_key` | `sk-` or `sk-proj-` followed by at least 20 alphanumeric characters |
| `anthropic_api_key` | `sk-ant-` followed by at least 20 key characters |
| `aws_access_key_id` | `AKIA` followed by 16 upper-case alphanumeric characters |
| `private_key_block` | a PEM private key header |
| `bearer_token` | `Bearer` followed by a token of at least 20 characters |
| `assigned_secret` | a name containing `secret`, `password`, `api_key`, or `token` assigned a literal of at least 16 characters: quoted in code, or unquoted on an environment-style line (`NAME=value`); assignments from code such as `token = make_token()` do not match |

The skill's own scripts and fixtures, the `tests/` directory (deliberate dummy keys that
exercise the secret checks), `uv.lock`, and the third-party skills are excluded. Findings report only the file, the
line number, and the pattern name, never the matched value. Any finding must be reported in
section 13 with the advice to remove and rotate the secret.

## PII handling (MC-032, reported as text)

Describe from the specifications and configuration: what the application stores (uploaded
files and chunks under `storage/`, git-ignored), what it logs (structured events with
request ids, statuses, and counts; no question text, no file content), and what it traces
in Langfuse (question, retrieved chunk metadata and a short preview, model inputs and
outputs). The sample knowledge and questions are fictional and contain no personal data.
