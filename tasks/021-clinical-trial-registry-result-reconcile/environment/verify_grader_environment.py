#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json

rows = [
    {"source_id": "REG-V2", "authority": "controlling_prespecification"},
    {"source_id": "REG-V3", "authority": "current_but_not_prespecification"},
]
canonical = json.dumps(sorted(rows, key=lambda row: row["source_id"]), sort_keys=True)
digest = hashlib.sha256(canonical.encode()).hexdigest()
decoded = json.loads(canonical)
if decoded[0]["source_id"] != "REG-V2" or len(digest) != 64:
    raise SystemExit("grader keyed JSON/SHA-256 probe failed")
print(json.dumps({"keyed_json": "passed", "sha256": digest}, sort_keys=True))
