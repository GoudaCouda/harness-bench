#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 10):
    raise SystemExit(f"expected grader CPython 3.10, found {sys.version}")

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    script = root / "grant_probe.py"
    script.write_text("import json\nprint(json.dumps({'status': 'staged_not_disbursed'}))\n", encoding="utf-8")
    completed = subprocess.run(
        ["python3", script.name],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
if completed.returncode != 0:
    raise SystemExit(f"grader grant replay probe failed: {completed.stderr}")
value = json.loads(completed.stdout)
if value != {"status": "staged_not_disbursed"}:
    raise SystemExit(f"grader grant state probe failed: {value!r}")

print(json.dumps({"python3": "3.10", "writable_replay": "passed", "subprocess": "passed"}, sort_keys=True))
