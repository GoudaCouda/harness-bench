import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pool import run_batch


async def main():
    items = json.loads((ROOT / "jobs.json").read_text(encoding="utf-8"))
    active = 0
    peak = 0

    async def worker(item):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(item["payload"]["delay_ms"] / 1000)
            if item["payload"]["fail"]:
                raise RuntimeError("synthetic worker failure")
            return item["payload"]["value"]
        finally:
            active -= 1

    results = await run_batch(items, worker, concurrency=2, queue_size=1)
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    counts = {name: sum(row["status"] == name for row in results) for name in ("ok", "error", "cancelled")}
    audit = {"items": len(items), "peak_concurrency": peak, "counts": counts, "ordered_ids": [row["id"] for row in results], "status": "complete"}
    (out / "audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
