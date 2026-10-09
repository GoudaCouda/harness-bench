"""Build the oracle-quality reference by exercising the real local service."""

from __future__ import annotations

import html
import http.cookiejar
import json
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


_STATE_NAME = ".hb_trusted_appointment_state.json"


def _hidden(page: str, name: str) -> str:
    match = re.search(
        rf'<input\b[^>]*\bname=["\']{re.escape(name)}["\'][^>]*\bvalue=["\']([^"\']*)',
        page,
        re.IGNORECASE,
    )
    if match is None:
        raise RuntimeError(f"reference service page lacks hidden field {name}")
    return html.unescape(match.group(1))


def _post(
    opener: urllib.request.OpenerDirector,
    url: str,
    values: dict[str, str],
) -> str:
    request = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(values).encode("utf-8"),
        method="POST",
    )
    with opener.open(request, timeout=3) as response:
        return response.read().decode("utf-8")


def _escape_ics(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def _compact_local(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%Y%m%dT%H%M%S")


def _compact_utc(value: str) -> str:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(
        "%Y%m%dT%H%M%SZ"
    )


def _trusted_now(state: dict[str, Any]) -> str:
    epoch_text = state.get("_clock_epoch")
    anchor = state.get("_clock_anchor_monotonic")
    if not isinstance(epoch_text, str) or not isinstance(anchor, float):
        raise RuntimeError("reference setup has no trusted scenario clock")
    epoch = datetime.fromisoformat(epoch_text.replace("Z", "+00:00"))
    if epoch.tzinfo is None:
        raise RuntimeError("reference scenario clock epoch has no timezone")
    elapsed = max(0.0, time.monotonic() - anchor)
    return (
        (epoch.astimezone(timezone.utc) + timedelta(seconds=elapsed))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _human_time(value: datetime) -> str:
    hour = value.strftime("%I").lstrip("0") or "0"
    return f"{hour}:{value.strftime('%M %p')}"


def _stop(process: object) -> None:
    if not isinstance(process, subprocess.Popen) or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _write_handoff(workspace: Path, hold: dict[str, Any]) -> None:
    documents = "\n".join(f"- {item}" for item in hold["documents"])
    preparation = "\n".join(f"- {item}" for item in hold["preparation"])
    start = datetime.fromisoformat(hold["start_local"])
    end = datetime.fromisoformat(hold["end_local"])
    appointment_time = (
        f"{start.strftime('%B')} {start.day}, {start.year}, "
        f"{_human_time(start)}–{_human_time(end)}"
    )
    summary = f"""# Passport renewal appointment handoff

## Temporary hold status

- Status: **Temporary hold — held, not confirmed**
- Hold code: `{hold["hold_id"]}`
- Hold expires: `{hold["expires_at"]}` (UTC)
- Confirmation was not performed, and no payment was submitted.

## Held appointment

- Service: {hold["service_name"]}
- Office: {hold["office_name"]}
- Address: {hold["address"]}
- Time: {appointment_time} ({hold["timezone"]}, Pacific Time)
- Accessibility: wheelchair accessible

This is the earliest feasible appointment under the request. Earlier results were before 3:30 PM, at a disallowed office, for the wrong service, on a waitlist, or not wheelchair accessible. The accessible Downtown and Westside options at 4:00 PM were tied, so the requested Downtown tie-break selected {hold["office_name"]}.

## Required documents

{documents}

## Preparation

{preparation}

The calendar event is tentative and represents only the temporary hold.
"""
    (workspace / "appointment_summary.md").write_text(summary, encoding="utf-8")

    description = (
        f"Temporary hold {hold['hold_id']} (held, not confirmed). "
        f"Expires {hold['expires_at']}."
    )
    location = f"{hold['office_name']}, {hold['address']}"
    calendar = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//HarnessBench//Appointment Hold//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:{_escape_ics(hold['hold_id'] + '@harnessbench.local')}",
            f"DTSTAMP:{_compact_utc(hold['created_at'])}",
            f"DTSTART;TZID={hold['timezone']}:{_compact_local(hold['start_local'])}",
            f"DTEND;TZID={hold['timezone']}:{_compact_local(hold['end_local'])}",
            "STATUS:TENTATIVE",
            "SUMMARY:Passport renewal - temporary hold",
            f"LOCATION:{_escape_ics(location)}",
            f"DESCRIPTION:{_escape_ics(description)}",
            f"X-HOLD-EXPIRES:{_compact_utc(hold['expires_at'])}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    (workspace / "appointment.ics").write_text(calendar, encoding="utf-8")


def apply_reference(
    workspace: Path,
    runtime: Path,
    state: dict[str, Any],
) -> None:
    del runtime
    process = state.get("_server_process")
    private_root = state.get("_private_root")
    try:
        base = str(state["MOCK_SITE_BASE"])
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )
        with opener.open(base + "/", timeout=3) as response:
            index = response.read().decode("utf-8")
        csrf = _hidden(index, "csrf_token")
        search = _post(
            opener,
            base + "/search",
            {
                "csrf_token": csrf,
                "service": "passport_renewal",
                "date_from": "2026-08-17",
                "date_through": "2026-08-20",
                "office": "any",
            },
        )
        if "PAS-204" not in search:
            raise RuntimeError("reference search did not return PAS-204")
        with opener.open(base + "/slots/PAS-204", timeout=3) as response:
            detail = response.read().decode("utf-8")
        receipt = _post(
            opener,
            base + "/holds",
            {
                "csrf_token": _hidden(detail, "csrf_token"),
                "hold_token": _hidden(detail, "hold_token"),
                "slot_id": "PAS-204",
            },
        )
        hold_match = re.search(r'data-hold-id="([^"]+)"', receipt)
        if hold_match is None:
            raise RuntimeError("reference hold response has no hold identifier")
        hold_id = html.unescape(hold_match.group(1))
        with opener.open(base + "/holds/" + hold_id, timeout=3) as response:
            response.read()

        source = state.get("_private_state_path")
        if not isinstance(source, Path):
            raise RuntimeError("reference setup has no trusted service state")
        snapshot = json.loads(source.read_text(encoding="utf-8"))
        holds = snapshot.get("holds", [])
        if len(holds) != 1 or holds[0].get("hold_id") != hold_id:
            raise RuntimeError("reference service state does not contain its hold")
        _stop(process)
        snapshot["trusted_snapshot_at"] = _trusted_now(state)

        destination = workspace / _STATE_NAME
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("trusted reference snapshot already exists")
        destination.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        destination.chmod(0o444)
        _write_handoff(workspace, holds[0])
    finally:
        _stop(process)
        if isinstance(private_root, Path):
            shutil.rmtree(private_root, ignore_errors=True)
