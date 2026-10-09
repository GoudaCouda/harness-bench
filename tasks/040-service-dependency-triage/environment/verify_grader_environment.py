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
    script = root / "checkout_probe.py"
    script.write_text("import json\nprint(json.dumps({'status':'pass','passed':2,'total':2}))\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, script.name],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
if completed.returncode != 0:
    raise SystemExit(f"grader checkout replay probe failed: {completed.stderr}")
value = json.loads(completed.stdout)
if value != {"status": "pass", "passed": 2, "total": 2}:
    raise SystemExit(f"grader checkout report probe failed: {value!r}")

print(json.dumps({"python3": "3.10", "writable_replay": "passed", "subprocess": "passed"}, sort_keys=True))
