#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.version_info < (3, 11):
    raise SystemExit(f"expected CPython >=3.11, found {sys.version}")
python3 = shutil.which("python3")
if not python3:
    raise SystemExit("python3 command is unavailable")

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    source = root / "raw.csv"
    output = root / "result.csv"
    source.write_text("arm,converted\ncontrol,0\ntreatment,1\n", encoding="utf-8")
    program = (
        "import csv,sys;"
        "rows=list(csv.DictReader(open(sys.argv[1],encoding='utf-8')));"
        "csv.writer(open(sys.argv[2],'w',newline='',encoding='utf-8')).writerows("
        "[['metric','value'],['rows',len(rows)]])"
    )
    completed = subprocess.run(
        [python3, "-c", program, str(source), str(output)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if completed.returncode != 0:
        raise SystemExit(f"stdlib analysis probe failed: {completed.stderr}")
    rows = list(csv.reader(io.StringIO(output.read_text(encoding="utf-8"))))
    if rows != [["metric", "value"], ["rows", "2"]]:
        raise SystemExit(f"CSV output probe failed: {rows!r}")

print(json.dumps({"python3": sys.version.split()[0], "stdlib_analysis": "passed"}, sort_keys=True))
