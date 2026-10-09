from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import sync_playwright
except ImportError as exc:  # pragma: no cover - optional external dependency
    sync_playwright = None
    PLAYWRIGHT_IMPORT_ERROR = exc
else:
    PLAYWRIGHT_IMPORT_ERROR = None


DESKTOP_VIEWPORT = {"width": 1440, "height": 900}
MOBILE_VIEWPORT = {"width": 390, "height": 844}


@dataclass
class Probe:
    filter_category: str | None = None
    selected_id: str | None = None
    scenario: str | None = None


def _load_probe(task_dir: Path | None) -> Probe:
    if task_dir is None:
        return Probe()
    contract_path = task_dir / "tests" / "ground_truth" / "frontend_contract.json"
    if not contract_path.is_file():
        return Probe()
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except Exception:
        return Probe()
    probe = contract.get("interaction_probe") or {}
    return Probe(
        filter_category=str(probe.get("filter_category") or "") or None,
        selected_id=str(probe.get("selected_id") or "") or None,
        scenario=str(probe.get("scenario") or "stress-review") or None,
    )


def _select_by_text_or_value(page, target: str) -> bool:
    target = str(target).strip()
    if not target:
        return False

    # Prefer real <select> controls when present.
    for select in page.locator("select").all():
        try:
            options = select.evaluate(
                "node => Array.from(node.options).map(opt => ({label: opt.label, value: opt.value, text: opt.textContent || ''}))"
            )
        except Exception:
            continue
        for option in options:
            if target in {str(option.get("label") or ""), str(option.get("value") or ""), str(option.get("text") or "").strip()}:
                candidate_value = str(option.get("value") or target)
                candidate_label = str(option.get("label") or option.get("text") or target).strip()
                try:
                    select.select_option(candidate_value)
                    return True
                except Exception:
                    try:
                        select.select_option(label=candidate_label)
                        return True
                    except Exception:
                        pass

    # Fall back to any clickable text/role.
    candidates = [
        page.get_by_role("button", name=re.compile(re.escape(target), re.I)),
        page.get_by_role("option", name=re.compile(re.escape(target), re.I)),
        page.get_by_text(target, exact=True),
        page.get_by_text(target, exact=False),
    ]
    for locator in candidates:
        try:
            if locator.count() > 0:
                locator.first.click(timeout=1500)
                return True
        except Exception:
            continue
    return False


def _apply_probe(page, probe: Probe) -> list[str]:
    actions: list[str] = []
    if probe.scenario and _select_by_text_or_value(page, probe.scenario):
        actions.append(f"scenario={probe.scenario}")
    if probe.filter_category and _select_by_text_or_value(page, probe.filter_category):
        actions.append(f"filter={probe.filter_category}")
    if probe.selected_id:
        clicked = False
        for candidate in [
            page.get_by_role("button", name=re.compile(re.escape(probe.selected_id), re.I)),
            page.get_by_role("link", name=re.compile(re.escape(probe.selected_id), re.I)),
            page.get_by_text(probe.selected_id, exact=True),
            page.get_by_text(probe.selected_id, exact=False),
        ]:
            try:
                if candidate.count() > 0:
                    candidate.first.click(timeout=1500)
                    clicked = True
                    break
            except Exception:
                continue
        if clicked:
            actions.append(f"selected={probe.selected_id}")
    return actions


def _capture(page, path: Path) -> dict[str, Any]:
    page.screenshot(path=str(path), full_page=True)
    text = ""
    try:
        text = page.locator("body").inner_text(timeout=1500)
    except Exception:
        pass
    return {
        "title": page.title(),
        "url": page.url,
        "text_excerpt": text[:4000],
        "viewport": page.viewport_size,
    }


def run(url: str, output_dir: Path, task_dir: Path | None = None) -> dict[str, Any]:
    if sync_playwright is None:  # pragma: no cover - optional external dependency
        raise RuntimeError(
            "playwright is not installed in this environment; install the Python package and browser binaries first"
        ) from PLAYWRIGHT_IMPORT_ERROR

    output_dir.mkdir(parents=True, exist_ok=True)
    probe = _load_probe(task_dir)
    report: dict[str, Any] = {
        "url": url,
        "task_dir": str(task_dir) if task_dir else None,
        "probe": probe.__dict__,
        "captures": {},
        "actions": [],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for label, viewport, filename in [
                ("desktop", DESKTOP_VIEWPORT, "desktop.png"),
                ("mobile", MOBILE_VIEWPORT, "mobile.png"),
            ]:
                context = browser.new_context(viewport=viewport, color_scheme="dark")
                try:
                    page = context.new_page()
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(500)
                    actions = _apply_probe(page, probe)
                    page.wait_for_timeout(250)
                    report["actions"].append({"viewport": label, "steps": actions})
                    report["captures"][label] = _capture(page, output_dir / filename)
                finally:
                    context.close()
        finally:
            browser.close()

    (output_dir / "interaction-state.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture frontend evidence with Playwright.")
    parser.add_argument("--url", required=True, help="URL of the running frontend app")
    parser.add_argument("--output-dir", required=True, help="Directory for screenshots and metadata")
    parser.add_argument("--task-dir", help="Optional task directory containing frontend_contract.json")
    args = parser.parse_args(argv)

    report = run(
        url=args.url,
        output_dir=Path(args.output_dir).resolve(),
        task_dir=Path(args.task_dir).resolve() if args.task_dir else None,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
