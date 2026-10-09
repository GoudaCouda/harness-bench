#!/usr/bin/env python3
"""Reference solver that derives, rather than hard-codes, the target product."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--constraints", required=True, type=Path)
    args = parser.parse_args()
    constraints = json.loads(args.constraints.read_text(encoding="utf-8"))
    products = get_json(args.base_url + "/api/snapshot")["products"]
    eligible = []
    for product in products:
        variant_match = any(
            variant["active"]
            and variant["size"] == constraints["required_size"]
            and variant["color"] == constraints["required_color"]
            for variant in product["variants"]
        )
        if not variant_match:
            continue
        if product["rating_x10"] < constraints["minimum_rating_x10"]:
            continue
        if product["price_cents"] > constraints["maximum_price_cents"]:
            continue
        if constraints["require_in_stock"] and product["inventory"] < 1:
            continue
        eligible.append(product)
    if not eligible:
        raise RuntimeError("no eligible product")
    minimum = min(item["price_cents"] for item in eligible)
    winners = [item for item in eligible if item["price_cents"] == minimum]
    if len(winners) != 1:
        raise RuntimeError("lowest eligible product is not unique")
    winner = winners[0]
    result = post_json(
        args.base_url + "/api/cart/items",
        {
            "user_id": constraints["target_user_id"],
            "product_id": winner["product_id"],
            "quantity": constraints["required_quantity"],
        },
    )
    print(json.dumps({"selected": winner["product_id"], "api_result": result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
