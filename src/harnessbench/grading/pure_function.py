from __future__ import annotations

import ast
import builtins
import json
import multiprocessing
import posixpath
from types import SimpleNamespace
from typing import Any, Callable, Iterable


_BUILTINS: dict[str, object] = {
    "Exception": Exception,
    "ValueError": ValueError,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "bytearray": bytearray,
    "bytes": bytes,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "ord": ord,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
}

# Computation-only standard-library modules and ordinary value/container
# methods are safe in the already isolated grader worker.  Keeping this common
# policy here prevents task authors from accidentally turning harmless Python
# style choices such as ``mapping.keys()`` or ``items.sort()`` into hidden
# zero-score conditions.  Filesystem, process, network, clock, environment,
# reflection, and dynamic-loading capabilities remain unavailable.
_SAFE_IMPORTS = frozenset(
    {
        "base64",
        "bisect",
        "binascii",
        "collections",
        "copy",
        "csv",
        "decimal",
        "fractions",
        "fnmatch",
        "functools",
        "heapq",
        "ipaddress",
        "io",
        "itertools",
        "json",
        "math",
        "operator",
        # Candidate code may use ``os.path`` as an ordinary string-path helper,
        # but execution receives the capability-free shim below rather than the
        # real ``os`` module.
        "os",
        "quopri",
        "re",
        "statistics",
        "unicodedata",
        # URI parsing and joining are deterministic string computations.  The
        # module does not perform network I/O; excluding it turns an ordinary
        # standards-compliant implementation choice into a hidden zero-score
        # condition for URI-resolution tasks.
        "urllib.parse",
    }
)

_SAFE_METHODS = frozenset(
    {
        "add",
        "append",
        "b64decode",
        "b64encode",
        "casefold",
        "Counter",
        "clear",
        "compile",
        "copy",
        "count",
        "deepcopy",
        "decode",
        "decodestring",
        "defaultdict",
        "difference",
        "discard",
        "encode",
        "encodestring",
        "endswith",
        "escape",
        "extend",
        "find",
        "findall",
        "fullmatch",
        "difference_update",
        "deque",
        "isdisjoint",
        "group",
        "groups",
        "heapify",
        "heappop",
        "heappush",
        "fromkeys",
        "fromhex",
        "finditer",
        "fnmatch",
        "fnmatchcase",
        "get",
        "index",
        "insert",
        "intersection",
        "ip_address",
        "ip_interface",
        "ip_network",
        "isalnum",
        "isalpha",
        "isascii",
        "isdecimal",
        "isdigit",
        "isidentifier",
        "islower",
        "isnumeric",
        "isspace",
        "issubset",
        "issuperset",
        "items",
        "join",
        "keys",
        "lower",
        "lstrip",
        "match",
        "normalize",
        "OrderedDict",
        "partition",
        "pop",
        "product",
        "remove",
        "replace",
        "reverse",
        "rfind",
        "rpartition",
        "rsplit",
        "rstrip",
        "search",
        "setdefault",
        "sort",
        "split",
        "splitlines",
        "startswith",
        "strip",
        "sub",
        "symmetric_difference",
        "union",
        "unhexlify",
        "update",
        "upper",
        "values",
        "zfill",
        "translate",
    }
)

# Safe modules and JSON-derived inputs do not carry ambient capabilities. Public
# methods on those values are therefore style choices, not a security boundary.
# File-backed constructors in ``io`` are the exception and remain explicitly
# unavailable; process, network, environment, clock, reflection, and dynamic
# loading modules are absent from ``_SAFE_IMPORTS`` and builtins.
_BLOCKED_METHODS = frozenset(
    {
        "BufferedRandom",
        "BufferedReader",
        "BufferedWriter",
        "FileIO",
        "TextIOWrapper",
        "open",
        "open_code",
    }
)

_SAFE_OS_PATH_METHODS = frozenset({"basename", "dirname", "join", "splitext"})

_SAFE_OS = SimpleNamespace(
    path=SimpleNamespace(
        basename=posixpath.basename,
        dirname=posixpath.dirname,
        join=posixpath.join,
        splitext=posixpath.splitext,
    )
)

_FORBIDDEN = (
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.AsyncWith,
    ast.Await,
    ast.ClassDef,
    ast.Global,
    ast.Match,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)


def audit_pure_function(
    source: str,
    function_name: str,
    *,
    allowed_methods: Iterable[str] = (),
    allowed_imports: Iterable[str] = (),
    allow_lambda: bool = True,
    max_nodes: int = 3200,
) -> tuple[bool, str]:
    """Audit a candidate function before isolated execution.

    The helper exposes only computation modules, JSON-derived values, public
    methods, and explicitly listed builtins. Private attributes, dynamic call
    targets, file-backed I/O, network, process, environment, reflection, and
    clock capabilities remain unavailable.
    """

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return False, f"syntax error: {exc.msg}"
    nodes = list(ast.walk(tree))
    if len(nodes) > max_nodes:
        return False, "implementation exceeds the auditable AST limit"
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    targets = [node for node in functions if node.name == function_name]
    if len(targets) != 1:
        return False, f"expected exactly one {function_name} function"
    defined = {node.name for node in nodes if isinstance(node, ast.FunctionDef)}
    callable_parameters = {
        argument.arg
        for function in (node for node in nodes if isinstance(node, ast.FunctionDef))
        for argument in (
            *function.args.posonlyargs,
            *function.args.args,
            *function.args.kwonlyargs,
        )
    }
    imported_callables = {
        alias.asname or alias.name
        for node in nodes
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    declared_methods = set(allowed_methods)
    if any(
        method.startswith("_") or method in _BLOCKED_METHODS
        for method in declared_methods
    ):
        return False, "unsafe method declaration"
    imports = _SAFE_IMPORTS | set(allowed_imports)
    for node in nodes:
        if isinstance(node, _FORBIDDEN) or (isinstance(node, ast.Lambda) and not allow_lambda):
            return False, f"forbidden syntax: {type(node).__name__}"
        if isinstance(node, ast.Import):
            if any(alias.name not in imports for alias in node.names):
                return False, "import outside pure subset"
        if isinstance(node, ast.ImportFrom):
            if (
                node.level
                or node.module not in imports
                or (node.module == "os" and any(alias.name != "path" for alias in node.names))
                or any(
                    alias.name == "*"
                    or alias.name.startswith("_")
                    or alias.name in _BLOCKED_METHODS
                    for alias in node.names
                )
            ):
                return False, "import outside pure subset"
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            return False, "private or dunder attribute access is forbidden"
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if (
                    node.func.id not in _BUILTINS
                    and node.func.id not in defined
                    and node.func.id not in imported_callables
                    and node.func.id not in callable_parameters
                ):
                    return False, f"call outside pure subset: {node.func.id}"
            elif isinstance(node.func, ast.Attribute):
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                ):
                    return False, f"os capability is outside pure subset: {node.func.attr}"
                if (
                    isinstance(node.func.value, ast.Attribute)
                    and isinstance(node.func.value.value, ast.Name)
                    and node.func.value.value.id == "os"
                    and (
                        node.func.value.attr != "path"
                        or node.func.attr not in _SAFE_OS_PATH_METHODS
                    )
                ):
                    return False, f"os capability is outside pure subset: {node.func.attr}"
                if node.func.attr in _BLOCKED_METHODS:
                    return False, f"file-backed method is forbidden: {node.func.attr}"
            else:
                return False, "dynamic call target is forbidden"
    return True, "audited"


def _execute(
    source: str,
    function_name: str,
    cases: list[dict[str, Any]],
    argument_names: tuple[str, ...],
    allowed_imports: tuple[str, ...],
) -> list[dict[str, Any]]:
    imports = _SAFE_IMPORTS | set(allowed_imports)

    def restricted_import(
        name: str,
        globals: object = None,
        locals: object = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        # datetime.strptime lazily imports its parser and time/locale/calendar
        # dependencies. The AST audit still rejects candidate imports of these
        # modules unless they are separately present in `imports`.
        trusted_lazy_import = name in {"_strptime", "time", "locale", "calendar"}
        if level or (name not in imports and not trusted_lazy_import):
            raise ImportError(f"import is not allowed: {name}")
        if name == "os":
            return _SAFE_OS
        return builtins.__import__(name, globals, locals, fromlist, level)

    safe_builtins = dict(_BUILTINS)
    safe_builtins["__import__"] = restricted_import
    namespace: dict[str, Any] = {"__builtins__": safe_builtins}
    exec(compile(ast.parse(source), f"candidate_{function_name}.py", "exec"), namespace)
    function = namespace[function_name]
    results: list[dict[str, Any]] = []
    for case in cases:
        values = json.loads(json.dumps(case))
        before = json.loads(json.dumps(values))
        try:
            value = function(*(values[name] for name in argument_names))
            results.append({"value": value, "unchanged": values == before})
        except Exception as exc:  # candidate failures are ordinary failed outcomes
            results.append({"error": type(exc).__name__, "unchanged": values == before})
    return results


def _worker(
    source: str,
    function_name: str,
    cases: list[dict[str, Any]],
    argument_names: tuple[str, ...],
    allowed_imports: tuple[str, ...],
    connection: Any,
) -> None:
    try:
        try:
            import resource

            resource.setrlimit(resource.RLIMIT_CPU, (4, 4))
            resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024,) * 2)
        except (ImportError, OSError, ValueError):
            pass
        connection.send(
            {
                "results": _execute(
                    source, function_name, cases, argument_names, allowed_imports
                )
            }
        )
    except BaseException as exc:
        connection.send({"error": f"{type(exc).__name__}: {exc}"})
    finally:
        connection.close()


def run_pure_function(
    source: str,
    function_name: str,
    cases: list[dict[str, Any]],
    argument_names: tuple[str, ...],
    *,
    timeout_seconds: int = 6,
    allowed_imports: Iterable[str] = (),
) -> tuple[list[dict[str, Any]], str]:
    """Execute audited candidate code in a bounded worker on POSIX graders."""

    try:
        context = multiprocessing.get_context("fork")
    except ValueError:
        try:
            return (
                _execute(
                    source,
                    function_name,
                    cases,
                    argument_names,
                    tuple(allowed_imports),
                ),
                "authoring fallback",
            )
        except Exception as exc:
            return [], f"fallback failed: {type(exc).__name__}: {exc}"
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker,
        args=(source, function_name, cases, argument_names, tuple(allowed_imports), writer),
    )
    process.start()
    writer.close()
    if not reader.poll(timeout_seconds):
        process.terminate()
        process.join(1)
        reader.close()
        return [], "candidate timed out"
    payload = reader.recv()
    reader.close()
    process.join(1)
    if process.is_alive():
        process.terminate()
        process.join(1)
    if "error" in payload:
        return [], payload["error"]
    return payload["results"], "evaluated"


def expected_results(
    oracle: Callable[..., object],
    cases: list[dict[str, Any]],
    argument_names: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Run the hidden independent oracle over copied JSON-compatible cases."""

    results: list[dict[str, Any]] = []
    for case in cases:
        values = json.loads(json.dumps(case))
        try:
            results.append({"value": oracle(*(values[name] for name in argument_names)), "unchanged": True})
        except Exception as exc:
            results.append({"error": type(exc).__name__, "unchanged": True})
    return results
