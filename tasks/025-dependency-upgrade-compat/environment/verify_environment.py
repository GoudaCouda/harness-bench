#!/usr/bin/env python3
"""Verify the real dependency used by task 025's public workflow."""

from __future__ import annotations

import importlib.metadata
import json
import platform

from slugify import slugify


def main() -> int:
    observed = {
        "python": platform.python_version(),
        "python-slugify": importlib.metadata.version("python-slugify"),
        "probe": slugify("Crème Brûlée", allow_unicode=True, separator="_"),
    }
    expected = {
        "python_major_minor": "3.12",
        "python-slugify": "8.0.4",
        "probe": "crème_brûlée",
    }
    ok = (
        ".".join(observed["python"].split(".")[:2]) == expected["python_major_minor"]
        and observed["python-slugify"] == expected["python-slugify"]
        and observed["probe"] == expected["probe"]
    )
    print(json.dumps({"ok": ok, "expected": expected, "observed": observed}, ensure_ascii=False, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
