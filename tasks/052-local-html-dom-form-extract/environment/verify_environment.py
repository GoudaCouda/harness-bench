#!/usr/bin/env python3
"""Verify the agent and local appointment-service Python capabilities."""

from __future__ import annotations

import html.parser
import http.cookiejar
import json
import platform
import urllib.parse
import urllib.request


def main() -> int:
    observed = {
        "python": platform.python_version(),
        "html_parser": html.parser.HTMLParser.__module__,
        "cookie_jar": http.cookiejar.CookieJar.__module__,
        "urljoin": urllib.parse.urljoin("http://appointment:8080/base/", "slot"),
        "urllib": urllib.request.Request.__module__,
    }
    expected = {
        "python_major_minor": "3.12",
        "html_parser": "html.parser",
        "cookie_jar": "http.cookiejar",
        "urljoin": "http://appointment:8080/base/slot",
        "urllib": "urllib.request",
    }
    ok = (
        ".".join(observed["python"].split(".")[:2]) == expected["python_major_minor"]
        and {key: observed[key] for key in expected if key != "python_major_minor"}
        == {key: expected[key] for key in expected if key != "python_major_minor"}
    )
    print(json.dumps({"ok": ok, "expected": expected, "observed": observed}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
