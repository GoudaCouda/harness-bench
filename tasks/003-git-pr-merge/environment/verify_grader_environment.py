#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess

git = subprocess.run(
    ["git", "--version"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if git.returncode != 0 or git.stdout.strip() != "git version 2.39.5":
    raise SystemExit(f"unexpected grader git runtime: {git.stdout!r} {git.stderr!r}")
print(json.dumps({"git": "2.39.5"}, sort_keys=True))
