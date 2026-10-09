#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
git = subprocess.run(
    ["git", "--version"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
match = re.fullmatch(r"git version (\d+)\.(\d+)(?:\.\d+)?(?:[.-].*)?", git.stdout.strip())
if git.returncode != 0 or match is None or not ((2, 39) <= tuple(map(int, match.groups())) < (3, 0)):
    raise SystemExit(f"expected Git >=2.39,<3, found: {git.stdout!r} {git.stderr!r}")
print(json.dumps({"python": "3.12", "git": git.stdout.strip()}, sort_keys=True))
