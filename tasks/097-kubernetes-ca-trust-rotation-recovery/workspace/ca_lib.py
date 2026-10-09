from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUTS = (
    "evidence/ca_inventory.json",
    "evidence/component_inventory.json",
    "evidence/handshake_matrix.json",
    "policy/rotation_policy.json",
)


def load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write_json(relative: str, value: object) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_digests() -> dict[str, str]:
    return {relative: file_sha(ROOT / relative) for relative in INPUTS}


def read_events() -> list[dict]:
    rows = []
    for line in (ROOT / "state/rotation_events.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("event row must be an object")
            rows.append(value)
    return rows


def append_event(value: dict) -> dict:
    rows = read_events()
    event = {"seq": len(rows) + 1, **value}
    with (ROOT / "state/rotation_events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return event


def file_record(path: str) -> dict | None:
    ca = load("evidence/ca_inventory.json")
    return next((row for row in ca.get("files", []) if row.get("path") == path), None)


def controller_errors(state: dict, overlap: bool) -> list[str]:
    policy = load("policy/rotation_policy.json")
    controller = state.get("controller_manager", {})
    errors = []
    root = file_record(str(controller.get("root_ca_file", "")))
    client = file_record(str(controller.get("client_ca_file", "")))
    signing = file_record(str(controller.get("cluster_signing_cert_file", "")))
    key = file_record(str(controller.get("cluster_signing_key_file", "")))
    expected_root_kind = policy["file_roles"]["root_ca_file"][
        "during_overlap" if overlap else "after_retirement"
    ]
    if not root or root.get("kind") != expected_root_kind:
        errors.append("root_ca_file_has_wrong_role")
    if overlap and (not root or set(root.get("contains", [])) != {"OLD-CA", "NEW-CA"}):
        errors.append("root_ca_file_lacks_dual_bundle")
    if not overlap and (not root or root.get("contains") != ["NEW-CA"]):
        errors.append("root_ca_file_is_not_new_only")
    for name, record in (("client_ca_file", client), ("cluster_signing_cert_file", signing)):
        if not record or record.get("kind") != "single_ca_certificate" or record.get("contains") != ["NEW-CA"]:
            errors.append(f"{name}_must_be_single_new_ca")
    if not key or key.get("kind") != "private_key" or key.get("for_ca") != "NEW-CA":
        errors.append("cluster_signing_key_file_must_match_new_ca")
    return errors


def state_maps(state: dict) -> tuple[dict[str, str], dict[str, str]]:
    clients = {str(row["client_id"]): str(row["trust"]) for row in state.get("clients", [])}
    servers = {str(row["server_id"]): str(row["signer"]) for row in state.get("servers", [])}
    return clients, servers


def probe_rows(state: dict, mode: str) -> list[dict]:
    inventory = load("evidence/component_inventory.json")
    matrix = load("evidence/handshake_matrix.json")
    clients, servers = state_maps(state)
    rules = {
        (str(row["client_trust"]), str(row["server_signer"])): str(row["result"])
        for row in matrix.get("rules", [])
    }
    expected_trust = "dual" if mode == "dual" else "new_only"
    rows = []
    for pair in inventory.get("required_handshakes", []):
        client_id = str(pair["client"])
        server_id = str(pair["server"])
        trust = clients.get(client_id, "missing")
        signer = servers.get(server_id, "missing")
        compatibility = rules.get((trust, signer), "fail_unknown_identity")
        passed = trust == expected_trust and compatibility == "pass"
        rows.append(
            {
                "client": client_id,
                "server": server_id,
                "client_trust": trust,
                "server_signer": signer,
                "result": "pass" if passed else compatibility,
            }
        )
    return sorted(rows, key=lambda row: (row["client"], row["server"]))


def probe_document(state: dict, mode: str) -> dict:
    rows = probe_rows(state, mode)
    return {
        "tool": "cactl/1",
        "cluster_id": state.get("cluster_id"),
        "policy_version": state.get("policy_version"),
        "mode": mode,
        "required_pair_count": len(rows),
        "pairs": rows,
        "status": "pass" if rows and all(row["result"] == "pass" for row in rows) else "fail",
        "input_sha256": input_digests(),
    }


def dual_probe_fingerprint(document: dict) -> str:
    return canonical_sha(document)
