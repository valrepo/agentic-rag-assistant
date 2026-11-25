# Contract: Evaluation report outputs

Files written by the `rag-evaluation-report` skill (SK-003 to SK-011). Only the skill writes
them; only under `reports/` (plus the label template under `evaluation/labels/`).

## reports/rag-evaluation-evidence.json

```json
{
  "generated_at": "ISO-8601 UTC",
  "git_commit": "str",
  "working_tree_dirty": true,
  "files": [
    {"path": "evaluation/results/....jsonl", "exists": true, "size_bytes": 0,
     "modified_at": "ISO-8601 UTC", "sha256": "hex", "records": 6}
  ],
  "env_file_present": true
}
```

`env_file_present` only records whether `.env` exists; the file is never opened.

## reports/rag-evaluation-metrics.json

```json
{
  "run": {"run_id": "str", "model": "str", "model_kind": "real", "k": 5,
          "git_commit": "str", "other_runs": ["run_id"]},
  "metrics": [
    {"id": "MC-001", "status": "measured (script)", "value": 0.75,
     "numerator": 3, "denominator": 4, "per_question": null, "n": 4,
     "inputs": ["evaluation/results/....jsonl", "evaluation/expected_answers.jsonl"],
     "reason": null, "collection_plan": null}
  ],
  "tests": {"passed": 0, "failed": 0, "skipped": 0, "duration_s": 0.0,
            "source": "reports/test-results/junit.xml"},
  "success_criteria": [
    {"id": "SC-008", "target": "max latency < 30000 ms", "measured": 21400,
     "verdict": "met", "metric": "MC-022"}
  ],
  "fake_runs": [ {"run_id": "str", "metrics": []} ]
}
```

Rules:

- `status` is one of `measured (script)`, `measured (human labels)`, `unavailable`,
  `not applicable`.
- `measured` entries have a `value`; rates have `numerator` and `denominator`; averaged
  metrics have `per_question` (`{id: value}`) and `n`.
- `unavailable` and `not applicable` entries have `value: null` and a `reason`;
  `unavailable` entries also have a `collection_plan`.
- All 32 catalogue ids appear exactly once in `metrics`.
- `fake_runs` never contributes to `metrics`.

## reports/rag-evaluation-report.md

Section order (SK-010), from `templates/rag-evaluation-report.template.md`:

1. Summary (run, model kind, staleness warning if `git_commit` differs or tree dirty)
2. Evidence inventory
3. Primary metric and guardrails
4. Metric tables per family (Id, Metric, Status, Value, n, Source, Decision supported, How
   to collect)
5. Test results
6. Success criteria (target, measured, verdict)
7. Per-question results (ids and file names only)
8. Langfuse observations
9. Fake-model runs (separate)
10. Provenance table
11. Limitations
12. Data-quality concerns
13. Privacy considerations
14. Recommended next experiments

## Self-check (scripts/check_report.py)

Exit code 0 only if: every number in sections 3 to 6 and 10 appears in the metrics file;
every trace id appears in the evidence; every `unavailable` row has no value and a
collection plan; all 32 ids are present; no fake run id appears outside section 9.
