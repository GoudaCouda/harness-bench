#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import hashlib
import json
import sys
import tempfile
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
rules = [(False, "config/*"), (True, "config/default.json")]
def included(name: str) -> bool:
    keep = True
    for negated, pattern in rules:
        if fnmatch.fnmatch(name, pattern) or name.startswith(pattern.rstrip("/") + "/"):
            keep = negated
    return keep
if not included("config/default.json") or included("config/local.json"):
    raise SystemExit("ordered dockerignore-negation probe failed")
with tempfile.TemporaryDirectory(prefix="hb-context-probe-") as temporary:
    root = Path(temporary)
    (root / ".env.production").write_text("TOKEN=synthetic\n", encoding="utf-8")
    (root / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    names = sorted(path.name for path in root.rglob("*") if path.is_file())
    if names != [".env.production", "Dockerfile"]:
        raise SystemExit("dotfile build-context discovery probe failed")
    manifest = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
    encoded = json.dumps(manifest, sort_keys=True)
    if json.loads(encoded) != manifest or not all(len(value) == 64 for value in manifest.values()):
        raise SystemExit("context manifest hash/JSON probe failed")
print(json.dumps({"python3": "3.12", "fnmatch_precedence": "passed", "dotfiles": "passed", "sha256_manifest": "passed"}, sort_keys=True))
