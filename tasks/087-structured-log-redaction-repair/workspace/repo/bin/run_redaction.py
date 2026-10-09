import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.redactor import redact_event


def main():
    policy = json.loads((ROOT / "policy.json").read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (ROOT / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results = [redact_event(event, policy) for event in events]
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "redacted.jsonl").write_text(
        "".join(json.dumps(item["event"], sort_keys=True) + "\n" for item in results),
        encoding="utf-8",
    )
    kinds = {}
    for result in results:
        for finding in result["redactions"]:
            kind = finding["kind"]
            kinds[kind] = kinds.get(kind, 0) + 1
    audit = {
        "events": len(events),
        "redactions": sum(kinds.values()),
        "by_kind": dict(sorted(kinds.items())),
        "findings": [item for result in results for item in result["redactions"]],
        "status": "redacted",
    }
    (out / "audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
