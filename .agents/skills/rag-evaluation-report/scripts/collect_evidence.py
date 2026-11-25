"""Collect the evidence manifest and run the secret scan (standard library only).

Writes reports/rag-evaluation-evidence.json and, when the latest real run has no labels, an
empty label template evaluation/labels/<run_id>.template.jsonl. Never opens `.env` or any
`.env.*` file other than `.env.example` (SK-007); only records whether `.env` exists.

    python collect_evidence.py --root <project root>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# SK-003 sources, relative to the project root. Globs are expanded.
SOURCES = [
    "specs/constitution.md",
    "specs/spec.md",
    "specs/plan.md",
    "specs/tasks.md",
    "reports/test-results/junit.xml",
    "evaluation/questions.jsonl",
    "evaluation/expected_answers.jsonl",
    "evaluation/results/*.jsonl",
    "evaluation/labels/*.jsonl",
    ".env.example",
    "pyproject.toml",
    "reports/langfuse/**/*.json",
]

# Fixed secret patterns (SK-011). Only the pattern name is ever reported.
SECRET_PATTERNS = {
    "langfuse_secret_key": re.compile(r"sk-lf-[A-Za-z0-9-]{8,}"),
    "langfuse_public_key": re.compile(r"pk-lf-[A-Za-z0-9-]{8,}"),
    "openai_api_key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}"),
    "anthropic_api_key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    # A literal value assigned to a secret-like name: quoted in code, or unquoted in an
    # environment-style line. A call such as `token = make_token()` does not match.
    "assigned_secret": re.compile(
        r"(?i)\b\w*(?:secret|password|api_key|token)\w*\s*[=:]\s*['\"][A-Za-z0-9/+_.-]{16,}['\"]"
        r"|^\s*[A-Z0-9_]*(?:SECRET|PASSWORD|API_KEY|TOKEN)[A-Z0-9_]*=[A-Za-z0-9/+_.-]{16,}\s*$"
    ),
}
# Files whose job is to document or test the patterns themselves.
SCAN_EXCLUDE = re.compile(
    r"(^|/)(collect_evidence\.py|fixtures/|uv\.lock$|\.claude/skills/(?!rag-evaluation-report))"
    r"|^tests/"
)
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".toml",
    ".yml",
    ".yaml",
    ".cfg",
    ".ini",
    ".example",
    ".sh",
    ".xml",
    ".html",
    ".csv",
}


def _git(root: Path, *args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def _forbidden(path: Path) -> bool:
    name = path.name
    return name == ".env" or (name.startswith(".env.") and name != ".env.example")


def _records(path: Path) -> int | None:
    if path.suffix == ".jsonl":
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    if path.suffix == ".xml":
        return path.read_text(encoding="utf-8").count("<testcase")
    return None


def _describe(root: Path, path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": path.relative_to(root).as_posix(),
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "records": _records(path),
    }


def manifest(root: Path) -> list[dict[str, Any]]:
    files = []
    for pattern in SOURCES:
        matches = sorted(p for p in root.glob(pattern) if p.is_file() and not _forbidden(p))
        matches = [p for p in matches if not p.name.endswith(".template.jsonl")]
        if not matches:
            files.append(
                {
                    "path": pattern,
                    "exists": False,
                    "size_bytes": None,
                    "modified_at": None,
                    "sha256": None,
                    "records": None,
                }
            )
        files.extend(_describe(root, p) for p in matches)
    return files


def scan_secrets(root: Path) -> dict[str, Any]:
    tracked = _git(root, "ls-files")
    candidates = [root / line for line in (tracked or "").splitlines() if line]
    candidates += sorted((root / "reports" / "langfuse").glob("**/*.json"))
    findings = []
    scanned = 0
    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.is_file() or _forbidden(path):
            continue
        seen.add(path)
        relative = path.relative_to(root).as_posix()
        if SCAN_EXCLUDE.search(relative):
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in {".gitignore", ".python-version"}:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        scanned += 1
        for number, line in enumerate(lines, start=1):
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    findings.append({"file": relative, "line": number, "pattern": name})
    return {"files_scanned": scanned, "patterns": sorted(SECRET_PATTERNS), "findings": findings}


def _latest_real_run(root: Path) -> tuple[str, list[dict[str, Any]]] | None:
    runs = []
    for path in sorted((root / "evaluation" / "results").glob("*.jsonl")):
        lines = [
            json.loads(row) for row in path.read_text(encoding="utf-8").splitlines() if row.strip()
        ]
        if lines and lines[0].get("record") == "header" and lines[0].get("model_kind") == "real":
            runs.append((str(lines[0]["started_at"]), str(lines[0]["run_id"]), lines[1:]))
    if not runs:
        return None
    _, run_id, records = sorted(runs)[-1]
    return run_id, records


def write_label_template(root: Path) -> str | None:
    latest = _latest_real_run(root)
    if latest is None:
        return None
    run_id, records = latest
    labels_dir = root / "evaluation" / "labels"
    if (labels_dir / f"{run_id}.jsonl").exists():
        return None
    template = labels_dir / f"{run_id}.template.jsonl"
    labels_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "id": r["id"],
            "points_covered": [],
            "claims_total": None,
            "claims_supported": None,
            "uncited_supported_claims": None,
            "citations_checked": None,
            "citations_supporting": None,
            "answer_relevance": None,
            "rubric_score": None,
            "labeller": "",
        }
        for r in records
        if r.get("record") == "question" and r.get("status") == "answered"
    ]
    template.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return template.relative_to(root).as_posix()


def trace_ids(root: Path) -> list[str]:
    ids = {p.stem for p in (root / "reports" / "langfuse").glob("*/*.json")}
    for path in (root / "evaluation" / "results").glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                trace_id = json.loads(line).get("trace_id")
                if trace_id:
                    ids.add(str(trace_id))
    for path in (root / "reports" / "langfuse").glob("*.txt"):
        ids.update(re.findall(r"\b[0-9a-f]{32}\b", path.read_text(encoding="utf-8")))
    return sorted(ids)


def collect(root: Path) -> dict[str, Any]:
    commit = (_git(root, "rev-parse", "--short=12", "HEAD") or "").strip() or None
    status = _git(root, "status", "--porcelain", "--untracked-files=no")
    template = write_label_template(root)
    return {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "git_commit": commit,
        "working_tree_dirty": bool(status.strip()) if status is not None else None,
        "files": manifest(root),
        "env_file_present": (root / ".env").exists(),
        "trace_ids": trace_ids(root),
        "label_template": template,
        "secret_scan": scan_secrets(root),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    evidence = collect(root)
    out = root / "reports" / "rag-evaluation-evidence.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    found = sum(1 for f in evidence["files"] if f["exists"])
    print(
        f"wrote reports/rag-evaluation-evidence.json: {found} file(s) found, "
        f"{len(evidence['secret_scan']['findings'])} secret finding(s)"
    )
    if evidence["label_template"]:
        print(f"label template: {evidence['label_template']}")


if __name__ == "__main__":
    main()
