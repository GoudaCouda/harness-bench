#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
alias = subprocess.run(
    ["python", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    capture_output=True,
    text=True,
    check=False,
    timeout=10,
)
if alias.returncode != 0 or alias.stdout.strip() != "3.12":
    raise SystemExit(f"python alias mismatch: {alias.stdout!r} {alias.stderr!r}")

subtotal = 330000
term_discount = subtotal * 1500 // 10000
after_term = subtotal - term_discount
coupon_discount = after_term * 500 // 10000
observed = {
    "subtotal_cents": subtotal,
    "term_discount_cents": term_discount,
    "coupon_discount_cents": coupon_discount,
    "total_cents": after_term - coupon_discount,
}
expected = {"subtotal_cents": 330000, "term_discount_cents": 49500,
            "coupon_discount_cents": 14025, "total_cents": 266475}
if observed != expected or not isinstance(observed["total_cents"], int):
    raise SystemExit(f"integer pricing probe failed: {observed}")
print(json.dumps({"python": "3.12", "integer_pricing_probe": observed}, sort_keys=True))
