#!/usr/bin/env python3
"""Agent-visible read-only browser snapshot tool."""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(args.base_url + "/api/snapshot", timeout=5) as response:
            sys.stdout.buffer.write(response.read())
            sys.stdout.write("\n")
        return 0
    except urllib.error.URLError as exc:
        print(f"service_unavailable:{type(exc).__name__}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
