from __future__ import annotations

import ast
import csv
import hashlib
import json
import posixpath
import re
import shlex
from pathlib import Path
from typing import Any

_TASK_DIR = Path(__file__).resolve().parents[2]
_GT = json.loads(
    (_TASK_DIR / "tests" / "ground_truth" / "ground_truth.json").read_text(
        encoding="utf-8"
    )
)
_FIXTURE_HASHES = {
    "pyproject.toml": "30029766b5f15c673e1ff3f94e51761f",
    "minisvc/cli.py": "a8f7b9c7f0272bfbbef55b24fb8d7130",
    "minisvc/api/handlers.py": "f896c519144abb5c65a145c6319445fb",
    "minisvc/audit.py": "451909772eca5b9566c554c7df884b1d",
    "minisvc/storage/repo.py": "9f021b7a7fb66549ee95e9cd1af05d60",
    "README.md": "e3180c362099c7759ee8f2cc06f6056f",
}


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _contains_name(items: list[Any], name: str) -> bool:
    text = json.dumps(items, ensure_ascii=False).lower()
    return name.lower() in text


def _canonical_entry_hits(items: list[Any]) -> float:
    normalized: list[str] = []
    for item in items:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, dict):
            module = str(item.get("module", "")).strip()
            function = str(item.get("function", "")).strip()
            normalized.append(
                f"{module}:{function}"
                if module and function
                else json.dumps(item, ensure_ascii=False)
            )
        else:
            normalized.append(str(item))
    text = "\n".join(normalized).lower()
    return sum(entry.lower() in text for entry in _GT["expected_entry_points"]) / len(
        _GT["expected_entry_points"]
    )


def _edge_parts(edge: Any) -> tuple[str, str, str]:
    if isinstance(edge, dict):
        return (_norm(edge.get("from")), _norm(edge.get("to")), _norm(edge.get("type")))
    if isinstance(edge, (list, tuple)) and len(edge) >= 2:
        return (_norm(edge[0]), _norm(edge[1]), _norm(edge[2]) if len(edge) > 2 else "")
    return ("", "", "")


def _sequence_present(flow_texts: list[str], sequence: list[str]) -> bool:
    for text in flow_texts:
        pos = -1
        ok = True
        for token in sequence:
            idx = text.find(token.lower(), pos + 1)
            if idx < 0:
                ok = False
                break
            pos = idx
        if ok:
            return True
    return False


def _flow_action_is_negated(text: str, start: int, end: int) -> bool:
    """Reject an exact identifier when the surrounding clause denies the call."""

    prefix = text[max(0, start - 72) : start]
    local_prefix = re.split(r"(?:[.!?;,\n]|->)", prefix)[-1]
    if re.search(r"\bnot\s+only\b[^.!?;,\n]{0,32}$", local_prefix):
        negated_before = False
    else:
        negated_before = bool(
            re.search(
                r"(?:"
                r"\b(?:does|do|did|will|would|should|must|can)\s+not\b|"
                r"\bnever\b|"
                r"\bwithout(?:\s+(?:calling|invoking|using))?\b|"
                r"\bfails?\s+to\b|"
                r"\b(?:skip|omit|bypass|avoid)(?:s|ed|ing)?\b"
                r")[^.!?;,\n]{0,40}$",
                local_prefix,
            )
        )
    suffix = text[end : end + 64]
    negated_after = bool(
        re.match(
            r"^\s+(?:(?:is|was|will|would)\s+)?"
            r"(?:not|never)\s+(?:called|invoked|used|reached)\b",
            suffix,
        )
    )
    return negated_before or negated_after


def _canonical_flow(value: Any) -> str:
    text = _norm(value)
    save_identifier = re.compile(
        r"(?<![a-z0-9_.])"
        r"(?:minisvc\.storage\.repo\.)?orderrepository\.save\b"
        r"(?:\s*\(\s*\))?"
    )
    text = save_identifier.sub(
        lambda match: (
            "orderrepository-save-negated"
            if _flow_action_is_negated(text, match.start(), match.end())
            else "repo.save"
        ),
        text,
    )
    text = text.replace(":", ".")
    text = re.sub(
        r"(?P<path>/[a-z0-9_/{}/<>-]+)\s*\(\s*"
        r"(?P<method>get|post|put|patch|delete)\s*\)",
        r"\g<method> \g<path>",
        text,
    )
    return re.sub(
        r"(?P<path>/[a-z0-9_/{}/<>-]+)\s+"
        r"(?P<method>get|post|put|patch|delete)\b",
        r"\g<method> \g<path>",
        text,
    )


def _marker_module_score(modules: list[Any]) -> float:
    marker_rows = []
    for item in modules:
        if not isinstance(item, dict):
            continue
        path = _norm(item.get("path"))
        name = _norm(item.get("name"))
        if path.endswith("__init__.py") or name.endswith(".__init__"):
            marker_rows.append(item)
    if not marker_rows:
        return 1.0
    marker_terms = ("marker", "empty", "package", "init", "exports")
    hits = 0
    for item in marker_rows:
        purpose = _norm(item.get("purpose"))
        hits += int(any(term in purpose for term in marker_terms))
    return hits / len(marker_rows)


def _contains_alias_group(text: str, aliases: list[str]) -> bool:
    low = _norm(text)
    return any(_norm(alias) in low for alias in aliases)


def _concrete_code_evidence(value: Any) -> bool:
    text = str(value or "").strip()
    low = text.lower()
    return bool(
        any(term in low for term in (".py", ":", "function", "module"))
        or re.search(
            r"\b[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*){2,}\b",
            text,
        )
    )


def _onboarding_group_present(text: str, aliases: list[str]) -> bool:
    low = _norm(text)
    normalized_aliases = {_norm(alias) for alias in aliases}
    if "safe first" in normalized_aliases:
        for direct in re.finditer(r"\bsafe\s+first\b", low):
            prefix = low[max(0, direct.start() - 32) : direct.start()]
            if not re.search(r"\b(?:no|not|never|without)\b[^.!?;\n]{0,20}$", prefix):
                return True
        headings = list(
            re.finditer(
                r"(?m)^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$",
                low,
            )
        )
        for index, heading in enumerate(headings):
            if not re.search(
                r"\b(?:recommended\s+)?first\s+"
                r"(?:contributions?|changes?|tasks?)\b",
                heading.group("title"),
            ):
                continue
            end = headings[index + 1].start() if index + 1 < len(headings) else len(low)
            section = f"{heading.group('title')} {low[heading.end() : end]}"
            safe_change = re.search(
                r"\bsafe\b.{0,120}\b(?:changes?|contributions?|tasks?)\b",
                section,
                re.DOTALL,
            )
            if safe_change is None:
                continue
            prefix = section[max(0, safe_change.start() - 40) : safe_change.start()]
            if not re.search(
                r"\b(?:no|not|never|without)\b[^.!?;\n]{0,28}$",
                prefix,
            ):
                return True
        return False
    if "__init__" in normalized_aliases:
        init_windows = [
            low[match.start() : match.end() + 220]
            for match in re.finditer(r"__init__(?:\.py)?", low)
        ]
        explicit_marker_claims = [
            window
            for window in init_windows
            if re.search(r"\b(?:package\s+)?markers?\b", window)
        ]
        if explicit_marker_claims:
            return any(
                not re.search(
                    r"\b(?:not|never)\s+(?:an?\s+)?"
                    r"(?:package\s+)?markers?\b",
                    window,
                )
                for window in explicit_marker_claims
            )
        return _contains_alias_group(text, aliases)
    if "runtime" in normalized_aliases:
        if _contains_alias_group(text, aliases):
            return True
        for marker in re.finditer(r"__init__(?:\.py)?", low):
            window = low[marker.start() : marker.end() + 220]
            marker_claim = re.search(r"\b(?:package\s+)?markers?\b", window)
            marker_denied = re.search(
                r"\b(?:not|never)\s+(?:an?\s+)?(?:package\s+)?markers?\b",
                window,
            )
            if (
                marker_claim
                and not marker_denied
                and re.search(
                    r"\b(?:no|not|without)\b.{0,40}\bbusiness logic\b",
                    window,
                )
            ):
                return True
        return False
    return _contains_alias_group(text, aliases)


def _fenced_code_blocks(text: str) -> list[tuple[int, str, str]]:
    return [
        (
            match.start(),
            match.group("language").strip().casefold(),
            match.group("body"),
        )
        for match in re.finditer(
            r"```(?P<language>[^\n]*)\n(?P<body>.*?)```",
            text,
            re.DOTALL,
        )
    ]


def _literal_db_path(value: str) -> str | None:
    stripped = value.strip()
    if not stripped or any(token in stripped for token in ("$", "`", "\x00")):
        return None
    return posixpath.normpath(stripped)


def _cli_bootstrap_paths(body: str) -> set[str]:
    """Return concrete SQLite paths initialized by real minisvc CLI commands."""

    active_db: str | None = None
    active_db_declared = False
    bootstrapped: set[str] = set()
    for raw_line in body.splitlines():
        try:
            tokens = shlex.split(raw_line, comments=True, posix=True)
        except ValueError:
            continue
        if tokens[:1] == ["$"]:
            tokens = tokens[1:]
        if not tokens:
            continue
        if tokens[0] == "unset" and "MINISVC_DB" in tokens[1:]:
            active_db = None
            active_db_declared = False
            continue
        if tokens[0] == "export":
            for token in tokens[1:]:
                if token.startswith("MINISVC_DB="):
                    active_db_declared = True
                    active_db = _literal_db_path(token.split("=", 1)[1])
            continue

        python_index = next(
            (
                index
                for index, token in enumerate(tokens)
                if re.fullmatch(r"(?:.*/)?python(?:3(?:\.\d+)?)?", token)
            ),
            None,
        )
        command_prefix = tokens[:python_index] if python_index is not None else []
        if command_prefix[:1] == ["env"]:
            command_prefix = command_prefix[1:]
        if (
            python_index is None
            or any(
                not re.fullmatch(r"[A-Za-z_]\w*=.*", token) for token in command_prefix
            )
            or tokens[python_index + 1 : python_index + 3] != ["-m", "minisvc.cli"]
        ):
            continue
        inline_db_tokens = [
            token for token in command_prefix if token.startswith("MINISVC_DB=")
        ]
        if inline_db_tokens:
            database_path = _literal_db_path(
                inline_db_tokens[-1].split("=", 1)[1],
            )
        elif active_db_declared:
            database_path = active_db
        else:
            database_path = "orders.sqlite"
        if database_path is not None:
            bootstrapped.add(database_path)
    return bootstrapped


def _handler_smoke_recipe_present(text: str) -> bool:
    """Recognize a fixture-bound smoke workflow without executing submitted code.

    A Python recipe may initialize its repository directly, or consume the
    same concrete SQLite path initialized by an earlier ``minisvc.cli`` shell
    command. It must then invoke a real handler and observe/assert its result.
    """

    blocks = _fenced_code_blocks(text)
    cli_bootstraps = [
        (position, database_path)
        for position, language, body in blocks
        if language in {"", "bash", "sh", "shell", "zsh"}
        for database_path in _cli_bootstrap_paths(body)
    ]

    for block_position, language, body in blocks:
        if language not in {"", "py", "python", "python3"}:
            continue
        try:
            tree = ast.parse(body)
        except SyntaxError:
            continue

        repository_constructors: set[str] = set()
        handlers: dict[str, str] = {}
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module == "minisvc.storage.repo":
                repository_constructors.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "OrderRepository"
                )
            elif node.module == "minisvc.api.handlers":
                handlers.update(
                    {
                        alias.asname or alias.name: alias.name
                        for alias in node.names
                        if alias.name in {"create_order", "get_order"}
                    }
                )
        if not repository_constructors or not handlers:
            continue

        dict_values: dict[str, tuple[int, ast.Dict]] = {}
        scalar_values: dict[str, tuple[int, Any]] = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            if isinstance(node.value, ast.Dict):
                dict_values[target.id] = (node.lineno, node.value)
            elif isinstance(node.value, ast.Constant):
                scalar_values[target.id] = (node.lineno, node.value.value)

        repository_values: dict[str, tuple[int, str | None]] = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            call = node.value
            if (
                not isinstance(target, ast.Name)
                or not isinstance(call, ast.Call)
                or not isinstance(call.func, ast.Name)
                or call.func.id not in repository_constructors
                or not call.args
            ):
                continue
            path_arg = call.args[0]
            if isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str):
                database_path = _literal_db_path(path_arg.value)
            elif isinstance(path_arg, ast.Name):
                value_line, value = scalar_values.get(
                    path_arg.id,
                    (node.lineno, None),
                )
                database_path = (
                    _literal_db_path(value)
                    if value_line < node.lineno and isinstance(value, str)
                    else None
                )
            else:
                database_path = None
            repository_values[target.id] = (node.lineno, database_path)

        initialized_lines: dict[str, int] = {}
        for statement in tree.body:
            if not isinstance(statement, ast.Expr):
                continue
            node = statement.value
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "init_schema"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in repository_values
                and repository_values[node.func.value.id][0] < node.lineno
            ):
                current = initialized_lines.get(node.func.value.id)
                initialized_lines[node.func.value.id] = (
                    node.lineno if current is None else min(current, node.lineno)
                )

        handler_results: list[tuple[str, int]] = []

        def argument(call: ast.Call, index: int, keyword: str) -> ast.expr | None:
            if len(call.args) > index:
                return call.args[index]
            return next(
                (item.value for item in call.keywords if item.arg == keyword),
                None,
            )

        def concrete_create_payload(value: ast.expr | None, call_line: int) -> bool:
            if isinstance(value, ast.Name):
                value_line, value = dict_values.get(value.id, (call_line, None))
                if value_line >= call_line:
                    return False
            if not isinstance(value, ast.Dict):
                return False
            try:
                payload = ast.literal_eval(value)
            except (ValueError, TypeError):
                return False
            if not isinstance(payload, dict):
                return False
            if not {"order_id", "customer", "total_cents"}.issubset(payload):
                return False
            if payload["order_id"] in ("", None) or payload["customer"] in ("", None):
                return False
            total_cents = payload["total_cents"]
            if isinstance(total_cents, bool) or total_cents in ("", None):
                return False
            try:
                int(total_cents)
            except (TypeError, ValueError):
                return False
            return True

        def statically_false(node: ast.expr) -> bool:
            if isinstance(node, ast.Constant):
                return not bool(node.value)
            if isinstance(node, ast.BoolOp):
                values = [statically_false(value) for value in node.values]
                if isinstance(node.op, ast.And):
                    return any(values)
                if isinstance(node.op, ast.Or):
                    return all(values)
            return False

        for node in tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            call = node.value
            if (
                not isinstance(target, ast.Name)
                or not isinstance(call, ast.Call)
                or not isinstance(call.func, ast.Name)
                or call.func.id not in handlers
            ):
                continue

            repo_arg = argument(call, 1, "repo")
            if (
                not isinstance(repo_arg, ast.Name)
                or repo_arg.id not in repository_values
            ):
                continue
            repository_line, database_path = repository_values[repo_arg.id]
            init_line = initialized_lines.get(repo_arg.id)
            initialized_in_recipe = (
                init_line is not None and repository_line < init_line < node.lineno
            )
            initialized_by_cli = database_path is not None and any(
                cli_position < block_position and cli_path == database_path
                for cli_position, cli_path in cli_bootstraps
            )
            if not initialized_in_recipe and not initialized_by_cli:
                continue

            handler = handlers[call.func.id]
            first_arg = argument(
                call,
                0,
                "payload" if handler == "create_order" else "order_id",
            )
            if handler == "create_order":
                if not concrete_create_payload(first_arg, node.lineno):
                    continue
            else:
                if isinstance(first_arg, ast.Constant):
                    concrete_order_id = first_arg.value not in ("", None)
                elif isinstance(first_arg, ast.Name):
                    value_line, value = scalar_values.get(
                        first_arg.id,
                        (node.lineno, None),
                    )
                    concrete_order_id = value_line < node.lineno and value not in (
                        "",
                        None,
                    )
                else:
                    concrete_order_id = False
                if not concrete_order_id:
                    continue
            handler_results.append((target.id, node.lineno))

        for result_name, result_line in handler_results:
            for statement in tree.body:
                if getattr(statement, "lineno", 0) <= result_line:
                    continue
                if isinstance(statement, ast.Assert):
                    observed = statement.test
                    if statically_false(observed):
                        continue
                elif (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Name)
                    and statement.value.func.id in {"print", "pprint"}
                ):
                    observed = statement.value
                else:
                    continue
                if any(
                    isinstance(child, ast.Name) and child.id == result_name
                    for child in ast.walk(observed)
                ):
                    return True
    return False


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = Path(workspace).resolve()
    out = w
    checks: list[dict[str, Any]] = []

    def add(cid: str, ok: bool, weight: float, detail: Any = None) -> None:
        checks.append({"id": cid, "pass": bool(ok), "weight": weight, "detail": detail})

    module_score = 0.0
    declared_module_names: list[str] = []
    declared_module_aliases: dict[str, set[str]] = {}
    mm_path = out / "module_map.json"
    if mm_path.is_file():
        try:
            data = json.loads(mm_path.read_text(encoding="utf-8"))
            modules = data.get("modules", [])
            declared_module_names = [
                str(item.get("name") or "").strip().casefold()
                for item in modules
                if isinstance(item, dict) and str(item.get("name") or "").strip()
            ]
            declared_module_aliases = {
                str(item.get("name") or "").strip().casefold(): {
                    str(item.get("name") or "").strip().casefold(),
                    str(item.get("path") or "").strip().casefold(),
                    Path(str(item.get("path") or "")).name.casefold(),
                    ".".join(
                        str(item.get("name") or "").strip().casefold().split(".")[-2:]
                    ),
                    str(item.get("name") or "")
                    .strip()
                    .casefold()
                    .split(".")[-1]
                    .removesuffix("s"),
                }
                for item in modules
                if isinstance(item, dict) and str(item.get("name") or "").strip()
            }
            for name, aliases in declared_module_aliases.items():
                leaf = name.rsplit(".", 1)[-1]
                aliases.update(
                    {
                        "repo": {"repository", "persistence", "storage"},
                        "models": {"model", "domain"},
                        "config": {"configuration", "settings"},
                    }.get(leaf, set())
                )
            entries = data.get("entry_points", [])
            edges = data.get("dependency_edges", [])
            funcs = data.get("key_functions", [])
            flows = data.get("runtime_flows", [])
            module_hits = sum(
                _contains_name(modules, m) for m in _GT["expected_modules"]
            ) / len(_GT["expected_modules"])
            entry_hits = _canonical_entry_hits(entries)
            edge_text = json.dumps(edges, ensure_ascii=False).lower()
            edge_hits = sum(
                (a.lower() in edge_text and b.lower() in edge_text)
                for a, b in _GT["expected_edges"]
            ) / len(_GT["expected_edges"])
            edge_parts = [_edge_parts(edge) for edge in edges]
            typed_hits = 0
            for exp in _GT.get("expected_typed_edges", []):
                exp_from = _norm(exp.get("from"))
                exp_to = _norm(exp.get("to"))
                exp_types = {_norm(t) for t in exp.get("types", [])}
                typed_hits += int(
                    any(
                        src == exp_from and dst == exp_to and typ in exp_types
                        for src, dst, typ in edge_parts
                    )
                )
            typed_edge_score = typed_hits / max(
                len(_GT.get("expected_typed_edges", [])), 1
            )
            fn_hits = sum(
                _contains_name(funcs, f) for f in _GT["expected_functions"]
            ) / len(_GT["expected_functions"])
            allowed_edge_types = {
                _norm(term) for term in _GT.get("allowed_edge_types", [])
            }
            edge_types_valid = bool(edge_parts) and all(
                edge_type in allowed_edge_types for _, _, edge_type in edge_parts
            )
            flow_text = _canonical_flow(json.dumps(flows, ensure_ascii=False))
            flow_hits = sum(
                term.lower() in flow_text
                for term in _GT.get("required_runtime_flow_terms", [])
            ) / max(len(_GT.get("required_runtime_flow_terms", [])), 1)
            flow_texts = [_canonical_flow(flow) for flow in flows]
            sequence_hits = sum(
                _sequence_present(flow_texts, seq)
                for seq in _GT.get("runtime_flow_sequences", [])
            )
            sequence_score = sequence_hits / max(
                len(_GT.get("runtime_flow_sequences", [])), 1
            )
            marker_score = _marker_module_score(modules)
            structure_ok = isinstance(data, dict) and all(
                k in data
                for k in (
                    "modules",
                    "entry_points",
                    "dependency_edges",
                    "key_functions",
                    "runtime_flows",
                )
            )
            module_score = (
                0.06 * structure_ok
                + 0.20 * module_hits
                + 0.14 * entry_hits
                + 0.09 * edge_hits
                + 0.18 * typed_edge_score
                + 0.10 * fn_hits
                + 0.05 * edge_types_valid
                + 0.07 * flow_hits
                + 0.06 * sequence_score
                + 0.05 * marker_score
            )
            add(
                "module_map_content",
                module_score >= 0.75,
                _GT["scoring"]["weights"]["module_map"],
                {
                    "score": round(module_score, 4),
                    "typed_edge_hits": typed_hits,
                    "edge_types_valid": edge_types_valid,
                    "sequence_hits": sequence_hits,
                    "marker_score": round(marker_score, 4),
                },
            )
        except Exception as exc:
            add(
                "module_map_parse",
                False,
                _GT["scoring"]["weights"]["module_map"],
                str(exc),
            )
    else:
        add(
            "module_map_exists",
            False,
            _GT["scoring"]["weights"]["module_map"],
            "missing",
        )

    md_score = 0.0
    architecture_text = ""
    arch_path = out / "architecture.md"
    if arch_path.is_file():
        text = arch_path.read_text(encoding="utf-8", errors="replace")
        architecture_text = text.casefold()
        concept_groups = _GT["architecture_concept_groups"]
        concept_hits = sum(
            _contains_alias_group(text, aliases) for aliases in concept_groups
        )
        flow_groups = _GT["architecture_flow_groups"]
        flow_hits = sum(
            all(_contains_alias_group(text, aliases) for aliases in flow)
            for flow in flow_groups
        )
        md_score = (concept_hits + flow_hits) / (len(concept_groups) + len(flow_groups))
        add(
            "architecture_markdown",
            md_score >= 0.70,
            _GT["scoring"]["weights"]["architecture_md"],
            {
                "score": round(md_score, 4),
                "concept_hits": concept_hits,
                "flow_hits": flow_hits,
            },
        )
    else:
        add(
            "architecture_md_exists",
            False,
            _GT["scoring"]["weights"]["architecture_md"],
            "missing",
        )

    missing_module_mentions = [
        name
        for name in declared_module_names
        if not any(
            alias and alias in architecture_text
            for alias in declared_module_aliases.get(name, {name})
        )
    ]
    cross_artifact_consistency = bool(
        declared_module_names and architecture_text and not missing_module_mentions
    )
    add(
        "cross_artifact_consistency",
        cross_artifact_consistency,
        0.0,
        {"missing_from_architecture": missing_module_mentions},
    )

    discrepancy_score = 0.0
    disc_path = out / "doc_code_discrepancies.csv"
    if disc_path.is_file():
        try:
            with disc_path.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            cols_ok = rows and set(_GT["discrepancy_required_columns"]).issubset(
                rows[0].keys()
            )
            text = json.dumps(rows, ensure_ascii=False).lower()
            term_groups = _GT["discrepancy_term_groups"]
            term_hits = sum(_contains_alias_group(text, group) for group in term_groups)
            row_count_ok = len(rows) >= 3
            evidence_hits = sum(
                _concrete_code_evidence(row.get("code_evidence")) for row in rows
            )
            concrete_evidence_score = evidence_hits / max(len(rows), 1)
            expectation_hits = 0
            for exp in _GT.get("discrepancy_expectations", []):
                for row in rows:
                    claim_alias_groups = exp.get(
                        "claim_alias_groups",
                        [[term] for term in exp.get("claim_terms", [])],
                    )
                    claim_ok = all(
                        _contains_alias_group(row.get("claim", ""), alias_group)
                        for alias_group in claim_alias_groups
                    )
                    assessment_ok = _norm(row.get("assessment")) == _norm(
                        exp.get("assessment")
                    )
                    evidence_ok = all(
                        _contains_alias_group(
                            row.get("code_evidence", ""),
                            alias_group,
                        )
                        for alias_group in exp.get(
                            "evidence_alias_groups",
                            [exp.get("evidence_terms", [])],
                        )
                    )
                    if claim_ok and assessment_ok and evidence_ok:
                        expectation_hits += 1
                        break
            expectation_score = expectation_hits / max(
                len(_GT.get("discrepancy_expectations", [])), 1
            )
            discrepancy_score = (
                0.22 * bool(cols_ok)
                + 0.26 * (term_hits / len(term_groups))
                + 0.13 * bool(row_count_ok)
                + 0.29 * expectation_score
                + 0.10 * concrete_evidence_score
            )
            add(
                "doc_code_discrepancies",
                discrepancy_score >= 0.85,
                _GT["scoring"]["weights"]["doc_code_discrepancies"],
                {
                    "score": round(discrepancy_score, 4),
                    "rows": len(rows),
                    "term_hits": term_hits,
                    "expectation_hits": expectation_hits,
                    "concrete_evidence": round(concrete_evidence_score, 4),
                },
            )
        except Exception as exc:
            add(
                "doc_code_discrepancies_parse",
                False,
                _GT["scoring"]["weights"]["doc_code_discrepancies"],
                str(exc),
            )
    else:
        add(
            "doc_code_discrepancies_exists",
            False,
            _GT["scoring"]["weights"]["doc_code_discrepancies"],
            "missing",
        )

    risk_score = 0.0
    risk_path = out / "risk_register.csv"
    if risk_path.is_file():
        try:
            with risk_path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            expected_columns = _GT["risk_register_required_columns"]
            cols_ok = (
                bool(rows)
                and list(reader.fieldnames or []) == expected_columns
                and all(
                    None not in row
                    and set(row) == set(expected_columns)
                    and all(row.get(column) is not None for column in expected_columns)
                    for row in rows
                )
            )
            area_groups = _GT["risk_register_area_groups"]
            area_hits = sum(
                any(_contains_alias_group(row.get("area", ""), aliases) for row in rows)
                for aliases in area_groups
            )
            row_count_ok = len(rows) >= 4
            evidence_hits = sum(
                _concrete_code_evidence(row.get("evidence")) for row in rows
            )
            concrete_evidence_score = evidence_hits / max(len(rows), 1)
            risk_score = (
                0.30 * bool(cols_ok)
                + 0.35 * (area_hits / len(area_groups))
                + 0.20 * bool(row_count_ok)
                + 0.15 * concrete_evidence_score
            )
            add(
                "risk_register",
                risk_score >= 0.85,
                _GT["scoring"]["weights"]["risk_register"],
                {
                    "score": round(risk_score, 4),
                    "rows": len(rows),
                    "area_hits": area_hits,
                    "concrete_evidence": round(concrete_evidence_score, 4),
                },
            )
        except Exception as exc:
            add(
                "risk_register_parse",
                False,
                _GT["scoring"]["weights"]["risk_register"],
                str(exc),
            )
    else:
        add(
            "risk_register_exists",
            False,
            _GT["scoring"]["weights"]["risk_register"],
            "missing",
        )

    onboarding_score = 0.0
    onboarding_path = out / "onboarding_plan.md"
    if onboarding_path.is_file():
        raw_text = onboarding_path.read_text(encoding="utf-8", errors="replace")
        text = raw_text.lower()
        term_groups = _GT["onboarding_term_groups"]
        term_hits = sum(_onboarding_group_present(text, group) for group in term_groups)
        command_ok = bool(
            re.search(
                r"(?:pytest|python(?:3)?\s+-m\s+(?:pytest|unittest)|tox\b)",
                text,
            )
        ) or _handler_smoke_recipe_present(raw_text)
        onboarding_score = 0.75 * (term_hits / len(term_groups)) + 0.25 * bool(
            command_ok
        )
        add(
            "onboarding_plan",
            onboarding_score >= 0.80,
            _GT["scoring"]["weights"]["onboarding_plan"],
            {"score": round(onboarding_score, 4), "term_hits": term_hits},
        )
    else:
        add(
            "onboarding_plan_exists",
            False,
            _GT["scoring"]["weights"]["onboarding_plan"],
            "missing",
        )

    intact = []
    for rel, digest in _FIXTURE_HASHES.items():
        path = w / "repo" / rel
        intact.append(path.is_file() and _md5(path) == digest)
    integrity_score = sum(intact) / len(intact)
    add(
        "fixture_integrity",
        integrity_score == 1.0,
        _GT["scoring"]["weights"]["fixture_integrity"],
        {"score": integrity_score},
    )

    weights = _GT["scoring"]["weights"]
    total = (
        module_score * weights["module_map"]
        + md_score * weights["architecture_md"]
        + discrepancy_score * weights["doc_code_discrepancies"]
        + risk_score * weights["risk_register"]
        + onboarding_score * weights["onboarding_plan"]
        + integrity_score * weights["fixture_integrity"]
    )
    if risk_score < 0.70 or onboarding_score < 0.60:
        total = min(total, 0.82)
    thresholds = _GT["scoring"]["thresholds"]
    level = (
        "excellent"
        if total >= thresholds["excellent"]
        else "good"
        if total >= thresholds["good"]
        else "pass"
        if total >= thresholds["pass"]
        else "fail"
    )
    return {
        "task": "024-repo-architecture-map",
        "outcome_score": round(total, 4),
        "level": level,
        "checks": checks,
    }
