"""Delivery archive (T059) on a temporary git repository."""

from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

import pytest

from scripts.package_submission import ARCHIVE_ROOT, PackagingError, build


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    skill = root / ".agents" / "skills" / "rag-evaluation-report"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: rag-evaluation-report\n---\n")
    (skill / "scripts" / "check_report.py").write_text("print('ok')\n")
    (root / ".claude" / "skills").mkdir(parents=True)
    os.symlink(
        "../../.agents/skills/rag-evaluation-report",
        root / ".claude" / "skills" / "rag-evaluation-report",
    )
    (root / "app.py").write_text("print('app')\n")
    (root / ".env.example").write_text("LANGFUSE_SECRET_KEY=\n")
    (root / ".gitignore").write_text(".env\nstorage/\n")
    (root / ".env").write_text("LANGFUSE_SECRET_KEY=sk-lf-real-secret-value-123\n")
    (root / "storage").mkdir()
    (root / "storage" / "kb.bin").write_text("data")
    (root / "untracked.md").write_text("not added")
    _git(root, "init", "-q")
    _git(root, "add", "app.py", ".env.example", ".gitignore", ".agents", ".claude")
    return root


def test_archive_dereferences_skill_and_excludes_private_files(repo: Path, tmp_path: Path) -> None:
    output = tmp_path / "out.zip"
    build(repo, output)
    names = set(zipfile.ZipFile(output).namelist())
    prefix = ARCHIVE_ROOT + "/"
    assert prefix + "app.py" in names
    assert prefix + ".env.example" in names
    for base in (".agents", ".claude"):
        assert f"{prefix}{base}/skills/rag-evaluation-report/SKILL.md" in names
        assert f"{prefix}{base}/skills/rag-evaluation-report/scripts/check_report.py" in names
    assert not any(n.endswith("/.env") for n in names)
    assert not any("/storage/" in n for n in names)
    assert prefix + "untracked.md" not in names
    linked = zipfile.ZipFile(output).getinfo(
        f"{prefix}.claude/skills/rag-evaluation-report/SKILL.md"
    )
    assert linked.file_size > 0, "a real file, not a link"


def test_secret_in_tracked_file_fails(repo: Path, tmp_path: Path) -> None:
    (repo / "config.py").write_text('KEY = "sk-lf-abcdefgh12345678"\n')
    _git(repo, "add", "config.py")
    with pytest.raises(PackagingError, match="config.py, line 1"):
        build(repo, tmp_path / "out.zip")


def test_tracked_env_file_is_never_packaged(repo: Path, tmp_path: Path) -> None:
    _git(repo, "add", "-f", ".env")
    output = tmp_path / "out.zip"
    build(repo, output)
    assert not any(n.endswith("/.env") for n in zipfile.ZipFile(output).namelist())
