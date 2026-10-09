from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from task_environment_runtime import (  # noqa: E402
    BUILDER_ID,
    SUPPORTED_ABI,
    TaskEnvironmentBuilder,
    TaskEnvironmentError,
    _validate_combined_image,
    load_task_environment,
    run_task_environment_prepare,
    validate_overlay_dockerfile,
)


BASE_ID = "sha256:" + "1" * 64
FINAL_ID = "sha256:" + "2" * 64
ENV_SHA = "0" * 64


def base_config(*, image_id: str = BASE_ID) -> dict:
    return {
        "Id": image_id,
        "Config": {
            "Entrypoint": ["/usr/local/bin/harness"],
            "Cmd": ["run"],
            "User": "1000:1000",
            "WorkingDir": "/workspace",
            "Labels": {},
        },
    }


def shared_metadata(**overrides: object) -> dict:
    environment = {
        "schema_version": 1,
        "mode": "shared",
        "abi": SUPPORTED_ABI,
        "required_tools": {"python3": "3.12"},
        "services": [],
    }
    environment.update(overrides)
    return {"environment": environment}


def make_task(tmp_path: Path) -> Path:
    task = tmp_path / "001-example"
    (task / "environment").mkdir(parents=True)
    return task


def test_experimental_mode_requires_explicit_reviewed_environment(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    with pytest.raises(TaskEnvironmentError, match="explicit environment mapping"):
        load_task_environment(task, {})


def test_shared_without_declared_files_does_not_require_empty_directory(
    tmp_path: Path,
) -> None:
    task = tmp_path / "001-example"
    task.mkdir()
    spec = load_task_environment(task, shared_metadata())
    assert not spec.environment_dir.exists()
    assert spec.source_files == ()


def test_shared_hash_tracks_hook(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    hook = task / "environment/hooks.py"
    hook.write_text("VALUE = 1\n", encoding="utf-8")
    metadata = shared_metadata()
    metadata["hooks_module"] = "environment/hooks.py"
    first = load_task_environment(task, metadata)
    hook.write_text("VALUE = 2\n", encoding="utf-8")
    second = load_task_environment(task, metadata)
    assert second.sha256 != first.sha256
    assert second.source_files == ("hooks.py",)


def test_shared_rejects_undeclared_legacy_dockerfile(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    (task / "environment/Dockerfile").write_text(
        "FROM python:3.10\n",
        encoding="utf-8",
    )
    with pytest.raises(TaskEnvironmentError, match="undeclared environment/Dockerfile"):
        load_task_environment(task, shared_metadata())

def test_shared_accepts_todo_style_paths_and_hashes_explicit_inputs(
    tmp_path: Path,
) -> None:
    task = make_task(tmp_path)
    lock = task / "environment/requirements.lock"
    verifier = task / "environment/verify_environment.py"
    grader_verifier = task / "environment/verify_grader_environment.py"
    lock.write_text("package==1.0\n", encoding="utf-8")
    verifier.write_text("raise SystemExit(0)\n", encoding="utf-8")
    grader_verifier.write_text("raise SystemExit(0)\n", encoding="utf-8")
    metadata = shared_metadata(
        verifier="environment/verify_environment.py",
        inputs=["environment/requirements.lock"],
        grader={"verifier": "environment/verify_grader_environment.py"},
    )

    first = load_task_environment(task, metadata)
    assert first.verifier == "verify_environment.py"
    assert dict(first.grader) == {"verifier": "verify_grader_environment.py"}
    assert first.inputs == ("requirements.lock",)
    assert set(first.source_files) == {
        "requirements.lock",
        "verify_environment.py",
        "verify_grader_environment.py",
    }

    lock.write_text("package==1.1\n", encoding="utf-8")
    second = load_task_environment(task, metadata)
    assert second.sha256 != first.sha256


def test_prepare_is_hashed_and_runs_in_resolved_agent_image(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    prepare = task / "environment/prepare.py"
    prepare.write_text("print('prepared')\\n", encoding="utf-8")
    spec = load_task_environment(task, shared_metadata(prepare="environment/prepare.py"))
    assert spec.prepare == "prepare.py"
    assert spec.source_files == ("prepare.py",)

    resolved = TaskEnvironmentBuilder(
        docker_fn=lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(base_config()),
            stderr="",
        )
    ).resolve(spec=spec, harness_image="harness:test", grader_image="grader:test")
    calls: list[tuple[str, ...]] = []

    def fake_docker(*args: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="prepared\\n", stderr="")

    workspace = tmp_path / "workspace"
    runtime = tmp_path / "runtime"
    workspace.mkdir()
    runtime.mkdir()
    report = run_task_environment_prepare(
        spec=spec, resolved=resolved, workspace=workspace, runtime=runtime, docker_fn=fake_docker
    )
    assert report["status"] == "pass"
    assert "harness:test" in calls[0]
    assert "--network" in calls[0] and "none" in calls[0]
    assert any("dst=/workspace" in value for value in calls[0])


def test_shared_rejects_hidden_evaluator_input_path(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    hidden = task / "environment/tests"
    hidden.mkdir()
    (hidden / "oracle.py").write_text("ANSWER = 42\n", encoding="utf-8")
    with pytest.raises(TaskEnvironmentError, match="hidden-evaluation"):
        load_task_environment(task, shared_metadata())


def test_overlay_hashes_only_environment_context(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    (task / "tests").mkdir()
    (task / "tests/answer.txt").write_text("secret", encoding="utf-8")
    (task / "environment/Dockerfile").write_text(
        "ARG HARNESS_BASE\n"
        "FROM ${HARNESS_BASE}\n"
        "USER 1000:1000\n"
        "WORKDIR /workspace\n",
        encoding="utf-8",
    )
    (task / "environment/verify_environment.py").write_text(
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    metadata = shared_metadata(
        mode="overlay",
        dockerfile="Dockerfile",
        verifier="verify_environment.py",
    )
    spec = load_task_environment(task, metadata)
    validate_overlay_dockerfile(spec)
    assert set(spec.source_files) == {"Dockerfile", "verify_environment.py"}
    before = spec.sha256
    (task / "tests/answer.txt").write_text("different secret", encoding="utf-8")
    assert load_task_environment(task, metadata).sha256 == before


def test_overlay_rejects_entrypoint_replacement(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    (task / "environment/Dockerfile").write_text(
        "ARG HARNESS_BASE\n"
        "FROM ${HARNESS_BASE}\n"
        'ENTRYPOINT ["bash"]\n',
        encoding="utf-8",
    )
    (task / "environment/verify_environment.py").write_text(
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    spec = load_task_environment(
        task,
        shared_metadata(
            mode="overlay",
            dockerfile="Dockerfile",
            verifier="verify_environment.py",
        ),
    )
    with pytest.raises(TaskEnvironmentError, match="runtime contract"):
        validate_overlay_dockerfile(spec)


def test_service_images_must_be_digest_pinned(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    metadata = shared_metadata(
        services=[{"name": "db", "image": "postgres:16"}],
    )
    with pytest.raises(TaskEnvironmentError, match="pinned by sha256"):
        load_task_environment(task, metadata)


def test_combined_image_must_preserve_harness_contract() -> None:
    base = base_config()
    final = base_config(image_id=FINAL_ID)
    final["Config"]["Labels"] = {
        "org.harnessbench.task-environment-sha256": ENV_SHA,
        "org.harnessbench.environment-builder-id": BUILDER_ID,
        "org.harnessbench.environment-base-image-id": BASE_ID,
        "org.harnessbench.environment-abi": SUPPORTED_ABI,
    }
    _validate_combined_image(
        base=base,
        final=final,
        expected_labels=final["Config"]["Labels"],
    )
    final["Config"]["Entrypoint"] = ["bash"]
    with pytest.raises(TaskEnvironmentError, match="Entrypoint"):
        _validate_combined_image(
            base=base,
            final=final,
            expected_labels=final["Config"]["Labels"],
        )


def test_shared_resolution_records_both_immutable_bases(tmp_path: Path) -> None:
    task = make_task(tmp_path)
    spec = load_task_environment(task, shared_metadata())
    grader_id = "sha256:" + "3" * 64
    images = {
        "harness:test": base_config(),
        "grader:test": base_config(image_id=grader_id),
    }
    calls: list[tuple[tuple[str, ...], dict]] = []

    def fake_docker(*args: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        assert args[:2] == ("image", "inspect")
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(images[args[2]]),
            stderr="",
        )

    resolved = TaskEnvironmentBuilder(docker_fn=fake_docker).resolve(
        spec=spec,
        harness_image="harness:test",
        grader_image="grader:test",
    )
    assert resolved.combined_image_id == BASE_ID
    assert resolved.task_grader_image_id == grader_id
    assert resolved.verifier["agent"]["status"] == "not_required"
    assert resolved.verifier["grader"]["status"] == "not_required"
    assert len(calls) == 3
