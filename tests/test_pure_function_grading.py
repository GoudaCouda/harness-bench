from harnessbench.grading.pure_function import audit_pure_function, run_pure_function


def test_audit_and_execution_accept_pure_candidate() -> None:
    source = "def solve(items):\n    return sorted(items, key=lambda item: item['id'])\n"
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(source, "solve", [{"items": [{"id": 2}, {"id": 1}]}], ("items",))
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": [{"id": 1}, {"id": 2}], "unchanged": True}]


def test_audit_rejects_dynamic_os_capability() -> None:
    source = "import os\ndef solve(items):\n    return os.listdir('.')\n"
    ok, detail = audit_pure_function(source, "solve")
    assert not ok
    assert "outside pure subset" in detail


def test_audit_and_runner_expose_only_pure_os_path_helpers() -> None:
    source = (
        "import os\n"
        "def solve(path):\n"
        "    stem, extension = os.path.splitext(os.path.basename(path))\n"
        "    return os.path.join(os.path.dirname(path), stem + extension)\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source, "solve", [{"path": "dir/item.txt"}], ("path",)
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": "dir/item.txt", "unchanged": True}]


def test_audit_allows_internal_helper_callback_parameter() -> None:
    source = (
        "def apply(value, callback):\n"
        "    return callback(value)\n"
        "def double(value):\n"
        "    return value * 2\n"
        "def solve(value):\n"
        "    return apply(value, double)\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source, "solve", [{"value": 3}], ("value",)
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": 6, "unchanged": True}]


def test_audit_accepts_common_pure_methods_without_task_allowlist() -> None:
    source = (
        "def solve(items):\n"
        "    keys = list(items.keys())\n"
        "    keys.sort()\n"
        "    seen = set()\n"
        "    for key in keys:\n"
        "        seen.add(key)\n"
        "    return sorted(seen)\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")


def test_audit_accepts_computation_only_standard_library_by_default() -> None:
    source = (
        "import copy\n"
        "import re\n"
        "def solve(items):\n"
        "    cloned = copy.deepcopy(items)\n"
        "    return [item for item in cloned if re.fullmatch('[a-z]+', item)]\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"items": ["safe", "NOT-SAFE"]}],
        ("items",),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": ["safe"], "unchanged": True}]


def test_audit_accepts_pure_uri_parsing_without_task_allowlist() -> None:
    source = (
        "from urllib.parse import urljoin, urlparse\n"
        "def solve(base, ref):\n"
        "    joined = urljoin(base, ref)\n"
        "    return {'uri': joined, 'scheme': urlparse(joined).scheme}\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"base": "https://schema.test/a/root.json", "ref": "../defs.json"}],
        ("base", "ref"),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [
        {
            "value": {
                "uri": "https://schema.test/defs.json",
                "scheme": "https",
            },
            "unchanged": True,
        }
    ]


def test_audit_accepts_pure_glob_matching_without_task_allowlist() -> None:
    source = (
        "import fnmatch\n"
        "def solve(paths, pattern):\n"
        "    return [path for path in paths if fnmatch.fnmatchcase(path, pattern)]\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"paths": ["src/app.py", "README.md"], "pattern": "*.md"}],
        ("paths", "pattern"),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": ["README.md"], "unchanged": True}]


def test_audit_accepts_deterministic_round_builtin() -> None:
    source = "def solve(value):\n    return round(value * 1000)\n"
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"value": 0.333}],
        ("value",),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": 333, "unchanged": True}]


def test_audit_accepts_in_memory_bytearray_accumulation() -> None:
    source = (
        "def solve(chunks):\n"
        "    payload = bytearray()\n"
        "    for chunk in chunks:\n"
        "        payload.extend(bytes(chunk))\n"
        "    return bytes(payload).decode('utf-8')\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source, "solve", [{"chunks": [[111], [107]]}], ("chunks",)
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": "ok", "unchanged": True}]


def test_audit_accepts_pure_transfer_decoders() -> None:
    source = (
        "import base64\n"
        "import quopri\n"
        "def solve(encoded, quoted):\n"
        "    return {\n"
        "        'base64': base64.b64decode(encoded).decode('utf-8'),\n"
        "        'quoted': quopri.decodestring(quoted).decode('utf-8'),\n"
        "    }\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"encoded": "aGVsbG8=", "quoted": "a=3Db"}],
        ("encoded", "quoted"),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [
        {"value": {"base64": "hello", "quoted": "a=b"}, "unchanged": True}
    ]


def test_audit_accepts_observed_regex_heap_and_hex_styles() -> None:
    source = (
        "import binascii\n"
        "import heapq\n"
        "import re\n"
        "def solve(encoded):\n"
        "    match = re.search(r'([a-z]+)', 'safe-123')\n"
        "    queue = [3, 1]\n"
        "    heapq.heapify(queue)\n"
        "    first = heapq.heappop(queue)\n"
        "    heapq.heappush(queue, 2)\n"
        "    return {\n"
        "        'decoded': binascii.unhexlify(encoded).decode('utf-8'),\n"
        "        'escaped': re.escape('a.b'),\n"
        "        'first': first,\n"
        "        'group': match.group(1),\n"
        "        'queue': queue,\n"
        "    }\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"encoded": "6f6b"}],
        ("encoded",),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [
        {
            "value": {
                "decoded": "ok",
                "escaped": r"a\.b",
                "first": 1,
                "group": "safe",
                "queue": [2, 3],
            },
            "unchanged": True,
        }
    ]


def test_audit_accepts_in_memory_csv_without_style_allowlists() -> None:
    source = (
        "import csv\n"
        "import io\n"
        "def solve(text):\n"
        "    rows = list(csv.reader(io.StringIO(text), delimiter=','))\n"
        "    return rows\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"text": "a,b\n1,2\n"}],
        ("text",),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [
        {"value": [["a", "b"], ["1", "2"]], "unchanged": True}
    ]


def test_audit_rejects_file_backed_io_entry_points() -> None:
    direct = "import io\ndef solve(path):\n    return io.open(path).read()\n"
    ok, detail = audit_pure_function(direct, "solve")
    assert not ok
    assert "file-backed" in detail

    imported = (
        "from io import open as file_open\n"
        "def solve(path):\n"
        "    return file_open(path).read()\n"
    )
    ok, detail = audit_pure_function(imported, "solve")
    assert not ok
    assert "import" in detail


def test_audit_accepts_pure_collections_constructor() -> None:
    source = (
        "import collections\n"
        "def solve(items):\n"
        "    grouped = collections.defaultdict(list)\n"
        "    for item in items:\n"
        "        grouped[item['group']].append(item['id'])\n"
        "    return dict(grouped)\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"items": [{"group": "a", "id": 1}, {"group": "a", "id": 2}]}],
        ("items",),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": {"a": [1, 2]}, "unchanged": True}]


def test_audit_accepts_pure_ip_network_matching() -> None:
    source = (
        "import ipaddress\n"
        "def solve(address, network):\n"
        "    return ipaddress.ip_address(address) in ipaddress.ip_network(network)\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"address": "10.2.3.4", "network": "10.0.0.0/8"}],
        ("address", "network"),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": True, "unchanged": True}]


def test_audit_and_runner_allow_explicit_safe_import() -> None:
    source = "import copy\ndef solve(items):\n    return copy.deepcopy(items)\n"
    assert audit_pure_function(
        source,
        "solve",
        allowed_imports=("copy",),
        allowed_methods=("deepcopy",),
    ) == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"items": [{"id": 1}]}],
        ("items",),
        allowed_imports=("copy",),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": [{"id": 1}], "unchanged": True}]


def test_audit_allows_helpers_and_safe_from_import() -> None:
    source = (
        "from copy import deepcopy\n"
        "def clone(items):\n    return deepcopy(items)\n"
        "def solve(items):\n    return clone(items)\n"
    )
    assert audit_pure_function(source, "solve", allowed_imports=("copy",)) == (
        True,
        "audited",
    )
    results, detail = run_pure_function(
        source,
        "solve",
        [{"items": [{"id": 1}]}],
        ("items",),
        allowed_imports=("copy",),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": [{"id": 1}], "unchanged": True}]


def test_audit_allows_deletion_from_a_local_copy() -> None:
    source = (
        "def solve(items):\n"
        "    projected = dict(items)\n"
        "    del projected['drop']\n"
        "    return projected\n"
    )
    assert audit_pure_function(source, "solve") == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"items": {"keep": 1, "drop": 2}}],
        ("items",),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": {"keep": 1}, "unchanged": True}]

def test_datetime_strptime_can_load_its_internal_parser_lazily() -> None:
    source = (
        "from datetime import datetime\n"
        "def solve(value):\n"
        "    parsed = datetime.strptime(value, '%Y-%m-%dT%H:%M')\n"
        "    return parsed.strftime('%Y-%m-%dT%H:%M')\n"
    )
    assert audit_pure_function(
        source,
        "solve",
        allowed_imports=("datetime",),
    ) == (True, "audited")
    results, detail = run_pure_function(
        source,
        "solve",
        [{"value": "2026-11-01T01:30"}],
        ("value",),
        allowed_imports=("datetime",),
    )
    assert detail in {"evaluated", "authoring fallback"}
    assert results == [{"value": "2026-11-01T01:30", "unchanged": True}]


def test_candidate_cannot_import_internal_strptime_directly() -> None:
    source = "import _strptime\ndef solve(value):\n    return value\n"
    ok, detail = audit_pure_function(source, "solve")
    assert not ok
    assert "import outside pure subset" in detail
