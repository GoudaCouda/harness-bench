#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

with tempfile.TemporaryDirectory(prefix="hb096-env-") as temporary:
    path = Path(temporary) / "probe.json"
    payload = {"generation": 57, "ready": False, "ports": {"web": 9000}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    if json.loads(path.read_text(encoding="utf-8")) != payload:
        raise SystemExit("JSON/pathlib readback probe failed")

parser = argparse.ArgumentParser()
parser.add_argument("--observed")
if parser.parse_args(["--observed", "state.json"]).observed != "state.json":
    raise SystemExit("argparse probe failed")
probe = subprocess.run(
    ["python3", "-B", "-c", "import argparse,json,pathlib; print('ok')"],
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
)
if probe.returncode != 0 or probe.stdout.strip() != "ok":
    raise SystemExit(f"python3 simulator subprocess probe failed: {probe.stderr.strip()}")

print(json.dumps({"python3": "3.12", "offline_cluster_simulator": "passed"}, sort_keys=True))
