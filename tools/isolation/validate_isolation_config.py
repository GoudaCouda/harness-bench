from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VARIABLE_DIGEST = re.compile(r"@\$\{[A-Z][A-Z0-9_]*_DIGEST\}$")
LITERAL_DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def _mapping(value: Any, path: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{path} must be a mapping")
        return {}
    return value


def _require(
    mapping: dict[str, Any], key: str, expected: Any, path: str, errors: list[str]
) -> None:
    actual = mapping.get(key)
    if actual != expected:
        errors.append(f"{path}.{key} must be {expected!r}, got {actual!r}")


def _validate_image(
    image: Any, path: str, allowed_registries: list[str], errors: list[str]
) -> None:
    if not isinstance(image, str) or not image.strip():
        errors.append(f"{path} must be a non-empty image reference")
        return
    value = image.strip()
    if not (LITERAL_DIGEST.search(value) or VARIABLE_DIGEST.search(value)):
        errors.append(
            f"{path} must be pinned with @sha256:<64 hex> or @${{..._DIGEST}}"
        )
    registry_ok = any(
        value == registry or value.startswith(registry.rstrip("/") + "/")
        for registry in allowed_registries
    )
    if not registry_ok:
        errors.append(f"{path} registry is not allowlisted: {value!r}")


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    runtime = _mapping(data.get("runtime"), "runtime", errors)
    image_policy = _mapping(data.get("image_policy"), "image_policy", errors)
    container = _mapping(data.get("container_policy"), "container_policy", errors)
    mounts = _mapping(data.get("mount_policy"), "mount_policy", errors)
    network = _mapping(data.get("network_policy"), "network_policy", errors)
    secrets = _mapping(data.get("secret_policy"), "secret_policy", errors)
    grader = _mapping(data.get("grader"), "grader", errors)
    cleanup = _mapping(data.get("cleanup"), "cleanup", errors)

    _require(runtime, "rootless_required", True, "runtime", errors)
    if runtime.get("engine") not in {"podman", "docker"}:
        errors.append("runtime.engine must be 'podman' or 'docker'")
    if runtime.get("minimum_isolation_level") not in {"L1", "L2", "L3"}:
        errors.append("runtime.minimum_isolation_level must be L1, L2, or L3")

    _require(image_policy, "require_digest", True, "image_policy", errors)
    _require(image_policy, "allow_mutable_tags", False, "image_policy", errors)
    allowed_registries = image_policy.get("allowed_registries")
    if not isinstance(allowed_registries, list) or not all(
        isinstance(item, str) and item.strip() for item in allowed_registries
    ):
        errors.append("image_policy.allowed_registries must be a non-empty string list")
        allowed_registries = []

    for key, expected in {
        "privileged": False,
        "host_network": False,
        "host_pid": False,
        "host_ipc": False,
        "docker_socket_mount": False,
        "rootfs_read_only": True,
        "no_new_privileges": True,
        "run_as_non_root": True,
    }.items():
        _require(container, key, expected, "container_policy", errors)
    if container.get("cap_drop") != ["ALL"]:
        errors.append("container_policy.cap_drop must be exactly ['ALL']")
    if container.get("allow_devices") not in ([], None):
        errors.append("container_policy.allow_devices must be empty")
    if container.get("allow_host_ports") not in ([], None):
        errors.append("container_policy.allow_host_ports must be empty")
    for key in ("pids_limit", "memory_mb", "cpu_cores", "tmpfs_mb"):
        value = container.get(key)
        if not isinstance(value, (int, float)) or value <= 0:
            errors.append(f"container_policy.{key} must be positive")

    for key in (
        "allow_repo_mount",
        "allow_home_mount",
        "allow_absolute_host_bind",
    ):
        _require(mounts, key, False, "mount_policy", errors)
    targets = mounts.get("allowed_container_targets")
    if not isinstance(targets, list) or "/workspace" not in targets:
        errors.append("mount_policy.allowed_container_targets must include /workspace")
    if isinstance(targets, list):
        for target in targets:
            if not isinstance(target, str) or not target.startswith("/"):
                errors.append(
                    "mount_policy.allowed_container_targets entries must be absolute container paths"
                )

    for key, expected in {
        "direct_egress": False,
        "internal_network_per_run": True,
        "publish_host_ports": False,
        "block_private_ranges": True,
        "block_cloud_metadata": True,
        "allowed_task_services_only": True,
    }.items():
        _require(network, key, expected, "network_policy", errors)

    _require(secrets, "provider_credentials", "gateway_only", "secret_policy", errors)
    _require(
        secrets,
        "expose_provider_key_to_harness",
        False,
        "secret_policy",
        errors,
    )
    _require(secrets, "use_ephemeral_run_token", True, "secret_policy", errors)
    _require(secrets, "redact_authorization_headers", True, "secret_policy", errors)
    _require(secrets, "persist_raw_secrets", False, "secret_policy", errors)

    harnesses = _mapping(data.get("harnesses"), "harnesses", errors)
    if not harnesses:
        errors.append("harnesses must contain at least one harness")
    for harness_id, raw in harnesses.items():
        harness = _mapping(raw, f"harnesses.{harness_id}", errors)
        _validate_image(
            harness.get("image"),
            f"harnesses.{harness_id}.image",
            allowed_registries,
            errors,
        )
        _require(
            harness,
            "direct_egress",
            False,
            f"harnesses.{harness_id}",
            errors,
        )
        _require(
            harness,
            "provider_credentials",
            False,
            f"harnesses.{harness_id}",
            errors,
        )
        user = str(harness.get("user", "")).strip()
        if not user or user.startswith("0:") or user == "0":
            errors.append(f"harnesses.{harness_id}.user must be non-root")

    _validate_image(grader.get("image"), "grader.image", allowed_registries, errors)
    _require(grader, "network", "none", "grader", errors)
    _require(grader, "workspace_read_only", True, "grader", errors)
    _require(grader, "hidden_oracle_read_only", True, "grader", errors)
    _require(grader, "rootfs_read_only", True, "grader", errors)
    if grader.get("cap_drop") != ["ALL"]:
        errors.append("grader.cap_drop must be exactly ['ALL']")

    for key in (
        "always",
        "remove_containers",
        "remove_networks",
        "remove_ephemeral_volumes",
        "revoke_run_tokens",
        "verify_no_resources_remain",
    ):
        _require(cleanup, key, True, "cleanup", errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail-closed validation for Harness-Bench isolation policy."
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=str(PROJECT_ROOT / "docker" / "isolation.example.yaml"),
    )
    args = parser.parse_args()
    path = Path(args.config).expanduser().resolve()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        print(f"ERROR {path}: top-level YAML value must be a mapping")
        return 1
    errors = validate(data)
    print(f"config={path}")
    print(f"errors={len(errors)}")
    for error in errors:
        print(f"ERROR {error}")
    if errors:
        return 1
    print("isolation_policy=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
