#!/usr/bin/env python3
"""Trusted reference driver; never copied into an agent workspace."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener


OPENER = build_opener(ProxyHandler({}))


def request_json(
    base_url: str,
    method: str,
    path: str,
    body=None,
    *,
    transient_retries: int = 0,
):
    data = None if body is None else json.dumps(body).encode("utf-8")
    for attempt in range(transient_retries + 1):
        request = Request(
            base_url.rstrip("/") + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with OPENER.open(request, timeout=10) as response:
                payload = response.read()
            if not payload:
                return None
            return json.loads(payload)
        except HTTPError as error:
            if 500 <= error.code < 600 and attempt < transient_retries:
                time.sleep(0.15 * (attempt + 1))
                continue
            raise RuntimeError(
                f"{method} {path} failed with HTTP {error.code}"
            ) from error
        except URLError as error:
            if attempt < transient_retries:
                time.sleep(0.15 * (attempt + 1))
                continue
            raise RuntimeError(f"{method} {path} failed: {error.reason}") from error
    raise AssertionError("retry loop exhausted")


def matcher_key(matcher: dict) -> tuple[object, ...]:
    return (
        matcher.get("name"),
        matcher.get("value"),
        matcher.get("isRegex"),
        matcher.get("isEqual", True),
    )


def is_active(silence: dict) -> bool:
    return silence.get("status", {}).get("state") == "active"


def is_broad_payments(silence: dict) -> bool:
    matchers = silence.get("matchers", [])
    return (
        is_active(silence)
        and isinstance(matchers, list)
        and len(matchers) == 1
        and matcher_key(matchers[0]) == ("service", "payments", False, True)
    )


def is_narrow_deploy_noise(silence: dict) -> bool:
    matchers = silence.get("matchers", [])
    return (
        is_active(silence)
        and isinstance(matchers, list)
        and {matcher_key(matcher) for matcher in matchers if isinstance(matcher, dict)}
        == {
            ("service", "payments", False, True),
            ("alertname", "DeployNoise", False, True),
        }
        and len(matchers) == 2
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--alertmanager-url",
        default=os.environ.get("ALERTMANAGER_URL"),
    )
    args = parser.parse_args()
    if not args.alertmanager_url:
        parser.error("--alertmanager-url or ALERTMANAGER_URL is required")

    silences = request_json(args.alertmanager_url, "GET", "/api/v2/silences")
    if not isinstance(silences, list):
        raise RuntimeError("silence list response is not an array")
    broad = [
        item for item in silences if isinstance(item, dict) and is_broad_payments(item)
    ]
    narrow = [
        item
        for item in silences
        if isinstance(item, dict) and is_narrow_deploy_noise(item)
    ]
    if len(broad) > 1 or len(narrow) > 1:
        raise RuntimeError("ambiguous broad or replacement silence state")

    expired_id = None
    if broad:
        expired_id = str(broad[0].get("id", ""))
        if not expired_id:
            raise RuntimeError("discovered broad silence has no resource ID")
        request_json(
            args.alertmanager_url,
            "DELETE",
            "/api/v2/silence/" + quote(expired_id, safe=""),
        )

    replacement_id = str(narrow[0].get("id", "")) if narrow else None
    if not narrow:
        starts_at = datetime.now(timezone.utc).replace(microsecond=0)
        ends_at = starts_at + timedelta(minutes=90)
        replacement = {
            "matchers": [
                {
                    "name": "service",
                    "value": "payments",
                    "isRegex": False,
                    "isEqual": True,
                },
                {
                    "name": "alertname",
                    "value": "DeployNoise",
                    "isRegex": False,
                    "isEqual": True,
                },
            ],
            "startsAt": starts_at.isoformat().replace("+00:00", "Z"),
            "endsAt": ends_at.isoformat().replace("+00:00", "Z"),
            "createdBy": "harnessbench-local-operator",
            "comment": "INC-482 local rehearsal: narrow deployment-noise suppression",
        }
        result = request_json(
            args.alertmanager_url,
            "POST",
            "/api/v2/silences",
            replacement,
        )
        if not isinstance(result, dict) or not result.get("silenceID"):
            raise RuntimeError("replacement silence response lacks silenceID")
        replacement_id = str(result["silenceID"])

    request_json(
        args.alertmanager_url,
        "POST",
        "/-/reload",
        transient_retries=3,
    )
    request_json(args.alertmanager_url, "GET", "/-/ready", transient_retries=2)
    print(
        json.dumps(
            {
                "expired": expired_id,
                "replacement": replacement_id,
                "created_replacement": not bool(narrow),
                "ready": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
