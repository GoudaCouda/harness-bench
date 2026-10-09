#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import sys
from http.client import parse_headers
from urllib.parse import quote, unquote

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
headers = parse_headers(io.BytesIO(
    b"traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01\r\n"
    b"tracestate: rojo=00f067aa0ba902b7,congo=t61rcWkgMzE\r\n"
    b"baggage: user=alice%20smith,region=us\r\n\r\n"
))
if headers.get_all("traceparent") != [
    "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
]:
    raise SystemExit("traceparent HTTP-header probe failed")
if unquote("alice%20smith") != "alice smith" or quote("alice smith") != "alice%20smith":
    raise SystemExit("baggage percent-encoding probe failed")
if headers.get("tracestate").split(",")[0] != "rojo=00f067aa0ba902b7":
    raise SystemExit("tracestate ordering probe failed")
print(json.dumps({
    "python3": "3.12",
    "http_headers": "passed",
    "traceparent": "passed",
    "tracestate": "passed",
    "urllib_parse": "passed",
}, sort_keys=True))
