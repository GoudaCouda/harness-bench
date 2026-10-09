#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unicodedata


if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

cases = {
    "Straße": "strasse",
    "ＳＥＲＶＩＣＥ": "service",
    "e\u0301clair": "éclair",
}
observed = {
    source: unicodedata.normalize(
        "NFKC",
        unicodedata.normalize("NFKC", source).casefold(),
    )
    for source in cases
}
if observed != cases:
    raise SystemExit(f"Unicode NFKC/casefold probe failed: {observed}")
if not all(value.isidentifier() for value in observed.values()):
    raise SystemExit("Unicode identifier-profile probe failed")

print(
    json.dumps(
        {
            "python3": "3.12",
            "unicode_version": unicodedata.unidata_version,
            "nfkc_casefold": "passed",
            "identifier_profile": "passed",
        },
        sort_keys=True,
        ensure_ascii=False,
    )
)
