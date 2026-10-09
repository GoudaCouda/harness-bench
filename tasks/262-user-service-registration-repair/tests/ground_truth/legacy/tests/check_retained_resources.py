from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check retained exact case_08 resources")
    parser.add_argument("--sandbox-plan", required=True, type=Path)
    return parser.parse_args()


def docker(args: list[str]) -> str:
    completed = subprocess.run(
        ["docker", *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"docker_{args[0]}_failed")
    return completed.stdout


def main() -> int:
    args = parse_args()
    plan = json.loads(args.sandbox_plan.resolve(strict=True).read_text(encoding="utf-8"))
    image_values = json.loads(docker(["image", "inspect", plan["image_id"]]))
    image = image_values[0]
    image_labels = image.get("Config", {}).get("Labels") or {}
    image_ok = (
        image.get("Id") == plan["image_id"]
        and image_labels.get("agent_sft.sandbox_contract_sha256")
        == plan["sandbox_contract_sha256"]
    )
    attempts: list[dict[str, Any]] = []
    for entry in plan["attempts"]:
        container_id = str(entry["container_id"])
        values = json.loads(docker(["inspect", container_id]))
        value = values[0]
        config = value.get("Config", {})
        host = value.get("HostConfig", {})
        labels = config.get("Labels") or {}
        mounts = value.get("Mounts") or []
        top = docker(["top", container_id, "-eo", "pid,args"])
        commands = [
            line.split(maxsplit=1)[1]
            for line in top.splitlines()[1:]
            if len(line.split(maxsplit=1)) == 2
        ]
        scratch = docker(
            [
                "exec",
                container_id,
                "python3",
                "-c",
                (
                    "from pathlib import Path; "
                    "print(len(list(Path('/scratch').iterdir())))"
                ),
            ]
        ).strip()
        checks = {
            "exact_id": value.get("Id") == container_id,
            "exact_name": value.get("Name") == f"/{entry['name']}",
            "running": value.get("State", {}).get("Status") == "running",
            "image": value.get("Image") == plan["image_id"],
            "contract_label": labels.get("agent_sft.sandbox_contract_sha256")
            == plan["sandbox_contract_sha256"],
            "attempt_label": labels.get("agent_sft.attempt_id")
            == entry["attempt_id"],
            "run_label": labels.get("agent_sft.run_id") == plan["run_id"],
            "network_none": host.get("NetworkMode") == "none",
            "no_ports": not (host.get("PortBindings") or {})
            and not (config.get("ExposedPorts") or {}),
            "exact_mount": len(mounts) == 1
            and mounts[0].get("Source") == entry["runtime_workspace"]
            and mounts[0].get("Destination") == "/workspace",
            "only_idle_process": commands
            == ["python3 /opt/case08-runtime/idle.py"],
            "scratch_empty": scratch == "0",
        }
        attempts.append(
            {
                "attempt_id": entry["attempt_id"],
                "container_id": container_id,
                "checks": checks,
                "valid": all(checks.values()),
            }
        )
    valid = image_ok and all(item["valid"] for item in attempts)
    print(
        json.dumps(
            {
                "schema_version": "case08_retained_resource_check_v1",
                "valid": valid,
                "image_id": plan["image_id"],
                "image_contract_label_valid": image_ok,
                "attempt_count": len(attempts),
                "attempts": attempts,
            },
            sort_keys=True,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
