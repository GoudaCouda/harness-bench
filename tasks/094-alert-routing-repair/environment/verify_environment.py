#!/usr/bin/env python3
"""Verify task 094's pinned offline validator runtime dependencies."""

from __future__ import annotations

import importlib.metadata
import json
import platform

import yaml


def main() -> int:
    observed = {
        "python": platform.python_version(),
        "PyYAML": importlib.metadata.version("PyYAML"),
        "safe_load": yaml.safe_load("route:\n  receiver: local\n"),
    }
    expected = {
        "python_major_minor": "3.12",
        "PyYAML": "6.0.2",
        "safe_load": {"route": {"receiver": "local"}},
    }
    ok = (
        ".".join(observed["python"].split(".")[:2]) == expected["python_major_minor"]
        and observed["PyYAML"] == expected["PyYAML"]
        and observed["safe_load"] == expected["safe_load"]
    )
    print(json.dumps({"ok": ok, "expected": expected, "observed": observed}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
