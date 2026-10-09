#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from urllib.parse import urldefrag, urljoin


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

retrieval = "https://schemas.example/catalog/orders/order.json"
effective = urljoin(retrieval, "order.json")
resolved = urljoin(effective, "../common/address.json#address")
target, fragment = urldefrag(resolved)
if (target, fragment) != ("https://schemas.example/catalog/common/address.json", "address"):
    raise SystemExit("JSON Schema effective-base/anchor resolution probe failed")

schema = {"$id": "order.json", "$ref": "../common/address.json#address", "required": ["ship_to"]}
encoded = json.dumps(schema, sort_keys=True)
decoded = json.loads(encoded)
if decoded["$id"] != "order.json" or decoded["required"] != ["ship_to"]:
    raise SystemExit("JSON Schema serialization probe failed")

with tempfile.TemporaryDirectory(prefix="hb-schema-bundle-probe-") as temporary:
    root = Path(temporary)
    out = root / "out"
    out.mkdir()
    staged = out / ".bundle_audit.json.tmp"
    final = out / "bundle_audit.json"
    staged.write_text(json.dumps({"valid": True}) + "\n", encoding="utf-8")
    staged.replace(final)
    if json.loads(final.read_text(encoding="utf-8")) != {"valid": True}:
        raise SystemExit("schema audit atomic-write probe failed")
    if len(hashlib.sha256(final.read_bytes()).hexdigest()) != 64:
        raise SystemExit("schema audit hash probe failed")

print(json.dumps({"python3": "3.12", "uri_resolution": "passed", "json": "passed", "atomic_replace": "passed", "sha256": "passed"}, sort_keys=True))
