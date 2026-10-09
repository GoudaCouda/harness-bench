#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from html.parser import HTMLParser

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

class Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows = []

    def handle_starttag(self, tag, attrs) -> None:
        self.rows.append((tag, dict(attrs)))

parser = Tags()
parser.feed('<nav><button aria-label="Menu">Open</button></nav>')
if parser.rows != [("nav", {}), ("button", {"aria-label": "Menu"})]:
    raise SystemExit(f"HTML parsing probe failed: {parser.rows!r}")

payload = json.dumps({"page_ids": ["home", "checkout"]}, sort_keys=True)
digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
if len(digest) != 64:
    raise SystemExit("SHA-256 receipt probe failed")

print(json.dumps({"python3": "3.12", "html_parser": "passed", "sha256": "passed"}, sort_keys=True))
