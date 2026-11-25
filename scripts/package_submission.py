"""Build the delivery archive (standard library only).

    uv run python scripts/package_submission.py [--output dist/submission.zip]

The archive contains the files tracked by git plus the generated reports and results, with
symbolic links dereferenced: `.claude/skills/rag-evaluation-report/` holds real files, the
same as `.agents/skills/rag-evaluation-report/`. It never contains `.env` files, the
knowledge base storage, caches, virtual environments, or untracked files, and the build
fails if a file would match a secret pattern.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = "agentic-rag-assistant"

EXCLUDED = re.compile(
    r"(^|/)(\.env(\..*)?|storage|uploads|chroma|\.venv|venv|__pycache__|\.pytest_cache"
    r"|\.ruff_cache|\.cache|dist|build|\.idea|\.vscode|\.DS_Store|.*\.egg-info)(/|$)"
)
ALLOWED_ENV = ".env.example"
SECRET = re.compile(
    r"sk-lf-[A-Za-z0-9-]{8,}|pk-lf-[A-Za-z0-9-]{8,}|sk-ant-[A-Za-z0-9_-]{20,}"
    r"|sk-(?:proj-)?[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)
# Files that document or test secret patterns on purpose.
SECRET_SCAN_EXCLUDED = re.compile(
    r"(^|/)(scripts/package_submission\.py|tests/|fixtures/|collect_evidence\.py|references/privacy\.md"
    r"|uv\.lock)"
)


class PackagingError(RuntimeError):
    pass


def tracked_files(root: Path) -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True
    ).stdout.decode()
    return [path for path in output.split("\0") if path]


def is_excluded(relative: str) -> bool:
    name = relative.rsplit("/", 1)[-1]
    if name == ALLOWED_ENV:
        return False
    return bool(EXCLUDED.search(relative))


def expand(root: Path, relative: str) -> list[tuple[str, Path]]:
    """Return (archive path, real file) pairs; a linked directory is copied file by file."""
    path = root / relative
    if path.is_symlink() and path.is_dir():
        target = path.resolve()
        if not target.is_relative_to(root.resolve()):
            raise PackagingError(f"{relative} links outside the repository")
        pairs = []
        for file in sorted(target.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts:
                pairs.append((f"{relative}/{file.relative_to(target).as_posix()}", file))
        return pairs
    if path.is_file():
        return [(relative, path.resolve())]
    return []


def collect(root: Path) -> list[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = []
    for relative in tracked_files(root):
        if is_excluded(relative):
            continue
        entries.extend(expand(root, relative))
    return entries


def check_secrets(entries: list[tuple[str, Path]]) -> None:
    for archive_path, file in entries:
        if SECRET_SCAN_EXCLUDED.search(archive_path):
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if SECRET.search(line):
                raise PackagingError(f"possible secret in {archive_path}, line {number}")


def build(root: Path, output: Path) -> list[str]:
    entries = collect(root)
    for archive_path, _ in entries:
        if is_excluded(archive_path):
            raise PackagingError(f"excluded file would be packaged: {archive_path}")
    check_secrets(entries)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for archive_path, file in entries:
            archive.write(file, f"{ARCHIVE_ROOT}/{archive_path}")
    return [path for path, _ in entries]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the delivery archive.")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "dist" / "submission.zip")
    args = parser.parse_args()
    untracked = subprocess.run(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout
    if any(line.startswith((" M", "M ", "A ")) for line in untracked.splitlines()):
        print("warning: uncommitted changes are packaged as they are on disk")
    try:
        paths = build(REPO_ROOT, args.output)
    except PackagingError as exc:
        sys.exit(f"packaging failed: {exc}")
    skill_copies = [p for p in paths if p.startswith(".claude/skills/rag-evaluation-report/")]
    print(f"wrote {args.output} ({len(paths)} files, {len(skill_copies)} in the linked skill)")


if __name__ == "__main__":
    main()
