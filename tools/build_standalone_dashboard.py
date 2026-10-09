#!/usr/bin/env python3
"""Bundle one HarnessBench run into a self-contained, offline HTML dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVALIDATION_MARKER = "RUN_INVALIDATED.json"
INVALIDATION_MARKERS = (INVALIDATION_MARKER, "INVALIDATED.json")


def reject_invalidated_summary(summary: Path) -> None:
    """Do not turn a retired run or shard family into a shareable artifact."""
    candidate = summary.expanduser().resolve().parent
    while True:
        for marker_name in INVALIDATION_MARKERS:
            try:
                (candidate / marker_name).lstat()
            except FileNotFoundError:
                continue
            except OSError:
                raise ValueError("run invalidation state cannot be verified") from None
            raise ValueError("run is explicitly invalidated")
        if candidate == candidate.parent:
            break
        candidate = candidate.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    reject_invalidated_summary(args.summary)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    template = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
    styles = (ROOT / "dashboard" / "styles.css").read_text(encoding="utf-8")
    app = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")

    # Prevent a task title or error string from terminating the data script.
    embedded = json.dumps(summary, ensure_ascii=False).replace("</", "<\\/")
    template = template.replace(
        '<link rel="stylesheet" href="styles.css">',
        f"<style>\n{styles}\n</style>",
    )
    template = template.replace('<script src="../summary.js"></script>', "")
    template = template.replace(
        '<script src="app.js"></script>',
        (
            '<script id="harnessbench-data" type="application/json">'
            f"{embedded}</script>\n"
            "<script>\n"
            "window.HARNESSBENCH_SUMMARY = JSON.parse("
            "document.getElementById('harnessbench-data').textContent);\n"
            "window.fetch = async () => ({"
            "ok: true, json: async () => window.HARNESSBENCH_SUMMARY"
            "});\n"
            "</script>\n"
            f"<script>\n{app}\n</script>"
        ),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template, encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
