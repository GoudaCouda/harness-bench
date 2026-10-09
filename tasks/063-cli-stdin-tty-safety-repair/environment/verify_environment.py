#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import pty
import shutil
import subprocess
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected agent CPython 3.12, found {sys.version}")

python = shutil.which("python")
if not python:
    raise SystemExit("task verification command requires the python alias")
version = subprocess.run(
    [python, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if version.returncode != 0 or version.stdout.strip() != "3.12":
    raise SystemExit(f"python alias probe failed: {version.stdout!r} {version.stderr!r}")

master, slave = pty.openpty()
try:
    if not os.isatty(slave):
        raise SystemExit("POSIX pseudo-terminal probe failed")
finally:
    os.close(master)
    os.close(slave)

result = subprocess.run(
    [python, "-c", "import json,sys; print(json.dumps({'tty': sys.stdin.isatty()}))"],
    input="yes\n",
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if result.returncode != 0 or json.loads(result.stdout) != {"tty": False}:
    raise SystemExit("piped-stdin subprocess probe failed")

print(json.dumps({"python": "3.12", "posix_pty": "passed", "piped_stdin": "passed"}, sort_keys=True))
