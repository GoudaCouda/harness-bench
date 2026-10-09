from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from task_environment_runtime import (  # noqa: E402
    BUILDER_ID,
    SUPPORTED_ABI,
    ResolvedTaskEnvironment,
    load_task_environment,
)
from task_service_runtime import TrialServiceRuntime  # noqa: E402


def _completed(args: tuple[str, ...], *, stdout: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(
        args=args,
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def test_local_service_uses_private_network_volume_and_controller_snapshot(
    tmp_path: Path,
) -> None:
    task = tmp_path / "052-example"
    environment = task / "environment"
    environment.mkdir(parents=True)
    (environment / "service.py").write_text("print('service')\n", encoding="utf-8")
    metadata = {
        "environment": {
            "schema_version": 1,
            "mode": "shared",
            "abi": SUPPORTED_ABI,
            "required_tools": {"python3": "3.12"},
            "services": [
                {
                    "name": "appointment",
                    "script": "environment/service.py",
                    "port": 8080,
                    "health_path": "/healthz",
                    "state_file": "state.json",
                    "health_timeout_sec": 5,
                }
            ],
        }
    }
    spec = load_task_environment(task, metadata)
    assert spec.source_files == ("service.py",)

    resolved = ResolvedTaskEnvironment(
        task_environment_sha256=spec.sha256,
        environment_builder_id=BUILDER_ID,
        abi=SUPPORTED_ABI,
        mode="shared",
        harness_image_id="sha256:" + "1" * 64,
        combined_image="harness:test",
        combined_image_id="sha256:" + "1" * 64,
        task_grader_image="grader:test",
        task_grader_image_id="sha256:" + "2" * 64,
        verifier={},
        service_image_digests=("sha256:" + "1" * 64,),
    )
    calls: list[tuple[str, ...]] = []

    def fake_docker(*args: str, **kwargs: object):
        del kwargs
        calls.append(args)
        if args[:2] == ("inspect", "--format"):
            return _completed(args, stdout=json.dumps({"Running": True}))
        if args[:1] == ("exec",):
            script = args[-1]
            if "/service-state/state.json" in script:
                return _completed(
                    args,
                    stdout=json.dumps(
                        {"schema_version": 1, "instance_id": "hb052-test"}
                    )
                    + "\n",
                )
            return _completed(args)
        if args[:1] == ("logs",):
            return _completed(args, stdout="service log\n")
        return _completed(args, stdout="ok\n")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    runtime = TrialServiceRuntime(
        spec=spec,
        resolved=resolved,
        task_id="052-example",
        run_id="unit-test",
        token="abc12345",
        task_dir=task,
        workspace=workspace,
        artifact=artifact,
        labels=["--label", "org.harnessbench.benchmark=true"],
        docker_fn=fake_docker,
    )
    runtime.create_network()
    handle = runtime.launch_local(
        "appointment",
        arguments=[
            "--state-dir",
            "/service-state",
            "--bind",
            "0.0.0.0",
            "--port",
            "8080",
            "--base-path",
            "/appointment/capability",
            "--instance-id",
            "hb052-test",
        ],
        base_path="/appointment/capability",
    )

    assert handle.public_base == "http://appointment:8080/appointment/capability"
    assert json.loads(handle.private_state_path.read_text())["instance_id"] == "hb052-test"
    volume_init = next(
        call for call in calls
        if call[:2] == ("run", "--rm") and "CHOWN" in call
    )
    assert volume_init[-1] == "chmod 700 /service-state && chown 1000:1000 /service-state"
    launch = next(call for call in calls if call[:2] == ("run", "--detach"))
    assert "--no-healthcheck" in launch
    assert "--network-alias" in launch
    assert "appointment" in launch
    assert any(
        value.startswith("type=volume,src=hb-svc-state-")
        and value.endswith(",dst=/service-state")
        for value in launch
    )
    assert not any("dst=/service-state" in value and "type=bind" in value for value in launch)
    assert any(
        value.endswith("dst=/workspace,readonly") for value in launch
    )

    runtime.cleanup()
    report = runtime.report()
    assert report["active_containers"] == []
    assert report["network"] is None
    assert any(call[:3] == ("volume", "rm", "--force") for call in calls)
    assert any(call[:2] == ("network", "rm") for call in calls)
    assert (artifact / "services/appointment/service.log").read_text() == "service log\n"
