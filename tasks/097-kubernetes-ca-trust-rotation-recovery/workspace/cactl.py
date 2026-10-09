#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from ca_lib import (
    ROOT,
    append_event,
    canonical_sha,
    controller_errors,
    dual_probe_fingerprint,
    file_sha,
    load,
    probe_document,
    read_events,
    state_maps,
    write_json,
)


STATE = "state/rotation_state.json"
EVENTS = "state/rotation_events.jsonl"


def save(state: dict) -> None:
    write_json(STATE, state)


def fail(*errors: str) -> int:
    print(json.dumps({"status": "rejected", "errors": list(errors)}, indent=2))
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Protected synthetic CA-rotation controller")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("history")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--component", required=True)
    repair = sub.add_parser("repair-controller")
    repair.add_argument("--root-ca-file", required=True)
    repair.add_argument("--client-ca-file", required=True)
    repair.add_argument("--signing-cert-file", required=True)
    repair.add_argument("--signing-key-file", required=True)
    refresh = sub.add_parser("refresh-client")
    refresh.add_argument("--client", required=True)
    refresh.add_argument("--trust", required=True, choices=("dual", "new_only"))
    rotate = sub.add_parser("rotate-server")
    rotate.add_argument("--server", required=True)
    rotate.add_argument("--signer", required=True, choices=("OLD-CA", "NEW-CA"))
    verify = sub.add_parser("verify")
    verify.add_argument("--mode", required=True, choices=("dual", "new-only"))
    sub.add_parser("retire-old")
    args = parser.parse_args()
    state = load(STATE)
    inventory = load("evidence/component_inventory.json")

    if args.command == "status":
        clients, servers = state_maps(state)
        result = {
            "cluster_id": state.get("cluster_id"),
            "phase": state.get("phase"),
            "controller_status": state.get("controller_manager", {}).get("status"),
            "controller_role_errors": controller_errors(state, bool(state.get("old_anchor_present"))),
            "clients_without_new_trust": sorted(name for name, trust in clients.items() if trust == "old_only"),
            "old_signed_servers": sorted(name for name, signer in servers.items() if signer == "OLD-CA"),
            "old_anchor_present": state.get("old_anchor_present"),
            "dual_probe_sha256": state.get("dual_probe_sha256"),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "history":
        print(json.dumps({"events": read_events()}, indent=2, sort_keys=True))
        return 0
    if args.command == "inspect":
        clients, servers = state_maps(state)
        if args.component == "kube-controller-manager":
            result = {"component": args.component, "configuration": state.get("controller_manager"), "role_errors": controller_errors(state, bool(state.get("old_anchor_present")))}
        elif args.component in clients:
            pairs = [row for row in inventory["required_handshakes"] if row["client"] == args.component]
            result = {"component": args.component, "kind": "client", "trust": clients[args.component], "required_connections": pairs}
        elif args.component in servers:
            pairs = [row for row in inventory["required_handshakes"] if row["server"] == args.component]
            result = {"component": args.component, "kind": "server", "signer": servers[args.component], "required_connections": pairs}
        else:
            return fail(f"unknown component: {args.component}")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "repair-controller":
        if state.get("old_anchor_present") is not True:
            return fail("controller overlap repair is no longer legal after retirement")
        proposed = {
            "status": "healthy",
            "root_ca_file": args.root_ca_file,
            "client_ca_file": args.client_ca_file,
            "cluster_signing_cert_file": args.signing_cert_file,
            "cluster_signing_key_file": args.signing_key_file,
        }
        trial = dict(state)
        trial["controller_manager"] = proposed
        errors = controller_errors(trial, True)
        if errors:
            return fail(*errors)
        if state.get("controller_manager") != proposed:
            state["controller_manager"] = proposed
            save(state)
            append_event({"event": "controller_ca_roles_repaired", "root_ca_file": args.root_ca_file, "client_ca_file": args.client_ca_file, "cluster_signing_cert_file": args.signing_cert_file, "cluster_signing_key_file": args.signing_key_file})
        print(json.dumps({"status": "pass", "controller_manager": proposed}, indent=2, sort_keys=True))
        return 0
    if args.command == "refresh-client":
        if state.get("old_anchor_present") is not True or args.trust != "dual":
            return fail("clients may move only to dual trust before protected retirement")
        rows = state.get("clients", [])
        row = next((item for item in rows if item.get("client_id") == args.client), None)
        if row is None:
            return fail(f"unknown client: {args.client}")
        if row.get("trust") == "new_only":
            return fail("client trust rollback is forbidden")
        if row.get("trust") != "dual":
            before = row.get("trust")
            row["trust"] = "dual"
            save(state)
            append_event({"event": "client_trust_refreshed", "client_id": args.client, "from": before, "to": "dual"})
        print(json.dumps({"status": "pass", "client_id": args.client, "trust": "dual"}, indent=2))
        return 0
    if args.command == "rotate-server":
        rows = state.get("servers", [])
        row = next((item for item in rows if item.get("server_id") == args.server), None)
        if row is None:
            return fail(f"unknown server: {args.server}")
        before = row.get("signer")
        if before == "NEW-CA" and args.signer == "OLD-CA":
            return fail("server signer rollback is forbidden")
        if args.signer != "NEW-CA":
            return fail("the active rotation target is NEW-CA")
        if before != "NEW-CA":
            row["signer"] = "NEW-CA"
            save(state)
            append_event({"event": "server_leaf_rotated", "server_id": args.server, "from": before, "to": "NEW-CA"})
        print(json.dumps({"status": "pass", "server_id": args.server, "signer": "NEW-CA"}, indent=2))
        return 0
    if args.command == "verify" and args.mode == "dual":
        clients, servers = state_maps(state)
        prerequisites = []
        if controller_errors(state, True) or state.get("controller_manager", {}).get("status") != "healthy":
            prerequisites.append("controller_manager_not_healthy")
        if any(value != "dual" for value in clients.values()):
            prerequisites.append("not_all_clients_have_dual_trust")
        if any(value != "NEW-CA" for value in servers.values()):
            prerequisites.append("not_all_servers_use_new_ca")
        if prerequisites:
            return fail(*prerequisites)
        document = probe_document(state, "dual")
        if document["status"] != "pass":
            return fail("dual handshake graph contains failures")
        fingerprint = dual_probe_fingerprint(document)
        write_json("work/dual_probe.json", document)
        if state.get("phase") != "dual_trust_verified" or state.get("dual_probe_sha256") != fingerprint:
            state["phase"] = "dual_trust_verified"
            state["dual_probe_sha256"] = fingerprint
            save(state)
            append_event({"event": "dual_trust_verification_passed", "pair_count": document["required_pair_count"], "probe_sha256": fingerprint})
        print(json.dumps({"status": "pass", "mode": "dual", "pair_count": document["required_pair_count"], "probe_sha256": fingerprint}, indent=2))
        return 0
    if args.command == "retire-old":
        if state.get("phase") != "dual_trust_verified":
            return fail("complete dual verification has not established the retirement gate")
        probe_path = ROOT / "work/dual_probe.json"
        if not probe_path.is_file():
            return fail("dual probe artifact is missing")
        try:
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return fail("dual probe artifact is malformed")
        if dual_probe_fingerprint(probe) != state.get("dual_probe_sha256") or probe.get("status") != "pass":
            return fail("dual probe artifact does not match protected state")
        clients, servers = state_maps(state)
        if controller_errors(state, True) or any(value != "dual" for value in clients.values()) or any(value != "NEW-CA" for value in servers.values()):
            return fail("retirement prerequisites no longer hold")
        for row in state["clients"]:
            row["trust"] = "new_only"
        state["controller_manager"]["root_ca_file"] = "pki/new-ca.crt"
        state["old_anchor_present"] = False
        state["phase"] = "old_anchor_retired"
        if controller_errors(state, False):
            return fail(*controller_errors(state, False))
        save(state)
        append_event({"event": "old_anchor_retired", "from": "dual", "to": "new_only", "dual_probe_sha256": state["dual_probe_sha256"]})
        print(json.dumps({"status": "pass", "phase": state["phase"], "old_anchor_present": False}, indent=2))
        return 0
    if args.command == "verify" and args.mode == "new-only":
        clients, servers = state_maps(state)
        if state.get("phase") not in {"old_anchor_retired", "new_ca_only_verified"}:
            return fail("old anchor has not been retired through the protected gate")
        errors = controller_errors(state, False)
        if state.get("old_anchor_present") is not False:
            errors.append("old_anchor_still_present")
        if any(value != "new_only" for value in clients.values()):
            errors.append("not_all_clients_are_new_only")
        if any(value != "NEW-CA" for value in servers.values()):
            errors.append("not_all_servers_use_new_ca")
        if errors:
            return fail(*errors)
        document = probe_document(state, "new_only")
        if document["status"] != "pass":
            return fail("new-only handshake graph contains failures")
        if state.get("phase") != "new_ca_only_verified":
            state["phase"] = "new_ca_only_verified"
            save(state)
            append_event({"event": "new_only_verification_passed", "pair_count": document["required_pair_count"]})
        document["final_state_sha256"] = canonical_sha(load(STATE))
        document["event_log_sha256"] = file_sha(ROOT / EVENTS)
        document["event_count"] = len(read_events())
        document["verification_fingerprint"] = canonical_sha(
            {key: value for key, value in document.items() if key != "verification_fingerprint"}
        )
        write_json("work/verification.json", document)
        print(json.dumps({"status": "pass", "mode": "new-only", "pair_count": document["required_pair_count"], "verification_fingerprint": document["verification_fingerprint"]}, indent=2))
        return 0
    return fail("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
