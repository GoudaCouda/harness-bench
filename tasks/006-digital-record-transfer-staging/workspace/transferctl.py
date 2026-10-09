#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "staged_transfer"


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def digest_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def digest_json(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def evidence() -> tuple[dict, dict, dict, dict, dict]:
    return (
        load("transfer_request.json"),
        load("inventory.json"),
        load("metadata.json"),
        load("qc_results.json"),
        load("checksum_register.json"),
    )


def candidate_index() -> dict[str, dict]:
    _, inventory, _, _, _ = evidence()
    return {row["path"]: row for row in inventory["candidates"]}


def metadata_index() -> dict[str, dict]:
    request, _, metadata, _, _ = evidence()
    required = request["required_metadata"]
    return {
        row["record_id"]: row
        for row in metadata["records"]
        if all(row.get(field) not in (None, "") for field in required)
    }


def acceptable(candidate: dict) -> bool:
    policy = load("format_policy.json")["categories"].get(candidate.get("category"), {})
    for rule in policy.get("accepted", []):
        observed = {
            **candidate,
            "extension": Path(str(candidate.get("path", ""))).suffix.casefold(),
        }
        if all(observed.get(key) == value for key, value in rule.items()):
            return True
    return False


def qc_status(path: str) -> str:
    _, _, _, qc, _ = evidence()
    rows = [row for row in qc["results"] if row.get("path") == path]
    return rows[0].get("status", "missing") if len(rows) == 1 else "missing"


def checksum_status(path: str) -> tuple[bool, str, str]:
    _, _, _, _, register = evidence()
    expected = str(register["digests"].get(path, ""))
    source = ROOT / path
    actual = digest_file(source) if source.is_file() else ""
    return bool(expected and actual == expected), expected, actual


def validate_plan(plan: dict) -> dict[str, object]:
    request, _, _, _, _ = evidence()
    candidates = candidate_index()
    metadata = metadata_index()
    selections = plan.get("selections", [])
    quarantine = plan.get("quarantine", [])
    selected_by_id = {
        row.get("record_id"): row
        for row in selections
        if isinstance(row, dict) and row.get("record_id")
    }
    quarantine_by_id = {
        row.get("record_id"): row
        for row in quarantine
        if isinstance(row, dict) and row.get("record_id")
    }
    by_record: dict[str, list[dict]] = {}
    for candidate in candidates.values():
        by_record.setdefault(str(candidate.get("record_id")), []).append(candidate)
    stageable: dict[str, list[str]] = {}
    quarantine_sources: dict[str, list[str]] = {}
    for record_id in request["required_record_ids"]:
        rows = by_record.get(record_id, [])
        stageable[record_id] = [
            row["path"]
            for row in rows
            if record_id in metadata
            and acceptable(row)
            and qc_status(row["path"]) == "pass"
            and checksum_status(row["path"])[0]
            and row.get("master") is True
        ]
        quarantine_sources[record_id] = [
            row["path"]
            for row in rows
            if record_id in metadata
            and acceptable(row)
            and qc_status(row["path"]) == "pass"
            and not checksum_status(row["path"])[0]
            and row.get("master") is True
        ]
    item_diagnostics = {}
    for record_id in request["required_record_ids"]:
        row = selected_by_id.get(record_id, {})
        path = str(row.get("source_path", ""))
        candidate = candidates.get(path, {})
        checksum_ok, _, _ = checksum_status(path) if path else (False, "", "")
        if len(stageable[record_id]) == 1:
            item_diagnostics[record_id] = {
                "selected_once": sum(
                    value.get("record_id") == record_id
                    for value in selections
                    if isinstance(value, dict)
                ) == 1,
                "unique_evidence_supported_source": path == stageable[record_id][0],
                "metadata_complete": record_id in metadata,
                "format_accepted": acceptable(candidate) if candidate else False,
                "qc_pass": qc_status(path) == "pass",
                "checksum_match": checksum_ok,
                "preservation_master": candidate.get("master") is True,
            }
        else:
            quarantine_row = quarantine_by_id.get(record_id, {})
            quarantine_path = str(quarantine_row.get("source_path", ""))
            item_diagnostics[record_id] = {
                "not_staged": record_id not in selected_by_id,
                "quarantined_once": sum(
                    value.get("record_id") == record_id
                    for value in quarantine
                    if isinstance(value, dict)
                ) == 1,
                "unique_unresolved_source": len(quarantine_sources[record_id]) == 1
                and quarantine_path == quarantine_sources[record_id][0],
                "reason": quarantine_row.get("reason") == "checksum_mismatch",
                "mismatch_confirmed": bool(quarantine_path)
                and not checksum_status(quarantine_path)[0],
            }
    stageable_ids = {
        record_id for record_id, paths in stageable.items() if len(paths) == 1
    }
    quarantined_ids = {
        record_id
        for record_id, paths in quarantine_sources.items()
        if not stageable[record_id] and len(paths) == 1
    }
    closed_set = (
        set(selected_by_id) == stageable_ids
        and set(quarantine_by_id) == quarantined_ids
        and stageable_ids | quarantined_ids == set(request["required_record_ids"])
        and len(selections) == len(stageable_ids)
        and len(quarantine) == len(quarantined_ids)
    )
    return {
        "transfer_id": plan.get("transfer_id") == request["transfer_id"],
        "closed_set": closed_set,
        "items": item_diagnostics,
        "all_items_pass": all(
            all(value is True for value in checks.values())
            for checks in item_diagnostics.values()
        ),
    }


def package_path(record_id: str, source_path: str) -> str:
    title = metadata_index()[record_id]["title"].casefold()
    stem = re.sub(r"[^a-z0-9]+", "_", title).strip("_")
    extension = Path(source_path).suffix.casefold()
    return f"records/{record_id}/{stem}{extension}"


def render(plan: dict) -> tuple[dict, dict, str]:
    request, _, _, _, _ = evidence()
    metadata = metadata_index()
    records = []
    checksum_lines = []
    for selection in sorted(plan["selections"], key=lambda row: row["record_id"]):
        record_id = selection["record_id"]
        source_path = selection["source_path"]
        target = package_path(record_id, source_path)
        actual = digest_file(ROOT / source_path)
        records.append(
            {
                **metadata[record_id],
                "package_path": target,
                "sha256": actual,
            }
        )
        checksum_lines.append(f"{actual}  {target}")
    manifest = {
        "transfer_id": request["transfer_id"],
        "record_group": request["record_group"],
        "series_id": request["series_id"],
        "schedule_item": request["schedule_item"],
        "inclusive_dates": request["inclusive_dates"],
        "state": "staged_not_submitted",
        "records": records,
    }
    quarantine = {
        "transfer_id": request["transfer_id"],
        "state": "requires_records_officer_review",
        "items": plan["quarantine"],
    }
    return manifest, quarantine, "\n".join(checksum_lines) + "\n"


def apply(plan: dict) -> None:
    diagnostics = validate_plan(plan)
    if not (
        diagnostics["transfer_id"]
        and diagnostics["closed_set"]
        and diagnostics["all_items_pass"]
    ):
        raise SystemExit(json.dumps({"status": "fail", "diagnostics": diagnostics}, indent=2))
    manifest, quarantine, checksums = render(plan)
    OUTPUT.mkdir(exist_ok=True)
    for row in manifest["records"]:
        source_path = next(
            item["source_path"]
            for item in plan["selections"]
            if item["record_id"] == row["record_id"]
        )
        target = OUTPUT / row["package_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source_path, target)
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUTPUT / "checksums.sha256").write_text(checksums)
    (ROOT / "quarantine.json").write_text(json.dumps(quarantine, indent=2) + "\n")
    receipt = {
        "tool": "transferctl/1",
        "status": "pass",
        "transfer_id": manifest["transfer_id"],
        "state": manifest["state"],
        "manifest_sha256": digest_json(manifest),
        "quarantine_sha256": digest_json(quarantine),
        "checksums_sha256": hashlib.sha256(checksums.encode()).hexdigest(),
        "checks": {
            "closed_record_set": True,
            "metadata_complete": True,
            "formats_accepted": True,
            "qc_passed": True,
            "checksums_matched": True,
            "unresolved_item_quarantined": True,
        },
    }
    (ROOT / "validation_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": "pass", "state": manifest["state"], "staged": 3, "quarantined": 1}))


def verify() -> None:
    plan = load("transfer_plan.json")
    manifest = load("staged_transfer/manifest.json")
    quarantine = load("quarantine.json")
    receipt = load("validation_receipt.json")
    checksums = (OUTPUT / "checksums.sha256").read_text()
    checks = []
    for row in manifest.get("records", []):
        path = OUTPUT / row.get("package_path", "")
        checks.append(path.is_file() and digest_file(path) == row.get("sha256"))
    expected_manifest, expected_quarantine, expected_checksums = render(plan)
    diagnostics = validate_plan(plan)
    ok = (
        diagnostics["transfer_id"]
        and diagnostics["closed_set"]
        and diagnostics["all_items_pass"]
        and manifest == expected_manifest
        and quarantine == expected_quarantine
        and checksums == expected_checksums
        and checks
        and all(checks)
        and receipt.get("manifest_sha256") == digest_json(manifest)
        and receipt.get("quarantine_sha256") == digest_json(quarantine)
        and receipt.get("checksums_sha256") == hashlib.sha256(checksums.encode()).hexdigest()
    )
    print(json.dumps({"status": "pass" if ok else "fail", "checks": len(checks)}))
    raise SystemExit(0 if ok else 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "preview", "apply", "verify"])
    parser.add_argument("plan", nargs="?")
    args = parser.parse_args()
    if args.command == "status":
        rows = []
        for path, candidate in candidate_index().items():
            match, expected, actual = checksum_status(path)
            rows.append({**candidate, "qc": qc_status(path), "format_accepted": acceptable(candidate), "checksum": "match" if match else "mismatch", "expected_sha256": expected, "actual_sha256": actual})
        print(json.dumps({"transfer": load("transfer_request.json"), "candidates": rows}, indent=2))
        return
    if args.command == "verify":
        verify()
        return
    if not args.plan:
        raise SystemExit("preview/apply requires a plan path")
    plan = load(args.plan)
    if args.command == "preview":
        diagnostics = validate_plan(plan)
        ok = diagnostics["transfer_id"] and diagnostics["closed_set"] and diagnostics["all_items_pass"]
        print(json.dumps({"status": "pass" if ok else "fail", "diagnostics": diagnostics}, indent=2))
        raise SystemExit(0 if ok else 1)
    apply(plan)


if __name__ == "__main__":
    main()
