#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")


def active(field: dict, direction: str) -> bool:
    if direction == "request" and field.get("readOnly"):
        return False
    if direction == "response" and field.get("writeOnly"):
        return False
    return True


properties = {
    "server_id": {"type": "string", "readOnly": True},
    "secret": {"type": "string", "writeOnly": True},
    "state": {"type": "string", "enum": ["new", "ready"]},
}
request_active = [name for name, field in properties.items() if active(field, "request")]
response_active = [name for name, field in properties.items() if active(field, "response")]
if request_active != ["secret", "state"] or response_active != ["server_id", "state"]:
    raise SystemExit("OpenAPI readOnly/writeOnly direction probe failed")

old_enum = {"new", "ready"}
request_new = {"new"}
response_new = {"new", "ready", "archived"}
if not request_new.issubset(old_enum):
    raise SystemExit("request enum subset probe failed")
if not old_enum.issubset(response_new):
    raise SystemExit("response enum variance probe failed")

mapping_old = {"cat": "#/components/schemas/Cat"}
mapping_new = {**mapping_old, "dog": "#/components/schemas/Dog"}
if not set(mapping_old).issubset(mapping_new):
    raise SystemExit("discriminator mapping expansion probe failed")

print(json.dumps({
    "python3": "3.12",
    "read_write_annotations": "passed",
    "directional_enum_variance": "passed",
    "discriminator_mapping": "passed",
    "api_service": "not_required_by_offline_task_contract",
}, sort_keys=True))
