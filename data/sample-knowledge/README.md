# Sample knowledge

Three short documents about the machine learning practices of Lumenfield Labs, a fictional
company. They were written for this project, contain no real or personal data, and may be
freely redistributed with it.

| File | Type | Content |
|---|---|---|
| `model-monitoring-guide.md` | Markdown | dashboards, latency objective, data drift thresholds, retraining, review cadence |
| `incident-runbook.txt` | plain text | severity levels, first steps, model rollback, post-mortems |
| `data-retention-policy.pdf` | PDF, 2 pages | retention of training data, inference logs, model artifacts, deletion requests |

The PDF is generated from `scripts/sample_sources/data-retention-policy.txt` with
`uv run python scripts/make_sample_pdf.py scripts/sample_sources/data-retention-policy.txt data/sample-knowledge/data-retention-policy.pdf`.

This README is documentation, not knowledge: upload only the three files above.
