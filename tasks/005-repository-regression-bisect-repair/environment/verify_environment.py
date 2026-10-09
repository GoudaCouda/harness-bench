#!/usr/bin/env python3
"""Verify the agent-visible runtime needed by task 005."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import re
import subprocess


def main() -> int:
    observed = {
        "python": platform.python_version(),
        "pytest": importlib.metadata.version("pytest"),
        "git": subprocess.run(
            ["git", "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip(),
    }
    expected = {
        "python_major_minor": "3.12",
        "pytest": "8.3.5",
        "git": ">=2.39,<3",
    }
    ok = (
        ".".join(observed["python"].split(".")[:2]) == expected["python_major_minor"]
        and observed["pytest"] == expected["pytest"]
        and (match := re.fullmatch(r"git version (\d+)\.(\d+)(?:\.\d+)?(?:[.-].*)?", observed["git"])) is not None
        and (2, 39) <= tuple(map(int, match.groups())) < (3, 0)
    )
    print(json.dumps({"ok": ok, "expected": expected, "observed": observed}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
