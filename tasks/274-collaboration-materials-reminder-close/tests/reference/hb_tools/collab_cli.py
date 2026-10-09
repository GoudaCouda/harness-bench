#!/usr/bin/env python3
"""Candidate-facing client for the synthetic case_20 collaboration sidecar."""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
from pathlib import Path, PurePosixPath


MAX_DESTINATION_BYTES = 240
MAX_COMPONENT_BYTES = 96


def emit(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def request_service(payload: dict[str, object]) -> dict[str, object]:
    import urllib.request
    endpoint = json.loads((Path(os.environ.get('HB_RUNTIME','/runtime'))/'gold20-service.json').read_text())['url']
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
    with opener.open(request, timeout=20) as response: value=json.loads(response.read(4194304))
    if not isinstance(value,dict) or value.get('ok') is not True: raise ValueError('service request failed')
    return value


def destination_path(workspace: Path, value: str) -> tuple[Path, str]:
    if (
        not value
        or "\\" in value
        or "\x00" in value
        or "//" in value
        or value.endswith("/")
        or len(value.encode("utf-8")) > MAX_DESTINATION_BYTES
    ):
        raise ValueError("destination encoding is invalid")
    pure = PurePosixPath(value)
    if pure.is_absolute() or len(pure.parts) != 4 or pure.parts[0] != "archive":
        raise ValueError("destination must be a structured relative path under archive/")
    if any(part in {"", ".", ".."} or len(part.encode("utf-8")) > MAX_COMPONENT_BYTES for part in pure.parts):
        raise ValueError("destination component is invalid")
    target = workspace.joinpath(*pure.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    resolved_parent = target.parent.resolve(strict=True)
    resolved_parent.relative_to(workspace)
    if target.exists() or target.is_symlink():
        raise FileExistsError("refusing to overwrite an existing archive path")
    return target, pure.as_posix()


def download(workspace: Path, attachment_id: str, destination: str) -> None:
    target, logical = destination_path(workspace, destination)
    try:
        response = request_service(
            {"operation": "download_attachment", "attachment_id": attachment_id, "destination": logical}
        )
        content = base64.b64decode(str(response["content_base64"]), validate=True)
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        emit(
            {
                "ok": True,
                "attachment_id": attachment_id,
                "destination": logical,
                "sha256": response["sha256"],
            }
        )
    except Exception:
        target.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(prog="collab_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    list_messages = sub.add_parser("list-messages")
    list_messages.add_argument("--channel", required=True)
    list_attachments = sub.add_parser("list-attachments")
    list_attachments.add_argument("--message-id", required=True)
    download_parser = sub.add_parser("download-attachment")
    download_parser.add_argument("--attachment-id", required=True)
    download_parser.add_argument("--destination", required=True)
    reminder_parser = sub.add_parser("send-reminder")
    reminder_parser.add_argument("--recipient-id", required=True)
    reminder_parser.add_argument("--body", required=True)
    try:
        args = parser.parse_args()
        workspace_value = os.environ.get("CASE20_WORKSPACE")
        if not workspace_value:
            raise ValueError("CASE20_WORKSPACE must be explicitly set")
        workspace = Path(workspace_value).resolve(strict=True)
        if args.command == "list-messages":
            emit(request_service({"operation": "list_messages", "channel": args.channel}))
        elif args.command == "list-attachments":
            emit(request_service({"operation": "list_attachments", "message_id": args.message_id}))
        elif args.command == "download-attachment":
            download(workspace, args.attachment_id, args.destination)
        elif args.command == "send-reminder":
            emit(
                request_service(
                    {"operation": "send_reminder", "recipient_id": args.recipient_id, "body": args.body}
                )
            )
        return 0
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        emit({"ok": False, "error": type(exc).__name__})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
