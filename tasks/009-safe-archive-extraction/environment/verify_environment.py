#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import subprocess
import sys
import tarfile

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

payload = io.BytesIO()
with tarfile.open(fileobj=payload, mode="w") as archive:
    member = tarfile.TarInfo("release/app.txt")
    member.size = 4
    archive.addfile(member, io.BytesIO(b"safe"))
payload.seek(0)
with tarfile.open(fileobj=payload, mode="r:") as archive:
    observed = [(member.name, member.size, member.isfile()) for member in archive]
if observed != [("release/app.txt", 4, True)]:
    raise SystemExit("in-memory tar metadata probe failed")
print(json.dumps({"python": "3.12", "tar_metadata": observed}, sort_keys=True))
