"""Mechanical self-check of the evaluation report (SK-006, SK-011; standard library only).

Exit code 0 only if every rule passes. The skill must not hand back a report that fails.

    python check_report.py --root <project root>

Rules:
1. The 14 sections are present, in order.
2. Every number in sections 3 to 6 and 10 appears in reports/rag-evaluation-metrics.json.
   Ids, dates, times, run ids, and section numbers are outside the check.
3. Every trace id (32 hexadecimal characters) appears in the evidence manifest.
4. Every "unavailable" row of a metric table has no value and a collection plan.
5. All 32 catalogue ids (MC-001 to MC-032) appear in the report.
6. No fake-model run id appears outside section 9.
7. No run of 12 or more consecutive words is copied from an answer of the result files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SECTIONS = [
    "Summary",
    "Evidence inventory",
    "Primary metric and guardrails",
    "Metric tables",
    "Test results",
    "Success criteria",
    "Per-question results",
    "Langfuse observations",
    "Fake-model runs",
    "Provenance",
    "Limitations",
    "Data-quality concerns",
    "Privacy considerations",
    "Recommended next experiments",
]
NUMBER_CHECKED_SECTIONS = {3, 4, 5, 6, 10}
SHINGLE = 12

_HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)
_IGNORED_TOKENS = re.compile(
    r"\b(?:MC|SC|FR|EV|EM|SK|US|T)-?\d+\b"  # requirement, metric, task ids
    r"|\bq\d+(?:-p\d+)?\b"  # question and answer point ids
    r"|\b\d{8}T\d{6}Z(?:-\w+)?\b"  # run ids
    r"|\b\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+Z?)?\b"  # dates and timestamps
    r"|\b[0-9a-f]{12,}(?:-\d+)?\b"  # hashes, trace ids, chunk ids, commits
    r"|`[^`]*`"  # inline code (paths, ids, field names)
    r"|\bp95\b|\blog2\b|@k\b"
)
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w])")
_TRACE_ID = re.compile(r"\b[0-9a-f]{32}\b")
_WORD = re.compile(r"[a-z0-9]+")
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def split_sections(text: str) -> dict[int, tuple[str, str]]:
    matches = list(_HEADING.finditer(text))
    sections = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[int(match.group(1))] = (match.group(2).strip(), text[match.end() : end])
    return sections


def _numbers_in(value: Any, out: set[float]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        out.add(float(value))
    elif isinstance(value, str):
        for token in re.findall(r"-?\d+(?:\.\d+)?", value):
            out.add(float(token))
    elif isinstance(value, dict):
        for item in value.values():
            _numbers_in(item, out)
    elif isinstance(value, list):
        for item in value:
            _numbers_in(item, out)


def known_numbers(metrics: dict[str, Any]) -> set[float]:
    numbers: set[float] = set()
    _numbers_in({k: v for k, v in metrics.items() if k != "fake_runs"}, numbers)
    return numbers


def check_numbers(sections: dict[int, tuple[str, str]], numbers: set[float]) -> list[str]:
    problems = []
    for number in sorted(NUMBER_CHECKED_SECTIONS):
        if number not in sections:
            continue
        for line_no, line in enumerate(sections[number][1].splitlines(), start=1):
            cleaned = _IGNORED_TOKENS.sub(" ", line)
            for token in _NUMBER.findall(cleaned):
                if float(token) not in numbers:
                    problems.append(
                        f"section {number}, line {line_no}: "
                        f"number {token} is not in the metrics file"
                    )
    return problems


def check_unavailable_rows(text: str) -> list[str]:
    problems = []
    header: list[str] | None = None
    for line in text.splitlines():
        if not line.startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        if "status" not in header or "value" not in header:
            continue
        row = dict(zip(header, cells, strict=False))
        if row.get("status", "").lower() != "unavailable":
            continue
        ident = row.get("id", cells[0])
        if row.get("value") not in ("", "-"):
            problems.append(f"{ident}: unavailable metric has a value ({row.get('value')})")
        plan = row.get("how to collect", "")
        if plan in ("", "-"):
            problems.append(f"{ident}: unavailable metric has no collection plan")
    return problems


def _shingles(text: str) -> set[tuple[str, ...]]:
    words = _WORD.findall(text.lower())
    return {tuple(words[i : i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}


def check_copies(report: str, root: Path) -> list[str]:
    protected: set[tuple[str, ...]] = set()
    for path in sorted((root / "evaluation" / "results").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                answer = json.loads(line).get("answer")
                if answer:
                    protected |= _shingles(answer)
    questions = root / "evaluation" / "questions.jsonl"
    if questions.exists():
        protected -= _shingles(questions.read_text(encoding="utf-8"))
    copied = _shingles(report) & protected
    if copied:
        sample = " ".join(sorted(copied)[0])
        return [f"report copies answer text (12-word run starting '{sample[:60]}...')"]
    return []


def check(root: Path) -> list[str]:
    report_path = root / "reports" / "rag-evaluation-report.md"
    metrics_path = root / "reports" / "rag-evaluation-metrics.json"
    evidence_path = root / "reports" / "rag-evaluation-evidence.json"
    for path in (report_path, metrics_path, evidence_path):
        if not path.exists():
            return [f"missing {path.relative_to(root).as_posix()}"]
    # HTML comments are not rendered: template guidance left in comments is not checked.
    report = _COMMENT.sub("", report_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    sections = split_sections(report)
    problems: list[str] = []

    for number, title in enumerate(SECTIONS, start=1):
        if number not in sections or not sections[number][0].startswith(title):
            problems.append(f"section {number} '{title}' is missing or out of order")

    problems += check_numbers(sections, known_numbers(metrics))

    allowed_traces = set(evidence.get("trace_ids") or [])
    for trace_id in sorted(set(_TRACE_ID.findall(report))):
        if trace_id not in allowed_traces:
            problems.append(f"trace id {trace_id} is not in the evidence manifest")

    problems += check_unavailable_rows(report)

    for metric_id in (f"MC-{i:03d}" for i in range(1, 33)):
        if metric_id not in report:
            problems.append(f"{metric_id} is missing from the report")

    for fake in metrics.get("fake_runs") or []:
        for number, (_, body) in sections.items():
            if number != 9 and fake["run_id"] in body:
                problems.append(
                    f"fake run {fake['run_id']} appears outside section 9 (section {number})"
                )

    problems += check_copies(report, root)
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    problems = check(args.root.resolve())
    if problems:
        print(f"self-check FAILED ({len(problems)} problem(s)):")
        for problem in problems:
            print(f"- {problem}")
        sys.exit(1)
    print("self-check passed")


if __name__ == "__main__":
    main()
