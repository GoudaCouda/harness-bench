#!/usr/bin/env python3
"""Verify the disposable-Git workflow required by task 075."""

from __future__ import annotations

import json
import platform
import re
import subprocess
import tempfile
from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()


def main() -> int:
    python_alias = subprocess.run(
        ["python", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="hb075-env-") as temporary:
        repo = Path(temporary)
        _git(repo, "init", "-q")
        _git(repo, "config", "user.name", "HarnessBench verifier")
        _git(repo, "config", "user.email", "verifier@example.invalid")
        _git(repo, "config", "core.ignoreCase", "true")
        source = repo / "API.py"
        source.write_text("identity\n", encoding="utf-8")
        _git(repo, "add", "API.py")
        _git(repo, "commit", "-qm", "seed")
        before = _git(repo, "hash-object", "API.py")
        _git(repo, "mv", "API.py", "temporary-hop")
        _git(repo, "mv", "temporary-hop", "api.py")
        after = _git(repo, "hash-object", "api.py")
        observed = {
            "python": platform.python_version(),
            "python_alias": python_alias,
            "git": _git(repo, "--version"),
            "index_path": _git(repo, "ls-files"),
            "oid_preserved": before == after,
        }
    expected = {
        "python_major_minor": "3.12",
        "python_alias": "3.12",
        "git": ">=2.39,<3",
        "index_path": "api.py",
        "oid_preserved": True,
    }
    ok = (
        ".".join(observed["python"].split(".")[:2]) == expected["python_major_minor"]
        and observed["python_alias"] == expected["python_alias"]
        and (match := re.fullmatch(r"git version (\d+)\.(\d+)(?:\.\d+)?(?:[.-].*)?", observed["git"])) is not None
        and (2, 39) <= tuple(map(int, match.groups())) < (3, 0)
        and observed["index_path"] == expected["index_path"]
        and observed["oid_preserved"] is True
    )
    print(json.dumps({"ok": ok, "expected": expected, "observed": observed}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
