#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.rows.append((tag, {key: value or "" for key, value in attrs}))


def load_json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def parse(relative: str) -> list[tuple[str, dict[str, str]]]:
    parser = Tags()
    parser.feed((ROOT / relative).read_text(encoding="utf-8"))
    return parser.rows


def sample_requirements() -> tuple[set[str], dict[str, dict]]:
    inventory = load_json("page_inventory.json")["pages"]
    by_id = {row["id"]: row for row in inventory}
    selected = {
        row["id"]
        for row in inventory
        if row.get("common_owner")
        or row.get("critical_process")
        or row.get("distinct_state")
        or row.get("representative") == "structured_cards"
    }
    return selected, by_id


def sample_checks(plan: dict) -> dict[str, bool]:
    required, by_id = sample_requirements()
    page_ids = plan.get("page_ids", [])
    return {
        "scope_id": plan.get("scope_id") == load_json("evaluation_scope.json")["scope_id"],
        "known_unique_pages": isinstance(page_ids, list)
        and len(page_ids) == len(set(page_ids))
        and set(page_ids) <= set(by_id),
        "common_and_process_coverage": set(page_ids) == required,
        "duplicate_templates_excluded": not {"product", "about", "legal"} & set(page_ids),
    }


def repair_checks() -> dict[str, bool]:
    nav = parse("site/components/nav.html")
    catalog = parse("site/catalog.html")
    checkout = parse("site/checkout.html")
    error = parse("site/checkout-error.html")
    css = (ROOT / "site/styles/theme.css").read_text(encoding="utf-8")
    preserved = {
        "nav": (ROOT / "site/components/nav.html").read_text(encoding="utf-8"),
        "catalog": (ROOT / "site/catalog.html").read_text(encoding="utf-8"),
        "checkout": (ROOT / "site/checkout.html").read_text(encoding="utf-8"),
        "error": (ROOT / "site/checkout-error.html").read_text(encoding="utf-8"),
    }
    menu_buttons = [attrs for tag, attrs in nav if tag == "button" and "menu-button" in attrs.get("class", "").split()]
    images = [attrs for tag, attrs in catalog if tag == "img"]
    labels = [attrs for tag, attrs in checkout if tag == "label"]
    checkout_inputs = [attrs for tag, attrs in checkout if tag == "input" and attrs.get("id") == "email"]
    summaries = [attrs for tag, attrs in error if tag == "div" and attrs.get("id") == "error-summary"]
    error_links = [attrs for tag, attrs in error if tag == "a"]
    error_inputs = [attrs for tag, attrs in error if tag == "input" and attrs.get("id") == "email"]
    return {
        "menu_button_named_once": len(menu_buttons) == 1 and bool(menu_buttons[0].get("aria-label", "").strip()),
        "catalog_images_named": len(images) == 2 and all(attrs.get("alt", "").strip() for attrs in images),
        "checkout_email_labeled": any(attrs.get("for") == "email" for attrs in labels) and len(checkout_inputs) == 1,
        "positive_tabindex_removed": bool(checkout_inputs) and not checkout_inputs[0].get("tabindex", "").strip().lstrip("-").isdigit(),
        "error_summary_announced": len(summaries) == 1
        and (summaries[0].get("role") == "alert" or summaries[0].get("aria-live") in {"assertive", "polite"}),
        "error_navigation_and_description": any(attrs.get("href") == "#email" for attrs in error_links)
        and len(error_inputs) == 1
        and "email-error" in error_inputs[0].get("aria-describedby", "").split(),
        "visible_keyboard_focus": not re.search(r"outline\s*:\s*(?:none|0)\b", css, flags=re.I)
        and ":focus-visible" in css
        and bool(re.search(r"outline\s*:\s*(?!none|0)[^;]+", css, flags=re.I)),
        "visible_functionality_preserved": all(
            token in "\n".join(preserved.values())
            for token in (
                "Home",
                "Catalog",
                "Permit review",
                "Records request",
                "Submit request",
                "Email for receipt",
                "Review request",
                'action="/requests"',
                'name="email"',
            )
        )
        and 'href="/"' in preserved["nav"]
        and 'href="/catalog"' in preserved["nav"]
        and 'src="permit.png"' in preserved["catalog"]
        and 'src="records.png"' in preserved["catalog"],
    }


def evaluate(plan: dict) -> dict[str, object]:
    sample = sample_checks(plan)
    repairs = repair_checks()
    return {
        "sample": sample,
        "repairs": repairs,
        "sample_pass": all(sample.values()),
        "repair_pass": all(repairs.values()),
    }


def certify(plan: dict) -> None:
    result = evaluate(plan)
    if not (result["sample_pass"] and result["repair_pass"]):
        raise SystemExit(json.dumps({"status": "fail", **result}, indent=2))
    required, by_id = sample_requirements()
    report = {
        "scope_id": plan["scope_id"],
        "standard": load_json("evaluation_scope.json")["standard"],
        "sample": [
            {"id": page_id, "path": by_id[page_id]["path"]}
            for page_id in sorted(required)
        ],
        "status": "sample_repairs_pass",
        "checks": {**result["sample"], **result["repairs"]},
        "boundary": "offline sample evidence; no live-site conformance claim",
    }
    (ROOT / "conformance_report.json").write_text(json.dumps(report, indent=2) + "\n")
    repaired = [
        "site/components/nav.html",
        "site/catalog.html",
        "site/checkout.html",
        "site/checkout-error.html",
        "site/styles/theme.css",
    ]
    receipt = {
        "tool": "a11yctl/1",
        "status": "pass",
        "scope_id": plan["scope_id"],
        "plan_sha256": sha256(ROOT / "sample_plan.json"),
        "report_sha256": sha256(ROOT / "conformance_report.json"),
        "repaired_file_sha256": {name: sha256(ROOT / name) for name in repaired},
    }
    (ROOT / "repair_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": "pass", "sample_count": len(required), "repair_checks": len(result["repairs"])}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["inventory", "scan", "certify", "verify"])
    parser.add_argument("plan", nargs="?")
    args = parser.parse_args()
    if args.command == "inventory":
        print(json.dumps({"scope": load_json("evaluation_scope.json"), "inventory": load_json("page_inventory.json")}, indent=2))
        return
    plan_name = args.plan or "sample_plan.json"
    plan = load_json(plan_name)
    if args.command == "scan":
        result = evaluate(plan)
        print(json.dumps({"status": "pass" if result["sample_pass"] and result["repair_pass"] else "fail", **result}, indent=2))
        raise SystemExit(0 if result["sample_pass"] and result["repair_pass"] else 1)
    if args.command == "certify":
        certify(plan)
        return
    report = load_json("conformance_report.json")
    receipt = load_json("repair_receipt.json")
    result = evaluate(plan)
    ok = (
        result["sample_pass"]
        and result["repair_pass"]
        and report.get("status") == "sample_repairs_pass"
        and receipt.get("plan_sha256") == sha256(ROOT / plan_name)
        and receipt.get("report_sha256") == sha256(ROOT / "conformance_report.json")
        and all(receipt.get("repaired_file_sha256", {}).get(name) == sha256(ROOT / name) for name in receipt.get("repaired_file_sha256", {}))
        and len(receipt.get("repaired_file_sha256", {})) == 5
    )
    print(json.dumps({"status": "pass" if ok else "fail"}))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
