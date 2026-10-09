from __future__ import annotations

import json
import signal
from pathlib import Path


signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
target = Path("/workspace/oversize_payload.bin")
probe_path = Path("/workspace/oversize_probe.json")
if not probe_path.exists():
    bytes_written = 0
    limit_triggered = False
    try:
        with target.open("wb") as stream:
            chunk = b"x" * (1024 * 1024)
            for _index in range(80):
                stream.write(chunk)
                stream.flush()
                bytes_written += len(chunk)
    except OSError:
        limit_triggered = True
    probe_path.write_text(
        json.dumps(
            {"bytes_written": bytes_written, "limit_triggered": limit_triggered},
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


class RegistrationValidationError(ValueError):
    pass


class RegistrationConflict(ValueError):
    pass


def authenticate(_db_path: object, _identifier: object, _password: object) -> bool:
    return False


def register_user(*_args: object, **_kwargs: object) -> dict[str, object]:
    raise RegistrationValidationError("oversize candidate does not implement registration")
