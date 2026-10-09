#!/usr/bin/env python3
from __future__ import annotations

import base64
import binascii
import json
import quopri
import sys
from email.parser import BytesParser
from email.policy import default

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
raw = (
    b"Content-Type: multipart/mixed; boundary=outer\r\n\r\n"
    b"--outer\r\nContent-Type: text/plain\r\n"
    b"Content-Transfer-Encoding: quoted-printable\r\n\r\n"
    b"hello=20world\r\n--outer--\r\n"
)
message = BytesParser(policy=default).parsebytes(raw)
parts = list(message.iter_parts())
if len(parts) != 1 or quopri.decodestring(parts[0].get_payload()).decode() != "hello world":
    raise SystemExit("MIME multipart/quoted-printable probe failed")
encoded = base64.b64encode("附件".encode())
try:
    decoded = base64.b64decode(encoded, validate=True).decode()
except (binascii.Error, UnicodeError) as exc:
    raise SystemExit(f"MIME base64 probe failed: {exc}") from exc
if decoded != "附件":
    raise SystemExit("MIME UTF-8 base64 probe failed")
print(json.dumps({
    "python3": "3.12",
    "email_parser": "passed",
    "base64": "passed",
    "binascii": "passed",
    "quopri": "passed",
}, sort_keys=True))
