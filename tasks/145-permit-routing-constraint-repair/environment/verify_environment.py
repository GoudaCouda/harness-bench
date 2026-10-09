#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
config = {
    "map_version": "Z-2026.3",
    "precedence": ["floodplain", "historic_overlay", "zoning"],
    "routes": {
        "floodplain": "floodplain",
        "historic_overlay": "historic",
        "zoning": "zoning",
    },
}
encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
if len(hashlib.sha256(encoded).hexdigest()) != 64:
    raise SystemExit("permit config digest probe failed")
with tempfile.TemporaryDirectory(prefix="hb-permit-agent-probe-") as temporary:
    path = Path(temporary) / "config.json"
    path.write_bytes(encoded)
    output = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json,sys; print(json.load(open(sys.argv[1]))['map_version'])",
            str(path),
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    loaded = json.loads(path.read_text())
if output != "Z-2026.3" or loaded["precedence"][0] != "floodplain":
    raise SystemExit("permit precedence JSON/subprocess probe failed")
print(
    json.dumps(
        {"python3": "3.12", "json": "passed", "sha256": "passed", "subprocess": "passed"},
        sort_keys=True,
    )
)
