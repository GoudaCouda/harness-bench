from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    items = [line.strip() for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    payload = {
        "item_count": len(items),
        "items": items,
        "schema_version": "calendar_briefing_result_v1",
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
