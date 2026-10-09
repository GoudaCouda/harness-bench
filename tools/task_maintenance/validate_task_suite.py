from __future__ import annotations

import argparse
import json
import re
import shlex
import stat
from pathlib import Path, PurePosixPath

import yaml

from common import (
    TASK_ROOTS,
    iter_task_yamls,
    oracle_definition,
    outcome_case_definition,
)
from deadline_policy import evaluate_deadline
from harnessbench.grading.deterministic_oracle import validate_oracle_spec
from harnessbench.grading.oracle_contract import (
    normalize_mutation_contract,
    normalize_required_artifacts,
)
from harnessbench.grading.semantic_judge import (
    SemanticJudgeError,
    validate_judge_config,
    validate_judge_request,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE_REGISTRY_TEXT = "\n".join(
    path.read_text(encoding="utf-8", errors="replace")
    for path in sorted((ROOT / "docs" / "task_sources").glob("*.md"))
)
REQUIRED_METADATA = {
    "domain",
    "difficulty",
    "capability_tags",
    "harness_demands",
    "stressors",
    "provenance",
}
LOCAL_PATH = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\)")
ALLOWED_DOMAINS = {
    "Software Engineering",
    "Data Analytics",
    "IT Operations",
    "Research",
    "Office Productivity",
    "Business Operations",
    "Personal Assistance",
    "Finance",
    "Compliance",
    "Customer Service",
    "Human Resources",
    "Education Administration",
    "Science and Laboratory Operations",
    "Energy and Utilities",
    "Media and Entertainment",
}
ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
ALLOWED_HARNESS_DEMANDS = {
    "context_management",
    "error_recovery",
    "evidence_grounding",
    "multi_step_execution",
    "output_contract",
    "safety_boundary",
    "state_management",
    "tool_selection",
    "verification_behavior",
}
REQUIRED_DESIGN_SECTIONS = (
    "## 1. Workflow identity",
    "## 2. Idea provenance",
    "## 3. Real-workflow justification",
    "## 4. Agent-visible inputs",
    "## 5. Hidden ground truth",
    "## 6. Expected workflow",
    "## 7. Harness demands",
    "## 8. Stressors and difficulty",
    "## 9. Oracle design",
    "## 10. Leakage, isolation, and safety review",
    "## 11. Pilot plan",
)
PUBLIC_EVIDENCE_REQUIREMENT_KEYS = (
    "required_reference_template",
    "required_reference_by_key",
    "required_reference_rule",
)
IDEA_PROVENANCE_SECTION = re.compile(
    r"^## 2\. Idea provenance\s*$"
    r"(?P<body>.*?)"
    r"(?=^## \d+\. |\Z)",
    re.MULTILINE | re.DOTALL,
)
FORMAL_AGENT_NAME = "agent"
FORMAL_AGENT_UID = "1000"
FORMAL_AGENT_GID = "1000"
FORMAL_AGENT_HOME = "/home/agent"


def validate_semantic_judge_record(
    task_dir: Path,
    metadata: dict,
    *,
    task_id: str | None = None,
) -> list[str]:
    """Validate the static, executable part of a task's semantic contract."""

    raw = metadata.get("semantic_judge")
    if raw is None:
        return []
    resolved_task_id = task_id or str(metadata.get("task_id") or task_dir.name)
    try:
        config = validate_judge_config(raw)
    except SemanticJudgeError as exc:
        return [f"{resolved_task_id}: invalid semantic_judge config: {exc}"]

    errors: list[str] = []

    def safe_file(field: str) -> Path | None:
        relative = PurePosixPath(config[field])
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(
                f"{resolved_task_id}: semantic_judge.{field} must stay inside the task"
            )
            return None
        path = task_dir.joinpath(*relative.parts)
        if not path.is_file() or path.is_symlink():
            errors.append(
                f"{resolved_task_id}: semantic_judge.{field} is missing or unsafe"
            )
            return None
        return path

    rubric_path = safe_file("rubric_file")
    builder_path = safe_file("input_builder")
    if builder_path is not None and builder_path.suffix != ".py":
        errors.append(
            f"{resolved_task_id}: semantic_judge.input_builder must be a Python file"
        )
    if rubric_path is None:
        return errors
    try:
        rubric = yaml.safe_load(rubric_path.read_text(encoding="utf-8"))
        validate_judge_request(
            {
                "schema_version": 1,
                "task_id": resolved_task_id,
                "score_role": config["score_role"],
                "rubric": rubric,
                "candidate": {},
                "case_map": config["case_map"],
            }
        )
    except (OSError, UnicodeError, yaml.YAMLError, SemanticJudgeError) as exc:
        errors.append(f"{resolved_task_id}: invalid semantic judge rubric: {exc}")
    return errors


def _docker_shell_commands(stage: str) -> list[list[str]]:
    """Return simple shell-form RUN command segments from one Docker stage.

    This is deliberately a strict static policy parser, not a general Dockerfile
    or POSIX-shell evaluator. Formal task images use plain ``RUN a && b`` setup
    commands so their identity and ownership contract remains reviewable.
    """

    folded = re.sub(r"\\\r?\n[ \t]*", " ", stage)
    commands: list[list[str]] = []
    for run in re.findall(r"(?im)^\s*RUN\s+(.+)$", folded):
        for segment in re.split(r"\s*(?:&&|;)\s*", run):
            try:
                tokens = shlex.split(segment, comments=True, posix=True)
            except ValueError:
                continue
            if tokens:
                commands.append(tokens)
    return commands


def _docker_option(tokens: list[str], *names: str) -> str | None:
    for index, token in enumerate(tokens):
        if token in names and index + 1 < len(tokens):
            return tokens[index + 1]
        for name in names:
            if name.startswith("--") and token.startswith(f"{name}="):
                return token.split("=", 1)[1]
    return None


def _docker_command_name(tokens: list[str]) -> str:
    return PurePosixPath(tokens[0]).name.casefold()


def validate_formal_environment_dockerfile(
    task_id: str,
    dockerfile_text: str,
) -> list[str]:
    """Enforce the named, fixed-identity formal task runtime contract.

    Numeric ``USER`` alone does not create a passwd entry or a usable home.
    The final stage must therefore create the common ``agent`` identity, set a
    writable home, and enter a work directory owned by that identity. Both
    Debian/Ubuntu ``groupadd``/``useradd`` and Alpine
    ``addgroup``/``adduser`` spellings are recognized.
    """

    errors: list[str] = []
    from_matches = list(
        re.finditer(
            r"(?im)^\s*FROM(?:\s+--platform=\S+)?\s+[^\s]+"
            r"(?:\s+AS\s+[^\s#]+)?[^\n]*$",
            dockerfile_text,
        )
    )
    final_stage = (
        dockerfile_text[from_matches[-1].start() :] if from_matches else dockerfile_text
    )
    commands = _docker_shell_commands(final_stage)

    group_created = any(
        _docker_command_name(tokens) in {"groupadd", "addgroup"}
        and _docker_option(tokens, "--gid", "-g") == FORMAL_AGENT_GID
        and tokens[-1] == FORMAL_AGENT_NAME
        for tokens in commands
    )
    if not group_created:
        errors.append(
            f"{task_id}: formal environment/Dockerfile final stage must create "
            f"group {FORMAL_AGENT_NAME!r} with fixed GID {FORMAL_AGENT_GID}"
        )

    user_created = False
    for tokens in commands:
        command = _docker_command_name(tokens)
        if command not in {"useradd", "adduser"} or tokens[-1] != FORMAL_AGENT_NAME:
            continue
        uid = _docker_option(tokens, "--uid", "-u")
        group = _docker_option(tokens, "--gid", "-g", "--ingroup", "-G")
        home = _docker_option(tokens, "--home-dir", "--home", "-h")
        explicit_home_creation = (
            command == "adduser"
            and "--no-create-home" not in tokens
            and "-H" not in tokens
            or "--create-home" in tokens
            or "-m" in tokens
        )
        if (
            uid == FORMAL_AGENT_UID
            and group in {FORMAL_AGENT_GID, FORMAL_AGENT_NAME}
            and home == FORMAL_AGENT_HOME
            and explicit_home_creation
        ):
            user_created = True
            break
    if not user_created:
        errors.append(
            f"{task_id}: formal environment/Dockerfile final stage must create "
            f"user {FORMAL_AGENT_NAME!r} with UID/GID "
            f"{FORMAL_AGENT_UID}:{FORMAL_AGENT_GID} and home {FORMAL_AGENT_HOME}"
        )

    folded_stage = re.sub(r"\\\r?\n[ \t]*", " ", final_stage)
    home: str | None = None
    for env_instruction in re.findall(r"(?im)^\s*ENV\s+(.+)$", folded_stage):
        try:
            tokens = shlex.split(env_instruction, comments=True, posix=True)
        except ValueError:
            continue
        if len(tokens) >= 2 and tokens[0] == "HOME":
            home = tokens[1]
        for token in tokens:
            if token.startswith("HOME="):
                home = token.split("=", 1)[1]
    if home != FORMAL_AGENT_HOME:
        errors.append(
            f"{task_id}: formal environment/Dockerfile final stage must set "
            f"HOME={FORMAL_AGENT_HOME}"
        )

    users = re.findall(r"(?im)^\s*USER\s+([^\s#]+)", final_stage)
    if not users or users[-1].casefold() != f"{FORMAL_AGENT_NAME}:{FORMAL_AGENT_NAME}":
        errors.append(
            f"{task_id}: formal environment/Dockerfile final USER must be "
            f"{FORMAL_AGENT_NAME}:{FORMAL_AGENT_NAME}"
        )

    workdirs = re.findall(r"(?im)^\s*WORKDIR\s+([^\s#]+)", final_stage)
    final_workdir = workdirs[-1].strip("'\"") if workdirs else ""
    workdir_owned = final_workdir == FORMAL_AGENT_HOME
    if final_workdir:
        for tokens in commands:
            command = _docker_command_name(tokens)
            if (
                command == "install"
                and "-d" in tokens
                and _docker_option(tokens, "--owner", "-o") == FORMAL_AGENT_NAME
                and _docker_option(tokens, "--group", "-g") == FORMAL_AGENT_NAME
                and final_workdir in tokens
            ):
                workdir_owned = True
                break
        if not workdir_owned:
            made = any(
                _docker_command_name(tokens) == "mkdir" and final_workdir in tokens
                for tokens in commands
            )
            owned = any(
                _docker_command_name(tokens) == "chown"
                and f"{FORMAL_AGENT_NAME}:{FORMAL_AGENT_NAME}" in tokens
                and final_workdir in tokens
                for tokens in commands
            )
            workdir_owned = made and owned
    if (
        not final_workdir
        or not PurePosixPath(final_workdir).is_absolute()
        or final_workdir == "/"
        or not workdir_owned
    ):
        errors.append(
            f"{task_id}: formal environment/Dockerfile final WORKDIR must be an "
            f"explicit writable directory owned by {FORMAL_AGENT_NAME}"
        )
    return errors


def formal_environment_directory_required(environment: object) -> bool:
    """Return whether a formal task must carry a tracked environment directory.

    A shared environment with no file-backed inputs intentionally inherits the
    common harness and grader images unchanged. Git cannot retain an empty
    directory, so requiring one would force meaningless placeholder files.
    """

    if not (
        isinstance(environment, dict)
        and environment.get("schema_version") == 1
        and environment.get("mode") == "shared"
    ):
        return True
    if environment.get("verifier") or environment.get("dockerfile"):
        return True
    if environment.get("inputs") or environment.get("services"):
        return True
    for role in ("agent", "grader"):
        if environment.get(role):
            return True
    return False


def _safe_task_file(task_dir: Path, raw_name: object) -> Path | None:
    """Resolve one task-root-relative maintainer file without accepting traversal."""
    name = str(raw_name or "").strip().replace("\\", "/")
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "." in path.parts:
        return None
    return task_dir.joinpath(*path.parts)


def validate_design_record(
    task_dir: Path,
    metadata: dict,
    *,
    expansion: bool,
) -> list[str]:
    """Validate the retained per-task design/provenance contract."""
    task_id = str(metadata.get("task_id") or task_dir.name)
    errors: list[str] = []
    raw_name = metadata.get("design_file", "design.md")
    if expansion and "design_file" not in metadata:
        errors.append(f"{task_id}: expansion task must declare design_file")
    design_path = _safe_task_file(task_dir, raw_name)
    if design_path is None:
        return [*errors, f"{task_id}: unsafe design_file {raw_name!r}"]
    if not design_path.is_file():
        return [*errors, f"{task_id}: missing design record {raw_name}"]

    text = design_path.read_text(encoding="utf-8", errors="replace")
    for section in REQUIRED_DESIGN_SECTIONS:
        if section not in text:
            errors.append(f"{task_id}: design record missing section {section!r}")
    provenance_match = IDEA_PROVENANCE_SECTION.search(text)
    if provenance_match is not None and not re.search(
        r"https?://",
        provenance_match.group("body"),
    ):
        errors.append(f"{task_id}: idea-provenance section has no source URL")
    if "- **Private user logs:**" not in text:
        errors.append(f"{task_id}: design record omits private-user-log statement")
    if expansion:
        if "- **Synthetic-data statement:**" not in text:
            errors.append(f"{task_id}: expansion design omits synthetic-data statement")
        provenance = metadata.get("provenance") or {}
        source_ids = provenance.get("source_ids") or []
        if not (
            isinstance(source_ids, list)
            and source_ids
            and all(isinstance(value, str) and value.strip() for value in source_ids)
        ):
            errors.append(f"{task_id}: expansion provenance requires source_ids")
    if LOCAL_PATH.search(text):
        errors.append(f"{task_id}: host-local absolute path in {design_path.name}")
    return errors


def validate_public_output_contract(task_dir: Path, task_id: str) -> list[str]:
    """Reject evidence scoring whose required baseline is grader-only.

    A list of allowed filenames and a reference grammar define representation,
    but they do not tell an agent which evidence is minimally required.  Every
    scored ``evidence_refs`` field therefore has to publish either a reusable
    template, an item-keyed baseline, or a deterministic derivation rule.
    """
    contract_path = task_dir / "workspace" / "output_contract.json"
    if not contract_path.is_file():
        return []
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except Exception:
        # The main JSON validation reports the parse error with its path.
        return []
    if not isinstance(contract, dict):
        return [f"{task_id}: output_contract.json must contain an object"]

    oracle_path = task_dir / "oracle_spec.json"
    try:
        oracle_spec = json.loads(oracle_path.read_text(encoding="utf-8"))
    except Exception:
        oracle_spec = {}

    def condition_leaves(condition: object) -> list[dict]:
        if not isinstance(condition, dict):
            return []
        leaves: list[dict] = []
        for combinator in ("all", "any"):
            children = condition.get(combinator)
            if isinstance(children, list):
                for child in children:
                    leaves.extend(condition_leaves(child))
        if isinstance(condition.get("not"), dict):
            leaves.extend(condition_leaves(condition["not"]))
        if "type" in condition:
            leaves.append(condition)
        return leaves

    oracle_leaves = [
        leaf
        for check in oracle_spec.get("checks", [])
        if isinstance(check, dict)
        for leaf in condition_leaves(check.get("condition"))
    ]
    shared_evidence = contract.get("evidence_reference_contract")
    shared_evidence = shared_evidence if isinstance(shared_evidence, dict) else {}
    errors: list[str] = []
    artifacts = contract.get("artifacts")
    if not isinstance(artifacts, dict):
        return errors

    for artifact_name, artifact in artifacts.items():
        if not isinstance(artifact, dict):
            continue
        fields = artifact.get("fields")
        if not isinstance(fields, dict):
            continue
        evidence = fields.get("evidence_refs")
        if not isinstance(evidence, dict):
            continue
        published = {
            key: evidence.get(
                key,
                artifact.get(key, shared_evidence.get(key)),
            )
            for key in PUBLIC_EVIDENCE_REQUIREMENT_KEYS
            if key in evidence or key in artifact or key in shared_evidence
        }
        nonempty = {
            key: value
            for key, value in published.items()
            if (
                isinstance(value, str)
                and value.strip()
                or isinstance(value, (list, dict))
                and bool(value)
            )
        }
        if not nonempty:
            errors.append(
                f"{task_id}: {artifact_name}.evidence_refs scores a hidden "
                "baseline; publish one of "
                f"{list(PUBLIC_EVIDENCE_REQUIREMENT_KEYS)}"
            )

    for artifact_name, artifact in artifacts.items():
        if not (
            isinstance(artifact, dict)
            and artifact.get("format") == "json_object"
            and isinstance(artifact.get("fields"), dict)
        ):
            continue
        artifact_path = artifact_name
        json_leaves = [
            leaf
            for leaf in oracle_leaves
            if leaf.get("type") == "json" and leaf.get("path") == artifact_path
        ]
        for field_name, field_contract in artifact["fields"].items():
            if not isinstance(field_contract, dict):
                continue
            collection = str(field_contract.get("collection") or "")
            if not collection.startswith("closed_"):
                continue
            pointer = f"/{field_name}"
            pointer_ops = {
                str(leaf.get("op") or "")
                for leaf in json_leaves
                if leaf.get("pointer", "") == pointer
            }
            root_ops = {
                str(leaf.get("op") or "")
                for leaf in json_leaves
                if leaf.get("pointer", "") == ""
            }
            if collection == "closed_ordered":
                strict = "equals" in pointer_ops or "equals" in root_ops
            else:
                strict = bool(
                    {
                        "equals",
                        "set_equals",
                        "contains_closed",
                        "contains_closed_zero_extended",
                    }
                    & pointer_ops
                    or {
                        "equals",
                        "contains_closed",
                        "contains_closed_zero_extended",
                    }
                    & root_ops
                )
            if not strict:
                rejected_items = (
                    "extra or reordered"
                    if collection == "closed_ordered"
                    else "extra or duplicate"
                )
                errors.append(
                    f"{task_id}: {artifact_name}.{field_name} is "
                    f"{collection} but its oracle does not reject "
                    f"{rejected_items} collection items"
                )
    return errors


def validate_workspace_seed(
    task_dir: Path,
    metadata: dict,
    *,
    task_id: str | None = None,
) -> list[str]:
    """Validate an optional on-disk seed for the unified agent workspace.

    Git does not represent empty directories. A missing declared workspace
    directory therefore denotes an empty seed; the controller still creates a
    fresh ``/workspace`` for the trial. If the path is present, it must remain a
    real directory containing only regular files and real directories.
    """

    resolved_task_id = str(task_id or metadata.get("task_id") or task_dir.name)
    workspace_name = str(metadata.get("workspace_dir") or "")
    workspace_relative = PurePosixPath(workspace_name)
    if (
        not workspace_name
        or workspace_relative.is_absolute()
        or ".." in workspace_relative.parts
        or len(workspace_relative.parts) != 1
    ):
        return [f"{resolved_task_id}: workspace_dir must be one safe directory"]

    workspace_seed = task_dir / workspace_name
    if workspace_seed.is_symlink() or (
        workspace_seed.exists() and not workspace_seed.is_dir()
    ):
        return [f"{resolved_task_id}: unsafe workspace seed"]
    if workspace_seed.is_dir() and any(
        path.is_symlink()
        or (
            path.exists()
            and not path.is_dir()
            and not stat.S_ISREG(path.lstat().st_mode)
        )
        for path in workspace_seed.rglob("*")
    ):
        return [f"{resolved_task_id}: workspace seed contains a link/special entry"]
    return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expected-count",
        type=int,
        help="require exactly this many active tasks",
    )
    parser.add_argument(
        "--task-set",
        help="catalog task-set manifest that must match the active tree",
    )
    parser.add_argument(
        "--suite-root",
        type=Path,
        default=ROOT,
        help="suite directory containing tasks/ and catalog/",
    )
    args = parser.parse_args()
    suite_root = args.suite_root.expanduser().resolve()
    tasks_root = suite_root / "tasks"
    catalog_root = suite_root / "catalog"
    if not tasks_root.is_dir() or not catalog_root.is_dir():
        raise SystemExit(
            f"suite root must contain tasks/ and catalog/: {suite_root}"
        )
    TASK_ROOTS.clear()
    TASK_ROOTS["main"] = tasks_root
    if args.task_set is None:
        try:
            release = yaml.safe_load(
                (catalog_root / "release.yaml").read_text(encoding="utf-8")
            ) or {}
            args.task_set = str(release["active_manifest"])
        except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
            raise SystemExit(f"cannot resolve active task set: {exc}") from exc
    errors: list[str] = []
    warnings: list[str] = []
    task_yamls = list(iter_task_yamls())
    ids: set[str] = set()

    for task_yaml in task_yamls:
        task_dir = task_yaml.parent
        try:
            data = yaml.safe_load(task_yaml.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            errors.append(f"{task_yaml}: invalid YAML: {exc}")
            continue
        task_id = str(data.get("task_id", ""))
        if not task_id:
            errors.append(f"{task_yaml}: missing task_id")
            continue
        if task_dir.name != task_id:
            errors.append(
                f"{task_id}: directory name {task_dir.name!r} does not match task_id"
            )
        if task_id in ids:
            errors.append(f"{task_yaml}: duplicate task_id {task_id}")
        ids.add(task_id)
        try:
            task_number = int(task_id.split("-", 1)[0])
        except (TypeError, ValueError):
            errors.append(f"{task_id}: task_id must start with a numeric prefix")
            task_number = 0
        missing = sorted(REQUIRED_METADATA - set(data))
        if missing:
            errors.append(f"{task_id}: missing metadata {missing}")
        try:
            deadline = evaluate_deadline(task_dir, data)
        except (OSError, ValueError) as exc:
            errors.append(f"{task_id}: invalid deadline policy inputs: {exc}")
        else:
            if deadline.existing_timeout < deadline.floor:
                active_flags = (
                    "".join(
                        name for name in ("H", "A", "I", "S") if deadline.flags[name]
                    )
                    or "-"
                )
                errors.append(
                    f"{task_id}: timeout_sec {deadline.existing_timeout} is "
                    f"below deterministic floor {deadline.floor} "
                    f"(flags={active_flags})"
                )
        collection = next(
            (
                name
                for name, task_root in TASK_ROOTS.items()
                if task_yaml.parent.parent == task_root
            ),
            None,
        )
        if collection == "main":
            domain = str(data.get("domain") or "")
            difficulty = str(data.get("difficulty") or "")
            if domain not in ALLOWED_DOMAINS:
                errors.append(f"{task_id}: unsupported domain {domain!r}")
            if difficulty not in ALLOWED_DIFFICULTIES:
                errors.append(f"{task_id}: unsupported difficulty {difficulty!r}")
            demands = data.get("harness_demands")
            if not (
                isinstance(demands, list)
                and demands
                and all(isinstance(value, str) and value for value in demands)
            ):
                errors.append(f"{task_id}: harness_demands must be a non-empty list")
            else:
                unknown_demands = sorted(set(demands) - ALLOWED_HARNESS_DEMANDS)
                if unknown_demands:
                    errors.append(
                        f"{task_id}: unsupported harness_demands {unknown_demands}"
                    )
                if task_number >= 69 and "multi_step_execution" not in demands:
                    errors.append(
                        f"{task_id}: expansion task must require multi_step_execution"
                    )
            errors.extend(
                validate_design_record(
                    task_dir,
                    data,
                    expansion=task_number >= 69,
                )
            )
        prompt_names = data.get("prompt_files") or [
            data.get("prompt_file", "prompt.txt")
        ]
        for name in prompt_names:
            if not (task_dir / name).is_file():
                errors.append(f"{task_id}: missing prompt {name}")
        errors.extend(validate_semantic_judge_record(task_dir, data, task_id=task_id))
        try:
            oracle_kind, oracle = oracle_definition(task_dir, data)
        except RuntimeError as exc:
            errors.append(f"{task_id}: {exc}")
            oracle_kind, oracle = "invalid", task_dir / "oracle_grade.py"
        if not oracle.is_file():
            oracle_label = {
                "outcome": "outcome test",
                "spec": "oracle spec",
            }.get(oracle_kind, "oracle")
            errors.append(f"{task_id}: missing {oracle_label} {oracle.name}")
        elif oracle_kind == "outcome":
            try:
                outcome_case_definition(task_dir, data)
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append(f"{task_id}: invalid outcome cases: {exc}")

            expected_layout = {
                "workspace_dir": "workspace",
                "outcome_test": "tests/test_outcome.py",
                "cases_file": "tests/cases.yaml",
                "design_file": "design.md",
            }
            for field, expected_value in expected_layout.items():
                actual = str(data.get(field) or "")
                if actual != expected_value:
                    errors.append(
                        f"{task_id}: formal outcome-case task {field} must be {expected_value!r}, "
                        f"got {actual!r}"
                    )
            formal_prompt_files = data.get("prompt_files")
            if formal_prompt_files:
                if data.get("prompt_file"):
                    errors.append(
                        f"{task_id}: formal task cannot declare both prompt_file and prompt_files"
                    )
                if not (
                    isinstance(formal_prompt_files, list)
                    and formal_prompt_files
                    and formal_prompt_files[0] == "instruction.md"
                    and all(
                        isinstance(value, str)
                        and (
                            value == "instruction.md"
                            or re.fullmatch(r"instructions/round-[0-9]{2}\.md", value)
                        )
                        for value in formal_prompt_files
                    )
                ):
                    errors.append(
                        f"{task_id}: formal prompt_files must start with instruction.md "
                        "and use instructions/round-NN.md for distinct later rounds"
                    )
            elif str(data.get("prompt_file") or "") != "instruction.md":
                errors.append(
                    f"{task_id}: formal single-round task prompt_file must be 'instruction.md'"
                )
            if str(data.get("variant") or "").casefold() in {
                "refined",
                "migrated",
                "v2",
            }:
                errors.append(
                    f"{task_id}: variant must describe task semantics, not migration status"
                )
            allowed_top_level = {
                "task.yaml",
                "instruction.md",
                "instructions",
                "workspace",
                "environment",
                "design.md",
                "tests",
            }
            unexpected_top_level = sorted(
                entry.name
                for entry in task_dir.iterdir()
                if entry.name not in allowed_top_level
                and entry.name not in {"__pycache__", ".pytest_cache"}
            )
            if unexpected_top_level:
                errors.append(
                    f"{task_id}: formal outcome-case task has paths outside the "
                    f"top-level layout: {unexpected_top_level}"
                )
            tests_dir = task_dir / "tests"
            if tests_dir.is_dir() and not tests_dir.is_symlink():
                allowed_test_entries = {
                    "cases.yaml",
                    "test_outcome.py",
                    "ground_truth",
                    "reference",
                }
                unexpected_test_entries = sorted(
                    entry.name
                    for entry in tests_dir.iterdir()
                    if entry.name not in allowed_test_entries
                    and entry.name not in {"__pycache__", ".pytest_cache"}
                )
                if unexpected_test_entries:
                    errors.append(
                        f"{task_id}: formal tests/ has non-standard paths: "
                        f"{unexpected_test_entries}"
                    )
            environment_config = data.get("environment")
            shared_environment = (
                isinstance(environment_config, dict)
                and environment_config.get("schema_version") == 1
                and environment_config.get("mode") == "shared"
            )
            required_directories = [
                "tests",
                "tests/ground_truth",
                "tests/reference",
            ]
            if formal_environment_directory_required(environment_config):
                required_directories.insert(0, "environment")
            for relative in required_directories:
                path = task_dir / relative
                if not path.is_dir() or path.is_symlink():
                    errors.append(
                        f"{task_id}: formal outcome-case task missing safe {relative}/"
                    )
            environment_dockerfile = task_dir / "environment" / "Dockerfile"
            if not environment_dockerfile.is_file() and not shared_environment:
                errors.append(
                    f"{task_id}: formal outcome-case task missing "
                    "environment/Dockerfile"
                )
            elif not shared_environment:
                dockerfile_text = environment_dockerfile.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
                stage_aliases: set[str] = set()
                for line_number, match in enumerate(
                    re.finditer(
                        r"(?im)^\s*FROM(?:\s+--platform=\S+)?\s+([^\s]+)"
                        r"(?:\s+AS\s+([^\s#]+))?",
                        dockerfile_text,
                    ),
                    start=1,
                ):
                    image, alias = match.groups()
                    if (
                        image.casefold() not in stage_aliases
                        and re.fullmatch(
                            r"[^@\s]+@sha256:[0-9a-f]{64}",
                            image,
                            flags=re.IGNORECASE,
                        )
                        is None
                    ):
                        errors.append(
                            f"{task_id}: environment/Dockerfile FROM #{line_number} "
                            "must use an immutable sha256 digest or a prior stage"
                        )
                    if alias:
                        stage_aliases.add(alias.casefold())
                errors.extend(
                    validate_formal_environment_dockerfile(
                        task_id,
                        dockerfile_text,
                    )
                )
            forbidden_legacy = (
                "prompt.txt",
                "oracle_grade.py",
                "oracle_spec.json",
                "ground_truth.json",
                "reference",
            )
            for relative in forbidden_legacy:
                if (task_dir / relative).exists():
                    errors.append(
                        f"{task_id}: formal outcome-case task retains legacy root "
                        f"path {relative!r}"
                    )
            if (task_dir / "workspace" / "output_contract.json").exists():
                errors.append(
                    f"{task_id}: formal outcome-case task must explain outputs in "
                    "instruction.md; "
                    "workspace/output_contract.json is forbidden"
                )
        elif oracle_kind == "spec":
            try:
                oracle_spec = json.loads(oracle.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"{task_id}: invalid oracle spec JSON: {exc}")
            else:
                for error in validate_oracle_spec(
                    oracle_spec,
                    task_dir=task_dir,
                ):
                    errors.append(f"{task_id}: oracle spec: {error}")
                if oracle_spec.get("task_id") != task_id:
                    errors.append(
                        f"{task_id}: oracle spec task_id mismatch "
                        f"{oracle_spec.get('task_id')!r}"
                    )
        if "fixtures_dir" in data or "input_integrity" in data:
            errors.append(f"{task_id}: legacy split-workspace metadata is forbidden")
        errors.extend(validate_workspace_seed(task_dir, data, task_id=task_id))
        errors.extend(validate_public_output_contract(task_dir, task_id))

        artifacts = data.get("required_artifacts", []) or []
        if collection == "main" and not artifacts:
            warnings.append(f"{task_id}: main task has no declared required_artifacts")
        if len(artifacts) != len(set(artifacts)):
            errors.append(f"{task_id}: duplicate required_artifacts")
        normalized_artifacts = normalize_required_artifacts(
            [str(value) for value in artifacts]
        )
        if len(artifacts) != len(normalized_artifacts):
            errors.append(f"{task_id}: normalized duplicate required_artifacts")
        try:
            mutation = normalize_mutation_contract(data.get("mutation_contract"))
        except (TypeError, ValueError) as exc:
            errors.append(f"{task_id}: invalid mutation_contract: {exc}")
            mutation = {
                "allowed_created": [],
                "allowed_modified": [],
                "allowed_deleted": [],
            }
        if collection == "main" and "mutation_contract" not in data:
            errors.append(f"{task_id}: main task must declare mutation_contract")

        def mutation_allows(path: str, rules: list[str]) -> bool:
            return any(
                path == rule.rstrip("/")
                or (rule.endswith("/") and path.startswith(rule))
                for rule in rules
            )

        writable_rules = [
            *mutation["allowed_created"],
            *mutation["allowed_modified"],
        ]
        for artifact in normalized_artifacts:
            if not mutation_allows(artifact, writable_rules):
                errors.append(
                    f"{task_id}: required artifact {artifact!r} is outside "
                    "the mutation contract"
                )
            reference_root = (
                task_dir / "tests" / "reference"
                if oracle_kind == "outcome"
                else task_dir / "reference"
            )
            if not (reference_root / artifact).exists():
                errors.append(f"{task_id}: reference artifact missing at {artifact!r}")

        text_paths = (
            [task_yaml]
            + ([oracle] if oracle.is_file() else [])
            + [task_dir / name for name in prompt_names if (task_dir / name).is_file()]
        )
        for path in text_paths:
            text = path.read_text(encoding="utf-8", errors="replace")
            if LOCAL_PATH.search(text):
                errors.append(f"{task_id}: host-local absolute path in {path.name}")
            if re.search(r"(?:\\$WORKSPACE|/workspace)/(?:in|out)(?:/|\\b)", text):
                errors.append(f"{task_id}: legacy split-workspace path in {path.name}")

        provenance = data.get("provenance", {})
        source_ids = provenance.get("source_ids") or []
        for source_id in source_ids:
            if str(source_id) not in SOURCE_REGISTRY_TEXT:
                errors.append(
                    f"{task_id}: source ID {source_id!r} is absent from "
                    "docs/task_sources"
                )
        if provenance.get("real_user_log_derived") is True and not provenance.get(
            "sampling_document"
        ):
            errors.append(f"{task_id}: user-log provenance lacks sampling_document")

        if collection == "main":
            hook = task_dir / data.get("hooks_module", "hooks.py")
            for path in [
                p for p in [hook, *(task_dir / n for n in prompt_names)] if p.is_file()
            ]:
                text = path.read_text(encoding="utf-8", errors="replace").lower()
                if "trycloudflare" in text or "public tunnel" in text:
                    errors.append(f"{task_id}: main task depends on a public tunnel")

        malformed_declarations = data.get("intentionally_malformed_workspace_files", [])
        declared_malformed: set[Path] = set()
        if malformed_declarations:
            if not (
                isinstance(malformed_declarations, list)
                and all(
                    isinstance(value, str) and value.strip()
                    for value in malformed_declarations
                )
            ):
                errors.append(
                    f"{task_id}: intentionally_malformed_workspace_files must "
                    "be a list of non-empty task-relative paths"
                )
            else:
                for raw_path in malformed_declarations:
                    declared = _safe_task_file(task_dir, raw_path)
                    if (
                        declared is None
                        or not declared.is_file()
                        or task_dir / "workspace" not in declared.parents
                        or declared.suffix.casefold() != ".json"
                    ):
                        errors.append(
                            f"{task_id}: unsafe or missing intentionally malformed "
                            f"JSON fixture {raw_path!r}"
                        )
                        continue
                    declared_malformed.add(declared.resolve())

        for json_file in task_dir.rglob("*.json"):
            try:
                json.loads(json_file.read_text(encoding="utf-8"))
            except Exception as exc:
                if json_file.resolve() in declared_malformed:
                    continue
                errors.append(
                    f"{task_id}: invalid JSON {json_file.relative_to(task_dir)}: {exc}"
                )

        unreadable_release_paths: list[str] = []
        for release_path in task_dir.rglob("*"):
            relative = release_path.relative_to(task_dir)
            if "__pycache__" in relative.parts or release_path.suffix == ".pyc":
                continue
            mode = release_path.stat().st_mode
            if release_path.is_dir():
                accessible = bool(mode & stat.S_IXOTH)
            else:
                accessible = bool(mode & stat.S_IROTH)
            if not accessible:
                unreadable_release_paths.append(relative.as_posix())
        if unreadable_release_paths:
            preview = unreadable_release_paths[:5]
            suffix = (
                ""
                if len(unreadable_release_paths) <= len(preview)
                else f" (+{len(unreadable_release_paths) - len(preview)} more)"
            )
            errors.append(
                f"{task_id}: release files are not readable from a distinct "
                f"CPU worker account: {preview}{suffix}"
            )

    main_count = sum(
        1 for task_yaml in task_yamls if task_yaml.parent.parent == TASK_ROOTS["main"]
    )
    if args.expected_count is not None:
        if args.expected_count <= 0:
            errors.append("--expected-count must be positive")
        if len(task_yamls) != args.expected_count:
            errors.append(
                f"expected {args.expected_count} formal tasks, found {len(task_yamls)}"
            )
        if main_count != args.expected_count:
            errors.append(
                f"expected {args.expected_count} default main tasks, found {main_count}"
            )
    actual_main_ids = {
        task_yaml.parent.name
        for task_yaml in task_yamls
        if task_yaml.parent.parent == TASK_ROOTS["main"]
    }
    standard_manifest = catalog_root / f"{args.task_set}.yaml"
    try:
        standard_data = yaml.safe_load(standard_manifest.read_text(encoding="utf-8"))
        standard_ids = set(standard_data["task_ids"])
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        errors.append(f"cannot load {args.task_set} manifest: {exc}")
    else:
        if actual_main_ids != standard_ids:
            errors.append(
                f"active task tree differs from catalog/{args.task_set}.yaml "
                f"missing={sorted(standard_ids - actual_main_ids)} "
                f"extra={sorted(actual_main_ids - standard_ids)}"
            )

    print(f"validated_tasks={len(task_yamls)}")
    print(f"errors={len(errors)}")
    print(f"warnings={len(warnings)}")
    for warning in warnings:
        print(f"WARNING {warning}")
    for error in errors:
        print(f"ERROR {error}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
