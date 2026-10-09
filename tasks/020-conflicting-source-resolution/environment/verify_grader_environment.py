#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys

program = (
    "import json, re; "
    "value={'event_id':'KST-2025-0821','supersedes':'KST-2025-0807'}; "
    "assert re.fullmatch(r'KST-\\d{4}-\\d{4}', value['event_id']); "
    "print(json.dumps(value, sort_keys=True))"
)
completed = subprocess.run(
    [sys.executable, "-c", program],
    capture_output=True, text=True, check=False, timeout=10,
)
if completed.returncode != 0:
    raise SystemExit(f"grader subprocess probe failed: {completed.stderr!r}")
observed = json.loads(completed.stdout)
if observed.get("supersedes") != "KST-2025-0807":
    raise SystemExit(f"grader JSONL event probe failed: {observed}")
