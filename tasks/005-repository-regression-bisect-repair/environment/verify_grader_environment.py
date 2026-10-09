#!/usr/bin/env python3
"""Verify grader tooling used to inspect task 005's Git state."""

from __future__ import annotations

import json
import subprocess


def main() -> int:
    observed = subprocess.run(
        ["git", "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    expected = "git version 2.39.5"
    ok = observed == expected
    print(json.dumps({"ok": ok, "expected": expected, "observed": observed}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
