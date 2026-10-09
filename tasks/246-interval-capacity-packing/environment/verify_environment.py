#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
alias = subprocess.run(
    ["python", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    capture_output=True,
    text=True,
    check=False,
    timeout=10,
)
if alias.returncode != 0 or alias.stdout.strip() != "3.12":
    raise SystemExit(f"python alias mismatch: {alias.stdout!r} {alias.stderr!r}")

layers = json.loads(
    '{"defaults":{"enabled":true,"port":8080},'
    '"environment":{"enabled":false,"port":"9090","token":null}}'
)
winning = layers["environment"]
observed = {
    "enabled": winning["enabled"],
    "port": int(winning["port"]),
    "token": winning["token"],
}
if observed != {"enabled": False, "port": 9090, "token": None}:
    raise SystemExit("typed JSON precedence probe failed")
print(json.dumps({"python": "3.12", "typed_config_probe": observed}, sort_keys=True))
