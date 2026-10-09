#!/usr/bin/env python3
from __future__ import annotations

import io
import json
import posixpath
import sys
import tarfile

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")
paths = ["usr/bin/tool", "etc/.wh.shadow", "var/lib/.wh..wh..opq"]
if [posixpath.normpath(path) for path in paths] != paths:
    raise SystemExit("OCI POSIX-path probe failed")
buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode="w") as archive:
    for name in paths:
        info = tarfile.TarInfo(name)
        info.size = 0
        archive.addfile(info, io.BytesIO())
buffer.seek(0)
with tarfile.open(fileobj=buffer, mode="r") as archive:
    observed = archive.getnames()
if observed != paths:
    raise SystemExit("OCI tar metadata/whiteout-name probe failed")
print(json.dumps({
    "python3": "3.12",
    "posixpath": "passed",
    "tarfile_metadata": "passed",
    "whiteout_names": "passed",
}, sort_keys=True))
