#!/usr/bin/env python3
"""Agent-visible scoped cart tool; it has no checkout or catalog mutation action."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


def request_json(request: urllib.request.Request) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    subparsers = parser.add_subparsers(dest="action", required=True)
    show = subparsers.add_parser("show")
    show.add_argument("--user-id", required=True)
    add = subparsers.add_parser("add")
    add.add_argument("--user-id", required=True)
    add.add_argument("--product-id", required=True)
    add.add_argument("--quantity", required=True, type=int)
    args = parser.parse_args()
    if args.action == "show":
        query = urllib.parse.urlencode({"user_id": args.user_id})
        request = urllib.request.Request(args.base_url + "/api/cart?" + query)
    else:
        payload = json.dumps(
            {
                "user_id": args.user_id,
                "product_id": args.product_id,
                "quantity": args.quantity,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            args.base_url + "/api/cart/items",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    status, content = request_json(request)
    sys.stdout.buffer.write(content)
    sys.stdout.write("\n")
    return 0 if 200 <= status < 300 else 2


if __name__ == "__main__":
    raise SystemExit(main())
