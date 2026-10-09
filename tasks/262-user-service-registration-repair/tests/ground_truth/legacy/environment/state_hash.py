from __future__ import annotations

import hashlib
from pathlib import Path


def workspace_sha256(root: str | Path) -> str:
    base = Path(root).resolve()
    digest = hashlib.sha256()
    for path in sorted(base.rglob("*")):
        relative = path.relative_to(base)
        if path.is_symlink():
            raise ValueError("workspace cannot contain symbolic links")
        encoded = relative.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        if path.is_dir():
            digest.update(b"D")
        elif path.is_file():
            digest.update(b"F")
            content = path.read_bytes()
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
        else:
            raise ValueError("workspace contains unsupported filesystem entry")
    return digest.hexdigest()
