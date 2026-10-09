#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from importlib.metadata import version

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
expected = {
    "lxml": "5.3.1",
    "python-docx": "1.1.2",
    "typing_extensions": "4.12.2",
}
actual = {name: version(name) for name in expected}
if actual != expected:
    raise SystemExit(f"Office runtime mismatch: expected={expected}, actual={actual}")
print(json.dumps({"python": "3.12", "packages": actual}, sort_keys=True))
