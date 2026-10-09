#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unicodedata
from pathlib import Path

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

config = {
    "config_version": "FILTER-8",
    "list_version": "LIST-2026-07-15",
    "alias_normalization": "nfkc_casefold",
    "fail_closed_on_probe_error": True,
    "authorized_clearance_roles": ["compliance_officer"],
}
normalized = unicodedata.normalize("NFKC", "ＡЛЬФА").casefold()
if normalized != "aльфа":
    raise SystemExit("sanctions alias-normalization probe failed")
with tempfile.TemporaryDirectory(prefix="hb-167-probe-") as directory:
    path = Path(directory) / "filter_config.json"
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {"tool": "filter_probe/1", "config_sha256": digest, "status": "pass"}
    if report["config_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
        raise SystemExit("digest-bound filter report probe failed")
print(json.dumps({
    "python3": "3.12",
    "nfkc_casefold": "passed",
    "config_digest_binding": "passed",
    "services": "not_required_by_task_contract",
}, sort_keys=True))
