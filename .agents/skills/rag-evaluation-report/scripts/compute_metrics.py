"""Compute every metric of the catalogue for the evaluation report (standard library only).

All arithmetic of the report happens here (SK-005). Inputs are read from the project root;
the only output is reports/rag-evaluation-metrics.json (contracts/evaluation-report-files.md).

    python compute_metrics.py --root <project root>

Run collect_evidence.py first: the secret scan result and the current commit come from
reports/rag-evaluation-evidence.json.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from summarize_langfuse import load_exports, summarize  # noqa: E402

DIGITS = 4
CATEGORIES = ("answerable", "unanswerable", "multi_source")

LABELS_PLAN = (
    "Fill evaluation/labels/<run_id>.jsonl from the template written by this skill "
    "(see evaluation/README.md), then invoke the skill again."
)
EXPORT_PLAN = (
    "Run the real evaluation with Langfuse enabled, then "
    "`uv run python scripts/export_traces.py --run <run_id>`, then invoke the skill again."
)
REAL_RUN_PLAN = (
    "Run `uv run python scripts/run_evaluation.py --model-kind real` with the model and "
    "Langfuse configured, then invoke the skill again."
)

# id, family, name, decision supported, collection plan when unavailable
CATALOGUE: list[tuple[str, str, str, str, str]] = [
    (
        "MC-001",
        "Retrieval",
        "Hit Rate@k",
        "tune k, chunking, or the embedding model",
        REAL_RUN_PLAN,
    ),
    ("MC-002", "Retrieval", "Recall@k (document level)", "tune k or chunking", REAL_RUN_PLAN),
    (
        "MC-003",
        "Retrieval",
        "Precision@k",
        "lower k or raise the minimum relevance score",
        REAL_RUN_PLAN,
    ),
    ("MC-004", "Retrieval", "MRR", "change the embedding model or add reranking", REAL_RUN_PLAN),
    ("MC-005", "Retrieval", "nDCG@k", "compare retrieval configurations", REAL_RUN_PLAN),
    (
        "MC-006",
        "Retrieval",
        "Context relevance",
        "tune the minimum relevance score",
        "Add passage-level relevance labels (relevant or not, per retrieved chunk) to the label "
        "file; at document level this metric would equal MC-003.",
    ),
    (
        "MC-007",
        "Retrieval",
        "Chunk coverage",
        "change chunk size or overlap",
        "Add point-to-chunk labels: for each answer point, the retrieved chunk ids "
        "that support it.",
    ),
    (
        "MC-008",
        "Generation",
        "Faithfulness / groundedness",
        "strengthen the guardrail or prompts",
        LABELS_PLAN,
    ),
    ("MC-009", "Generation", "Answer relevance", "revise the Answer/Verifier task", LABELS_PLAN),
    (
        "MC-010",
        "Generation",
        "Context utilization",
        "revise the citation instructions",
        REAL_RUN_PLAN,
    ),
    (
        "MC-011",
        "Generation",
        "Citation correctness",
        "strengthen the citation guardrail",
        LABELS_PLAN,
    ),
    (
        "MC-012",
        "Generation",
        "Citation completeness",
        "require a citation per statement",
        LABELS_PLAN,
    ),
    (
        "MC-013",
        "Generation",
        "Unsupported-claim rate",
        "strengthen the guardrail or change model",
        LABELS_PLAN,
    ),
    (
        "MC-014",
        "Task outcome",
        "Correctness against answer points",
        "release or change model",
        LABELS_PLAN,
    ),
    (
        "MC-015",
        "Task outcome",
        "Abstention quality",
        "tune the minimum relevance score or prompts",
        REAL_RUN_PLAN,
    ),
    (
        "MC-016",
        "Task outcome",
        "Human rubric score",
        "compare releases with a human view",
        LABELS_PLAN,
    ),
    (
        "MC-017",
        "Agent workflow",
        "Task success rate",
        "fix failing steps before tuning quality",
        REAL_RUN_PLAN,
    ),
    (
        "MC-018",
        "Agent workflow",
        "Tool / retrieval failure rate",
        "fix the retrieval tool or store",
        REAL_RUN_PLAN,
    ),
    (
        "MC-019",
        "Agent workflow",
        "Number of retries",
        "tune structured-output prompts or model",
        "Export traces with retry information (`retry_count` in reports/langfuse exports).",
    ),
    ("MC-020", "Agent workflow", "Trace completeness", "fix instrumentation gaps", EXPORT_PLAN),
    ("MC-021", "Agent workflow", "Step latency", "find the slowest step", EXPORT_PLAN),
    (
        "MC-022",
        "Agent workflow",
        "End-to-end latency",
        "choose model size or hardware",
        REAL_RUN_PLAN,
    ),
    ("MC-023", "Agent workflow", "Cost / token usage", "shorten prompts or reduce k", EXPORT_PLAN),
    ("MC-024", "Operations", "Upload success rate", "fix parsing of failing files", REAL_RUN_PLAN),
    ("MC-025", "Operations", "Indexing latency", "batch embeddings or change model", REAL_RUN_PLAN),
    (
        "MC-026",
        "Operations",
        "Query throughput",
        "size hardware for concurrent users",
        "Add a load test that sends questions concurrently and records questions per minute.",
    ),
    (
        "MC-027",
        "Operations",
        "Error rate",
        "fix failing steps before tuning quality",
        REAL_RUN_PLAN,
    ),
    (
        "MC-028",
        "Operations",
        "Resource usage",
        "size hardware",
        "Record CPU and memory during indexing and answering (for example with psutil) "
        "in the run header.",
    ),
    (
        "MC-029",
        "Safety / privacy",
        "Prompt-injection detection rate",
        "harden prompts and guardrail",
        "Add documents and questions containing injection attempts to the dataset with "
        "expected safe behavior.",
    ),
    (
        "MC-030",
        "Safety / privacy",
        "Data leakage checks",
        "harden the guardrail",
        "Add test cases whose answers must not contain content from outside the retrieved chunks.",
    ),
    (
        "MC-031",
        "Safety / privacy",
        "Secret exposure",
        "remove and rotate exposed secrets",
        "Run collect_evidence.py so the secret scan result is in the evidence manifest.",
    ),
    ("MC-032", "Safety / privacy", "PII handling", "decide what may be traced and logged", ""),
]
CATALOGUE_BY_ID = {entry[0]: entry for entry in CATALOGUE}

# FR-035 areas -> test modules (traceability table of specs/tasks.md)
FR035_AREAS = {
    "1. file type and empty-file validation": ["test_ingestion_validation"],
    "2. chunking and metadata preservation": ["test_chunking"],
    "3. retrieval of relevant evidence": ["test_retrieval"],
    "4. cautious answer for an unknown question": ["test_crew_stub", "test_guardrail"],
    "5. source references when evidence is available": ["test_crew_stub"],
    "6. observability disabled or mocked": ["test_observability"],
    "7. smoke test of the main path": ["test_smoke"],
}


# --- helpers ----------------------------------------------------------------------------


def _round(value: float | None) -> float | None:
    return None if value is None else round(float(value), DIGITS)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _entry(metric_id: str, status: str, **fields: Any) -> dict[str, Any]:
    _, family, name, decision, plan = CATALOGUE_BY_ID[metric_id]
    entry = {
        "id": metric_id,
        "name": name,
        "family": family,
        "status": status,
        "value": None,
        "numerator": None,
        "denominator": None,
        "per_question": None,
        "n": None,
        "per_category": None,
        "details": None,
        "inputs": [],
        "decision": decision,
        "reason": None,
        "collection_plan": None,
    }
    entry.update(fields)
    if status == "unavailable":
        entry["value"] = None
        entry["collection_plan"] = entry["collection_plan"] or plan
    return entry


def unavailable(metric_id: str, reason: str, plan: str | None = None) -> dict[str, Any]:
    return _entry(metric_id, "unavailable", reason=reason, collection_plan=plan)


def rate(numerator: int, denominator: int) -> dict[str, Any]:
    value = numerator / denominator if denominator else None
    return {"value": _round(value), "numerator": numerator, "denominator": denominator}


def average(per_question: dict[str, float]) -> dict[str, Any]:
    values = list(per_question.values())
    return {
        "value": _round(sum(values) / len(values)) if values else None,
        "per_question": {k: _round(v) for k, v in per_question.items()},
        "n": len(values),
    }


# --- run data -----------------------------------------------------------------------------


class Run:
    def __init__(self, path: Path, root: Path) -> None:
        lines = load_jsonl(path)
        self.path = path.relative_to(root).as_posix()
        self.header = lines[0]
        self.records = [r for r in lines[1:] if r.get("record") == "question"]
        self.by_id = {r["id"]: r for r in self.records}

    @property
    def run_id(self) -> str:
        return str(self.header["run_id"])

    @property
    def model_kind(self) -> str:
        return str(self.header.get("model_kind"))


def select_runs(root: Path) -> tuple[Run | None, list[Run], list[Run]]:
    runs = [Run(p, root) for p in sorted((root / "evaluation" / "results").glob("*.jsonl"))]
    runs = [r for r in runs if r.header.get("record") == "header"]
    real = sorted(
        (r for r in runs if r.model_kind == "real"), key=lambda r: str(r.header["started_at"])
    )
    fake = sorted(
        (r for r in runs if r.model_kind == "fake"), key=lambda r: str(r.header["started_at"])
    )
    selected = real[-1] if real else None
    others = [r for r in real[:-1]]
    return selected, others, fake


class Dataset:
    def __init__(self, root: Path) -> None:
        self.questions = {q["id"]: q for q in load_jsonl(root / "evaluation" / "questions.jsonl")}
        self.expected = {
            e["id"]: e for e in load_jsonl(root / "evaluation" / "expected_answers.jsonl")
        }
        self.inputs = ["evaluation/questions.jsonl", "evaluation/expected_answers.jsonl"]

    def category(self, qid: str) -> str:
        return str(self.questions.get(qid, {}).get("category", "unknown"))

    def expects_answer(self, qid: str) -> bool:
        return self.expected.get(qid, {}).get("expected_behavior") == "answer"

    def sources(self, qid: str) -> list[str]:
        return list(self.expected.get(qid, {}).get("expected_sources") or [])


# --- script metrics -----------------------------------------------------------------------


def _answer_population(run: Run, data: Dataset) -> list[dict[str, Any]]:
    return [r for r in run.records if data.expects_answer(r["id"])]


def _relevant_ranks(record: dict[str, Any], data: Dataset) -> list[int]:
    sources = set(data.sources(record["id"]))
    return [int(c["rank"]) for c in record.get("retrieved") or [] if c["file"] in sources]


def _sliced(
    records: list[dict[str, Any]],
    data: Dataset,
    compute: Callable[[list[dict[str, Any]]], dict[str, Any]],
) -> dict[str, Any]:
    slices = {}
    for category in CATEGORIES:
        subset = [r for r in records if data.category(r["id"]) == category]
        if subset:
            slices[category] = {
                k: v
                for k, v in compute(subset).items()
                if k in ("value", "numerator", "denominator", "n")
            }
    return slices


def retrieval_metrics(run: Run, data: Dataset) -> list[dict[str, Any]]:
    population = _answer_population(run, data)
    inputs = [run.path, *data.inputs]
    k = int(run.header["k"])
    chunk_counts = {
        i["file"]: int(i.get("chunk_count") or 0) for i in run.header.get("indexing", [])
    }
    if not population:
        reason = "no question with expected_behavior 'answer' in the run"
        return [unavailable(m, reason) for m in ("MC-001", "MC-002", "MC-003", "MC-004", "MC-005")]

    def hit(records):
        return rate(sum(1 for r in records if _relevant_ranks(r, data)), len(records))

    def recall(records):
        per = {}
        for r in records:
            sources = set(data.sources(r["id"]))
            found = {c["file"] for c in r.get("retrieved") or []} & sources
            per[r["id"]] = len(found) / len(sources)
        return average(per)

    def precision(records):
        return average({r["id"]: len(_relevant_ranks(r, data)) / k for r in records})

    def mrr(records):
        return average(
            {
                r["id"]: (1 / min(_relevant_ranks(r, data)) if _relevant_ranks(r, data) else 0.0)
                for r in records
            }
        )

    def ndcg(records):
        per = {}
        for r in records:
            ranks = _relevant_ranks(r, data)
            dcg = sum(1 / math.log2(rank + 1) for rank in ranks if rank <= k)
            total_relevant = sum(chunk_counts.get(s, 0) for s in data.sources(r["id"]))
            ideal = sum(1 / math.log2(i + 1) for i in range(1, min(k, total_relevant) + 1))
            if ideal > 0:
                per[r["id"]] = dcg / ideal
        return average(per)

    results = []
    for metric_id, func in (
        ("MC-001", hit),
        ("MC-002", recall),
        ("MC-003", precision),
        ("MC-004", mrr),
        ("MC-005", ndcg),
    ):
        values = func(population)
        results.append(
            _entry(
                metric_id,
                "measured (script)",
                inputs=inputs,
                per_category=_sliced(population, data, func),
                **values,
            )
        )
    return results


def _cited_files(record: dict[str, Any]) -> set[str]:
    by_id = {c["chunk_id"]: c["file"] for c in record.get("retrieved") or []}
    return {by_id[c] for c in record.get("cited_chunk_ids") or [] if c in by_id}


def generation_script_metrics(run: Run, data: Dataset) -> list[dict[str, Any]]:
    inputs = [run.path, *data.inputs]
    population = _answer_population(run, data)

    def utilization(records):
        per = {}
        for r in records:
            sources = set(data.sources(r["id"]))
            relevant = {c["chunk_id"] for c in r.get("retrieved") or [] if c["file"] in sources}
            if relevant:
                per[r["id"]] = len(relevant & set(r.get("cited_chunk_ids") or [])) / len(relevant)
        return average(per)

    answered = [r for r in population if r["status"] == "answered"]
    expected_cited = sum(1 for r in answered if _cited_files(r) & set(data.sources(r["id"])))
    mc010 = _entry(
        "MC-010",
        "measured (script)",
        inputs=inputs,
        per_category=_sliced(population, data, utilization),
        details={
            "answered_with_expected_source_cited": expected_cited,
            "answered_expecting_answer": len(answered),
        },
        **utilization(population),
    )

    drafted = valid = removed = 0
    for r in run.records:
        if r["status"] == "failed":
            continue
        retrieved = {c["chunk_id"] for c in r.get("retrieved") or []}
        draft = r.get("draft_cited_chunk_ids") or []
        drafted += len(draft)
        valid += sum(1 for c in draft if c in retrieved)
        removed += int(r.get("citations_removed") or 0)
    validity = rate(valid, drafted)
    mc011 = _entry(
        "MC-011",
        "measured (script)",
        inputs=[run.path],
        details={"validity": validity, "citations_removed_total": removed, "support": None},
        **validity,
    )
    return [mc010, mc011]


def outcome_script_metrics(run: Run, data: Dataset) -> list[dict[str, Any]]:
    counts = {
        "abstained_when_abstention_expected": 0,
        "answered_when_answer_expected": 0,
        "abstained_when_answer_expected": 0,
        "answered_when_abstention_expected": 0,
        "failed": 0,
    }
    for r in run.records:
        expects = data.expects_answer(r["id"])
        if r["status"] == "failed":
            counts["failed"] += 1
        elif r["status"] == "abstained":
            counts[
                "abstained_when_answer_expected"
                if expects
                else "abstained_when_abstention_expected"
            ] += 1
        else:
            counts[
                "answered_when_answer_expected" if expects else "answered_when_abstention_expected"
            ] += 1
    correct = counts["abstained_when_abstention_expected"] + counts["answered_when_answer_expected"]
    return [
        _entry(
            "MC-015",
            "measured (script)",
            inputs=[run.path, *data.inputs],
            details=counts,
            **rate(correct, len(run.records)),
        )
    ]


def workflow_script_metrics(run: Run, data: Dataset) -> list[dict[str, Any]]:
    records = run.records
    n = len(records)

    def success(rs):
        return rate(sum(1 for r in rs if r["status"] in ("answered", "abstained")), len(rs))

    def errors(rs):
        return rate(sum(1 for r in rs if r["status"] == "failed"), len(rs))

    retrieval_failed = sum(
        1 for r in records if r["status"] == "failed" and r.get("error_stage") == "retrieval"
    )
    latencies = [int(r["latency_ms"]) for r in records if r.get("latency_ms") is not None]
    latency_details: dict[str, Any] = {
        "median_ms": _round(statistics.median(latencies)) if latencies else None,
        "max_ms": max(latencies) if latencies else None,
        "p95_ms": None,
    }
    if len(latencies) >= 20:
        latency_details["p95_ms"] = _round(statistics.quantiles(latencies, n=20)[-1])
    per_category_latency = {}
    for category in CATEGORIES:
        values = [int(r["latency_ms"]) for r in records if data.category(r["id"]) == category]
        if values:
            per_category_latency[category] = {
                "value": _round(statistics.median(values)),
                "n": len(values),
                "max_ms": max(values),
            }
    return [
        _entry(
            "MC-017",
            "measured (script)",
            inputs=[run.path],
            per_category=_sliced(records, data, success),
            **success(records),
        ),
        _entry("MC-018", "measured (script)", inputs=[run.path], **rate(retrieval_failed, n)),
        _entry(
            "MC-022",
            "measured (script)",
            inputs=[run.path],
            value=latency_details["max_ms"],
            n=len(latencies),
            per_question={r["id"]: r.get("latency_ms") for r in records},
            per_category=per_category_latency,
            details=latency_details,
        ),
        _entry(
            "MC-027",
            "measured (script)",
            inputs=[run.path],
            per_category=_sliced(records, data, errors),
            **errors(records),
        ),
    ]


def token_metric(run: Run, langfuse: dict[str, Any] | None) -> dict[str, Any]:
    per_question = {}
    for r in run.records:
        if r.get("prompt_tokens") is not None or r.get("completion_tokens") is not None:
            per_question[r["id"]] = {
                "prompt_tokens": r.get("prompt_tokens"),
                "completion_tokens": r.get("completion_tokens"),
            }
    if not per_question:
        return unavailable("MC-023", "the result file has no token fields")
    prompt = sum(int(v["prompt_tokens"] or 0) for v in per_question.values())
    completion = sum(int(v["completion_tokens"] or 0) for v in per_question.values())
    cost = langfuse.get("cost_total") if langfuse else None
    inputs = [run.path] + ([f"reports/langfuse/{run.run_id}/"] if langfuse else [])
    return _entry(
        "MC-023",
        "measured (script)",
        inputs=inputs,
        value=prompt + completion,
        n=len(per_question),
        per_question=per_question,
        details={
            "prompt_tokens_total": prompt,
            "completion_tokens_total": completion,
            "cost_total": cost,
            "cost_status": "measured from Langfuse cost fields"
            if cost is not None
            else "unavailable: no Langfuse cost field (local model has no price)",
        },
    )


def operations_metrics(run: Run) -> list[dict[str, Any]]:
    indexing = run.header.get("indexing") or []
    indexed = sum(1 for i in indexing if i.get("status") == "indexed")
    return [
        _entry("MC-024", "measured (script)", inputs=[run.path], **rate(indexed, len(indexing))),
        _entry(
            "MC-025",
            "measured (script)",
            inputs=[run.path],
            value=run.header.get("total_indexing_ms"),
            per_question={i["file"]: i.get("duration_ms") for i in indexing},
            n=len(indexing),
        ),
    ]


# --- label and Langfuse metrics -----------------------------------------------------------


def label_metrics(run: Run, data: Dataset, root: Path) -> list[dict[str, Any]]:
    path = root / "evaluation" / "labels" / f"{run.run_id}.jsonl"
    ids = ("MC-008", "MC-009", "MC-012", "MC-013", "MC-014", "MC-016")
    labels = {lab["id"]: lab for lab in load_jsonl(path)}
    if not labels:
        reason = f"no human labels for run {run.run_id} (evaluation/labels/{run.run_id}.jsonl)"
        return [unavailable(m, reason) for m in ids]
    inputs = [path.relative_to(root).as_posix(), run.path]
    answered = [r["id"] for r in run.records if r["status"] == "answered" and r["id"] in labels]

    def per(func: Callable[[dict[str, Any]], float | None]) -> dict[str, Any]:
        values = {qid: func(labels[qid]) for qid in answered}
        kept = {q: v for q, v in values.items() if v is not None}
        result = average(kept)
        result["details"] = {"excluded_zero_denominator": sorted(set(values) - set(kept))}
        return result

    def faith(lab):
        return lab["claims_supported"] / lab["claims_total"] if lab["claims_total"] else None

    def completeness(lab):
        s = lab["claims_supported"]
        return (s - lab["uncited_supported_claims"]) / s if s else None

    def unsupported(lab):
        return 1 - lab["claims_supported"] / lab["claims_total"] if lab["claims_total"] else None

    results = [
        _entry("MC-008", "measured (human labels)", inputs=inputs, **per(faith)),
        _entry(
            "MC-009",
            "measured (human labels)",
            inputs=inputs,
            **per(lambda lab: float(lab["answer_relevance"])),
        ),
        _entry("MC-012", "measured (human labels)", inputs=inputs, **per(completeness)),
        _entry("MC-013", "measured (human labels)", inputs=inputs, **per(unsupported)),
    ]
    population = _answer_population(run, data)
    missing = [r["id"] for r in population if r["status"] == "answered" and r["id"] not in labels]
    if missing:
        results.append(unavailable("MC-014", f"labels missing for answered questions {missing}"))
    else:
        correctness = {}
        for r in population:
            points = len(data.expected[r["id"]]["answer_points"])
            covered = len(labels[r["id"]]["points_covered"]) if r["status"] == "answered" else 0
            correctness[r["id"]] = covered / points if points else 0.0
        results.append(
            _entry(
                "MC-014",
                "measured (human labels)",
                inputs=[*inputs, *data.inputs],
                **average(correctness),
            )
        )
    results.append(
        _entry(
            "MC-016",
            "measured (human labels)",
            inputs=inputs,
            **per(lambda lab: float(lab["rubric_score"])),
        )
    )
    checked = sum(int(labels[q]["citations_checked"]) for q in answered)
    supporting = sum(int(labels[q]["citations_supporting"]) for q in answered)
    support = rate(supporting, checked) if checked else None
    return results + [{"_mc011_support": support, "_labels_path": inputs[0]}]


def langfuse_metrics(run: Run, root: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    exports = load_exports(root, run.run_id)
    ids = ("MC-019", "MC-020", "MC-021")
    if not run.header.get("langfuse_enabled"):
        reason = "Langfuse was disabled for this run"
        return [unavailable(m, reason) for m in ids], None
    if not exports:
        reason = f"no Langfuse export in reports/langfuse/{run.run_id}/"
        return [unavailable(m, reason) for m in ids], None
    summary = summarize(exports)
    inputs = [f"reports/langfuse/{run.run_id}/", run.path]
    by_trace = {r.get("trace_id"): r["id"] for r in run.records if r.get("trace_id")}
    retries = {by_trace.get(t, t): v for t, v in summary["retry_count"].items()}
    if not retries or any(v is None for v in retries.values()):
        mc019 = unavailable("MC-019", "the exports do not contain retry_count for every trace")
    else:
        mc019 = _entry(
            "MC-019",
            "measured (script)",
            inputs=inputs,
            value=sum(retries.values()),
            per_question=retries,
            n=len(retries),
        )
    complete = sum(
        1 for r in run.records if r.get("trace_id") and summary["complete"].get(r["trace_id"])
    )
    mc020 = _entry(
        "MC-020",
        "measured (script)",
        inputs=inputs,
        details={
            "exported_traces": len(exports),
            "questions_without_trace_id": sum(1 for r in run.records if not r.get("trace_id")),
        },
        **rate(complete, len(run.records)),
    )
    mc021 = _entry(
        "MC-021", "measured (script)", inputs=[inputs[0]], details=summary["steps"], n=len(exports)
    )
    return [mc019, mc020, mc021], summary


# --- tests, secrets, success criteria ------------------------------------------------------


def test_summary(root: Path) -> dict[str, Any]:
    path = root / "reports" / "test-results" / "junit.xml"
    if not path.exists():
        return {"available": False, "source": "reports/test-results/junit.xml"}
    tree = ET.parse(path)
    suites = [tree.getroot()] if tree.getroot().tag == "testsuite" else list(tree.getroot())
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time": 0.0}
    modules: dict[str, dict[str, int]] = {}
    for suite in suites:
        for key in ("tests", "failures", "errors", "skipped"):
            totals[key] += int(suite.get(key, 0))
        totals["time"] += float(suite.get("time", 0))
        for case in suite.iter("testcase"):
            module = str(case.get("classname", "")).split(".")[-1]
            bucket = modules.setdefault(module, {"passed": 0, "failed": 0, "skipped": 0})
            if case.find("failure") is not None or case.find("error") is not None:
                bucket["failed"] += 1
            elif case.find("skipped") is not None:
                bucket["skipped"] += 1
            else:
                bucket["passed"] += 1
    failed = totals["failures"] + totals["errors"]
    areas = {}
    for area, wanted in FR035_AREAS.items():
        found = {m: modules[m] for m in wanted if m in modules}
        areas[area] = {
            "modules": sorted(found),
            "passed": sum(v["passed"] for v in found.values()),
            "failed": sum(v["failed"] for v in found.values()),
        }
    return {
        "available": True,
        "passed": totals["tests"] - failed - totals["skipped"],
        "failed": failed,
        "skipped": totals["skipped"],
        "duration_s": round(totals["time"], 2),
        "fr035_areas": areas,
        "source": "reports/test-results/junit.xml",
    }


def secret_metric(evidence: dict[str, Any] | None) -> dict[str, Any]:
    scan = (evidence or {}).get("secret_scan")
    if not scan:
        return unavailable("MC-031", "no secret scan in reports/rag-evaluation-evidence.json")
    findings = scan.get("findings") or []
    return _entry(
        "MC-031",
        "measured (script)",
        inputs=["reports/rag-evaluation-evidence.json"],
        value=len(findings),
        n=int(scan.get("files_scanned") or 0),
        details={"findings": findings, "patterns": scan.get("patterns")},
    )


def _verdict(measured: Any, ok: bool | None) -> str:
    if measured is None or ok is None:
        return "not measurable"
    return "met" if ok else "not met"


def success_criteria(
    metrics: dict[str, dict[str, Any]], run: Run | None, data: Dataset
) -> list[dict[str, Any]]:
    def measured(mid: str) -> dict[str, Any] | None:
        m = metrics.get(mid)
        return m if m and m["status"].startswith("measured") else None

    criteria = []
    mc025 = measured("MC-025")
    value = mc025["value"] if mc025 else None
    criteria.append(
        {
            "id": "SC-003",
            "target": "total indexing time < 60000 ms",
            "measured": value,
            "verdict": _verdict(value, value is not None and value < 60000),
            "metric": "MC-025",
        }
    )
    mc001 = measured("MC-001")
    value = f"{mc001['numerator']}/{mc001['denominator']}" if mc001 else None
    criteria.append(
        {
            "id": "SC-004",
            "target": "every answerable and multi-source question retrieves an expected source",
            "measured": value,
            "verdict": _verdict(value, mc001 and mc001["numerator"] == mc001["denominator"]),
            "metric": "MC-001",
        }
    )
    mc010 = measured("MC-010")
    if mc010:
        d = mc010["details"]
        value = f"{d['answered_with_expected_source_cited']}/{d['answered_expecting_answer']}"
        ok = d["answered_with_expected_source_cited"] == d["answered_expecting_answer"]
    else:
        value, ok = None, None
    criteria.append(
        {
            "id": "SC-005",
            "target": "each answered question cites an expected source",
            "measured": value,
            "verdict": _verdict(value, ok),
            "metric": "MC-010",
        }
    )
    if run is not None:
        abstain_ids = [q for q in data.expected if not data.expects_answer(q)]
        done = sum(1 for q in abstain_ids if run.by_id.get(q, {}).get("status") == "abstained")
        value = f"{done}/{len(abstain_ids)}" if abstain_ids else None
        ok = done == len(abstain_ids)
    else:
        value, ok = None, None
    criteria.append(
        {
            "id": "SC-006",
            "target": "unanswerable questions receive the safe response",
            "measured": value,
            "verdict": _verdict(value, ok),
            "metric": "MC-015",
        }
    )
    mc020 = measured("MC-020")
    value = f"{mc020['numerator']}/{mc020['denominator']}" if mc020 else None
    criteria.append(
        {
            "id": "SC-007",
            "target": "one complete trace per question (real Langfuse)",
            "measured": value,
            "verdict": _verdict(value, mc020 and mc020["numerator"] == mc020["denominator"]),
            "metric": "MC-020",
        }
    )
    mc022 = measured("MC-022")
    value = mc022["value"] if mc022 else None
    criteria.append(
        {
            "id": "SC-008",
            "target": "max end-to-end latency < 30000 ms",
            "measured": value,
            "verdict": _verdict(value, value is not None and value < 30000),
            "metric": "MC-022",
        }
    )
    return criteria


# --- assembly ------------------------------------------------------------------------------


def script_metrics(run: Run, data: Dataset) -> list[dict[str, Any]]:
    return (
        retrieval_metrics(run, data)
        + generation_script_metrics(run, data)
        + outcome_script_metrics(run, data)
        + workflow_script_metrics(run, data)
        + operations_metrics(run)
    )


def compute(root: Path) -> dict[str, Any]:
    data = Dataset(root)
    evidence_path = root / "reports" / "rag-evaluation-evidence.json"
    evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else None
    selected, others, fakes = select_runs(root)
    metrics: dict[str, dict[str, Any]] = {}

    if selected is None:
        for metric_id, *_ in CATALOGUE:
            metrics[metric_id] = unavailable(metric_id, "no real-model run in evaluation/results/")
    else:
        for entry in script_metrics(selected, data):
            metrics[entry["id"]] = entry
        support = None
        for entry in label_metrics(selected, data, root):
            if "_mc011_support" in entry:
                support = entry["_mc011_support"]
                labels_path = entry["_labels_path"]
            else:
                metrics[entry["id"]] = entry
        # MC-011 keeps status "measured (script)" for part (a); part (b) has its own status.
        if support is not None:
            metrics["MC-011"]["details"]["support"] = {
                "status": "measured (human labels)",
                **support,
            }
            metrics["MC-011"]["inputs"].append(labels_path)
        else:
            metrics["MC-011"]["details"]["support"] = {
                "status": "unavailable",
                "value": None,
                "collection_plan": LABELS_PLAN,
            }
        langfuse_entries, summary = langfuse_metrics(selected, root)
        for entry in langfuse_entries:
            metrics[entry["id"]] = entry
        metrics["MC-023"] = token_metric(selected, summary)

    metrics["MC-031"] = secret_metric(evidence)
    for metric_id in ("MC-006", "MC-007", "MC-026", "MC-028", "MC-029", "MC-030"):
        if metric_id not in metrics:
            reason = {
                "MC-006": (
                    "needs passage-level relevance labels; at document level it equals MC-003"
                ),
                "MC-007": "needs point-to-chunk labels",
                "MC-026": "query throughput is not instrumented",
                "MC-028": "resource usage is not instrumented",
                "MC-029": "the dataset has no prompt-injection test cases",
                "MC-030": "the dataset has no data-leakage test cases",
            }[metric_id]
            metrics[metric_id] = unavailable(metric_id, reason)
    metrics["MC-032"] = _entry(
        "MC-032",
        "not applicable",
        reason="reported as text: what personal data is traced, logged, and stored",
        inputs=["specs/spec.md", ".env.example"],
    )
    ordered = [metrics[metric_id] for metric_id, *_ in CATALOGUE]

    current_commit = (evidence or {}).get("git_commit")
    run_info: dict[str, Any] = {
        "run_id": None,
        "model": None,
        "model_kind": None,
        "k": None,
        "git_commit": None,
        "other_runs": [r.run_id for r in others],
    }
    if selected is not None:
        run_commit = str(selected.header.get("git_commit"))
        stale = []
        if current_commit and run_commit.removesuffix("-dirty") != str(current_commit).removesuffix(
            "-dirty"
        ):
            stale.append("the run was produced from another commit than the current one")
        if run_commit.endswith("-dirty"):
            stale.append("the run was produced from a working tree with uncommitted changes")
        if (evidence or {}).get("working_tree_dirty"):
            stale.append("the current working tree has uncommitted changes")
        run_info.update(
            run_id=selected.run_id,
            model=selected.header.get("model"),
            model_kind="real",
            k=selected.header.get("k"),
            git_commit=run_commit,
            embedding_model=selected.header.get("embedding_model"),
            min_relevance_score=selected.header.get("min_relevance_score"),
            started_at=selected.header.get("started_at"),
            questions=len(selected.records),
            path=selected.path,
            staleness=stale,
            per_question=[
                {
                    "id": r["id"],
                    "category": data.category(r["id"]),
                    "status": r["status"],
                    "expected_sources": data.sources(r["id"]),
                    "retrieved_files": sorted({c["file"] for c in r.get("retrieved") or []}),
                    "cited_files": sorted(_cited_files(r)),
                    "guardrail_decision": r.get("guardrail_decision"),
                    "citations_removed": r.get("citations_removed"),
                    "latency_ms": r.get("latency_ms"),
                    "trace_id": r.get("trace_id"),
                }
                for r in selected.records
            ],
        )

    return {
        "run": run_info,
        "metrics": ordered,
        "tests": test_summary(root),
        "success_criteria": success_criteria(metrics, selected, data),
        "fake_runs": [
            {"run_id": r.run_id, "path": r.path, "metrics": script_metrics(r, data)} for r in fakes
        ],
        "primary_metric": "MC-014",
        "guardrail_metrics": ["MC-013", "MC-015", "MC-011", "MC-022", "MC-023"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    result = compute(root)
    out = root / "reports" / "rag-evaluation-metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    statuses = [m["status"] for m in result["metrics"]]
    summary = {s: statuses.count(s) for s in sorted(set(statuses))}
    print(f"wrote reports/rag-evaluation-metrics.json {summary}")


if __name__ == "__main__":
    main()
