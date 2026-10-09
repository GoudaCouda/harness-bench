from __future__ import annotations

import hashlib
import html
import re
import sqlite3
import unicodedata
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any


_TEST_DIR = Path(__file__).resolve().parent
_GROUND_TRUTH = _TEST_DIR / "ground_truth"
_SOURCE_HASHES = {
    "sales_snapshot.sql": "7a1c844483d5838ed79507137115a18f10e22b93da7fc49b74738a5a7b4cbbd8",
    "reporting_policy.md": "972193f6ff0351de87e2f453121eed3f225de13351001faf92229b3584cb7f80",
}
_BASE_TABLES = ("customers", "products", "orders", "order_items", "refunds")
_ELIGIBLE_STATUSES = {"paid", "partially_refunded"}
_PERIOD_START = "2025-01-01"
_PERIOD_END = "2025-03-31"
_REFUND_CUTOFF = "2025-04-07"
_MONEY = Decimal("0.01")
_MAX_SQL_BYTES = 1_000_000
_MAX_SQL_VALUE_BYTES = 65_536
_MAX_VIEW_ROWS = 10_000
_MAX_VIEW_RESULT_BYTES = 1_000_000
_FETCH_BATCH_ROWS = 64
_VM_PROGRESS_INTERVAL = 1_000
_MAX_PROGRESS_CALLBACKS = 2_000

# SQLite reports both read-only and mutating PRAGMA statements through the same
# authorizer action.  Only the forms below can alter database/connection state
# or invoke a write-like maintenance operation.  Ordinary introspection such as
# ``PRAGMA table_info(orders)`` must not turn an otherwise correct report into a
# safety violation.
_ASSIGNMENT_MUTATING_PRAGMAS = {
    "application_id",
    "auto_vacuum",
    "automatic_index",
    "busy_timeout",
    "cache_size",
    "cache_spill",
    "case_sensitive_like",
    "cell_size_check",
    "checkpoint_fullfsync",
    "data_store_directory",
    "defer_foreign_keys",
    "encoding",
    "foreign_keys",
    "full_column_names",
    "fullfsync",
    "hard_heap_limit",
    "ignore_check_constraints",
    "journal_mode",
    "journal_size_limit",
    "legacy_alter_table",
    "legacy_file_format",
    "locking_mode",
    "max_page_count",
    "mmap_size",
    "page_size",
    "query_only",
    "read_uncommitted",
    "recursive_triggers",
    "reverse_unordered_selects",
    "schema_version",
    "secure_delete",
    "short_column_names",
    "soft_heap_limit",
    "synchronous",
    "temp_store",
    "temp_store_directory",
    "threads",
    "trusted_schema",
    "user_version",
    "writable_schema",
}
_ALWAYS_MUTATING_PRAGMAS = {
    "incremental_vacuum",
    "optimize",
    "shrink_memory",
    "wal_checkpoint",
}

_VIEW_COLUMNS = {
    "report_product_revenue": (
        "revenue_rank",
        "product_id",
        "product_name",
        "net_revenue",
    ),
    "report_region_revenue": ("region", "order_count", "net_revenue"),
    "report_category_revenue": ("category", "units_sold", "net_revenue"),
    "report_order_audit": ("order_id", "disposition"),
    "report_reconciliation": (
        "included_order_count",
        "gross_revenue",
        "discount_amount",
        "completed_refunds",
        "net_revenue",
    ),
}
_VIEW_ORDER = {
    "report_product_revenue": "revenue_rank",
    "report_region_revenue": "region",
    "report_category_revenue": "category",
    "report_order_audit": "order_id",
    "report_reconciliation": "included_order_count",
}
_MONEY_INDEXES = {
    "report_product_revenue": {3},
    "report_region_revenue": {2},
    "report_category_revenue": {2},
    "report_order_audit": set(),
    "report_reconciliation": {1, 2, 3, 4},
}
_INTEGER_INDEXES = {
    "report_product_revenue": {0},
    "report_region_revenue": {1},
    "report_category_revenue": {1},
    "report_order_audit": set(),
    "report_reconciliation": {0},
}


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("money must be returned as a numeric SQLite value")
    try:
        return Decimal(str(value)).quantize(_MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid money value") from exc


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("count and rank values must be SQLite integers")
    return value


def _pragma_crosses_safety_boundary(name: str | None, argument: str | None) -> bool:
    """Return whether a candidate PRAGMA can mutate state or perform upkeep.

    Parameterized introspection PRAGMAs (for example ``table_info(table)`` and
    ``integrity_check(1)``) are read-only and intentionally remain allowed.
    Assignment-capable settings cross the boundary only in their assignment
    form; querying their current value does not.
    """

    normalized = (name or "").casefold()
    return normalized in _ALWAYS_MUTATING_PRAGMAS or (
        normalized in _ASSIGNMENT_MUTATING_PRAGMAS and argument is not None
    )


def _expected(sql_text: str) -> dict[str, list[tuple[object, ...]]]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(sql_text)
        customers = {
            row["customer_id"]: dict(row)
            for row in connection.execute("SELECT * FROM customers")
        }
        products = {
            row["product_id"]: dict(row)
            for row in connection.execute("SELECT * FROM products")
        }
        orders = {
            row["order_id"]: dict(row)
            for row in connection.execute("SELECT * FROM orders")
        }
        refund_totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        for row in connection.execute("SELECT * FROM refunds"):
            if row["status"] == "completed" and row["refund_date"] <= _REFUND_CUTOFF:
                refund_totals[(row["order_id"], row["line_id"])] += Decimal(
                    str(row["amount"])
                )

        audit: list[tuple[object, ...]] = []
        included_orders: set[str] = set()
        for order_id, order in orders.items():
            if order["status"] not in _ELIGIBLE_STATUSES:
                disposition = "excluded_status"
            elif not _PERIOD_START <= order["order_date"] <= _PERIOD_END:
                disposition = "excluded_date"
            else:
                disposition = "included"
                included_orders.add(order_id)
            audit.append((order_id, disposition))
        audit.sort(key=lambda row: row[0])

        facts: list[dict[str, Any]] = []
        for row in connection.execute("SELECT * FROM order_items"):
            order_id = row["order_id"]
            if order_id not in included_orders:
                continue
            order = orders[order_id]
            product = products[row["product_id"]]
            gross = Decimal(str(row["quantity"])) * Decimal(str(row["unit_price"]))
            discount = Decimal(str(row["discount_amount"]))
            completed_refund = refund_totals[(order_id, row["line_id"])]
            facts.append(
                {
                    "order_id": order_id,
                    "product_id": row["product_id"],
                    "product_name": product["product_name"],
                    "category": product["category"],
                    "region": customers[order["customer_id"]]["region"],
                    "quantity": int(row["quantity"]),
                    "gross": gross,
                    "discount": discount,
                    "refund": completed_refund,
                    "net": gross - discount - completed_refund,
                }
            )

        product_totals: dict[str, Decimal] = defaultdict(Decimal)
        region_totals: dict[str, Decimal] = defaultdict(Decimal)
        region_orders: dict[str, set[str]] = defaultdict(set)
        category_totals: dict[str, Decimal] = defaultdict(Decimal)
        category_units: dict[str, int] = defaultdict(int)
        for fact in facts:
            product_totals[fact["product_id"]] += fact["net"]
            region_totals[fact["region"]] += fact["net"]
            region_orders[fact["region"]].add(fact["order_id"])
            category_totals[fact["category"]] += fact["net"]
            category_units[fact["category"]] += fact["quantity"]

        ranked_products = sorted(
            product_totals,
            key=lambda product_id: (-product_totals[product_id], product_id),
        )[:3]
        product_rows = [
            (
                rank,
                product_id,
                products[product_id]["product_name"],
                product_totals[product_id].quantize(_MONEY),
            )
            for rank, product_id in enumerate(ranked_products, start=1)
        ]
        region_rows = [
            (
                region,
                len(region_orders[region]),
                region_totals[region].quantize(_MONEY),
            )
            for region in sorted(region_totals)
        ]
        category_rows = [
            (
                category,
                category_units[category],
                category_totals[category].quantize(_MONEY),
            )
            for category in sorted(category_totals)
        ]
        reconciliation = [
            (
                len(included_orders),
                sum((fact["gross"] for fact in facts), Decimal()).quantize(_MONEY),
                sum((fact["discount"] for fact in facts), Decimal()).quantize(_MONEY),
                sum((fact["refund"] for fact in facts), Decimal()).quantize(_MONEY),
                sum((fact["net"] for fact in facts), Decimal()).quantize(_MONEY),
            )
        ]
        return {
            "report_product_revenue": product_rows,
            "report_region_revenue": region_rows,
            "report_category_revenue": category_rows,
            "report_order_audit": audit,
            "report_reconciliation": reconciliation,
        }
    finally:
        connection.close()


def _base_snapshot(connection: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    snapshot: dict[str, list[tuple[Any, ...]]] = {}
    for table in _BASE_TABLES:
        columns = [
            str(row[1])
            for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        ]
        order = ", ".join(f'"{column}"' for column in columns)
        snapshot[table] = connection.execute(
            f'SELECT * FROM "{table}" ORDER BY {order}'
        ).fetchall()
    return snapshot


def _actual_views(
    connection: sqlite3.Connection,
) -> dict[str, list[tuple[object, ...]]] | None:
    result: dict[str, list[tuple[object, ...]]] = {}
    try:
        for view, columns in _VIEW_COLUMNS.items():
            cursor = connection.execute(
                f'SELECT * FROM "{view}" ORDER BY {_VIEW_ORDER[view]}'
            )
            actual_columns = tuple(item[0] for item in cursor.description or ())
            if actual_columns != columns:
                return None
            rows: list[tuple[object, ...]] = []
            result_bytes = 0
            while True:
                source_rows = cursor.fetchmany(_FETCH_BATCH_ROWS)
                if not source_rows:
                    break
                if len(rows) + len(source_rows) > _MAX_VIEW_ROWS:
                    return None
                for source_row in source_rows:
                    result_bytes += sum(
                        len(value)
                        if isinstance(value, bytes)
                        else len(str(value).encode("utf-8"))
                        for value in source_row
                        if value is not None
                    )
                    if result_bytes > _MAX_VIEW_RESULT_BYTES:
                        return None
                    row = list(source_row)
                    for index in _MONEY_INDEXES[view]:
                        row[index] = _decimal(row[index])
                    for index in _INTEGER_INDEXES[view]:
                        row[index] = _integer(row[index])
                    rows.append(tuple(row))
            result[view] = rows
        return result
    except (sqlite3.Error, TypeError, ValueError):
        return None


def _run_variant(fixture_sql: str, report_sql: str) -> dict[str, object]:
    if len(report_sql.encode("utf-8")) > _MAX_SQL_BYTES:
        return {
            "executed": False,
            "idempotent": False,
            "matches": {view: False for view in _VIEW_COLUMNS},
            "safe": False,
        }
    expected = _expected(fixture_sql)
    connection = sqlite3.connect(":memory:")
    unsafe_attempt = False

    write_actions = {
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
    }
    forbidden_schema_actions = {
        value
        for value in (
            getattr(sqlite3, name, None)
            for name in (
                "SQLITE_ALTER_TABLE",
                "SQLITE_ANALYZE",
                "SQLITE_ATTACH",
                "SQLITE_CREATE_INDEX",
                "SQLITE_CREATE_TABLE",
                "SQLITE_CREATE_TEMP_INDEX",
                "SQLITE_CREATE_TEMP_TABLE",
                "SQLITE_CREATE_TEMP_TRIGGER",
                "SQLITE_CREATE_TEMP_VIEW",
                "SQLITE_CREATE_TRIGGER",
                "SQLITE_CREATE_VTABLE",
                "SQLITE_DETACH",
                "SQLITE_DROP_INDEX",
                "SQLITE_DROP_TABLE",
                "SQLITE_DROP_TEMP_INDEX",
                "SQLITE_DROP_TEMP_TABLE",
                "SQLITE_DROP_TEMP_TRIGGER",
                "SQLITE_DROP_TEMP_VIEW",
                "SQLITE_DROP_TRIGGER",
                "SQLITE_DROP_VTABLE",
                "SQLITE_REINDEX",
            )
        )
        if value is not None
    }
    progress_callbacks = 0

    def progress() -> int:
        nonlocal progress_callbacks, unsafe_attempt
        progress_callbacks += 1
        if progress_callbacks > _MAX_PROGRESS_CALLBACKS:
            unsafe_attempt = True
            return 1
        return 0

    def authorize(
        action: int,
        arg1: str | None,
        arg2: str | None,
        _database: str | None,
        _trigger: str | None,
    ) -> int:
        nonlocal unsafe_attempt
        if action in write_actions and arg1 in _BASE_TABLES:
            unsafe_attempt = True
            return sqlite3.SQLITE_DENY
        if action in forbidden_schema_actions:
            unsafe_attempt = True
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_PRAGMA and _pragma_crosses_safety_boundary(
            arg1, arg2
        ):
            unsafe_attempt = True
            return sqlite3.SQLITE_DENY
        if (
            action == sqlite3.SQLITE_FUNCTION
            and (arg2 or "").casefold() == "load_extension"
        ):
            unsafe_attempt = True
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    try:
        connection.executescript(fixture_sql)
        before = _base_snapshot(connection)
        # ``Connection.setlimit`` was added after Python 3.10, which remains
        # the pinned grader runtime. The explicit source-size check above,
        # progress budget, result-size budget, and container memory limit are
        # portable controls; newer runtimes receive the additional SQLite
        # engine limits when the API is available.
        setlimit = getattr(connection, "setlimit", None)
        if callable(setlimit):
            setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, _MAX_SQL_BYTES)
            setlimit(sqlite3.SQLITE_LIMIT_LENGTH, _MAX_SQL_VALUE_BYTES)
        connection.set_authorizer(authorize)
        connection.set_progress_handler(progress, _VM_PROGRESS_INTERVAL)
        connection.executescript(report_sql)
        first = _actual_views(connection)
        connection.executescript(report_sql)
        second = _actual_views(connection)
        # Python 3.10 accepts ``None`` here but then denies subsequent reads;
        # newer sqlite3 bindings use it to disable the callback. Install an
        # explicit allow-all callback for the trusted post-execution snapshot
        # so both runtimes audit the same base tables.
        connection.set_authorizer(lambda *_args: sqlite3.SQLITE_OK)
        after = _base_snapshot(connection)
        matches = {
            view: first is not None
            and second is not None
            and first.get(view) == expected[view]
            and second.get(view) == expected[view]
            for view in _VIEW_COLUMNS
        }
        return {
            "executed": first is not None and second is not None,
            "idempotent": first == second and first is not None,
            "matches": matches,
            "safe": not unsafe_attempt and before == after,
        }
    except (OSError, UnicodeError, sqlite3.Error, ValueError):
        return {
            "executed": False,
            "idempotent": False,
            "matches": {view: False for view in _VIEW_COLUMNS},
            "safe": not unsafe_attempt,
        }
    finally:
        connection.set_progress_handler(None, 0)
        connection.close()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _money_is_mentioned(text: str, value: str) -> bool:
    whole, decimal = value.split(".")
    comma = f"{int(whole):,}"
    decimal_alternatives = (f"{whole}.{decimal}", f"{comma}.{decimal}")
    whole_alternatives = (whole, comma)
    return any(
        re.search(rf"(?<![\d.])\$?{re.escape(candidate)}(?!\d)", text)
        for candidate in decimal_alternatives
    ) or any(
        re.search(rf"(?<![\d.])\$?{re.escape(candidate)}(?!\d|\.\d)", text)
        for candidate in whole_alternatives
    )


def _brief_units(text: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    units: list[str] = []
    for paragraph in paragraphs:
        flattened = " ".join(paragraph.split())
        units.append(flattened)
        units.extend(
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", flattened)
            if sentence.strip() and sentence.strip() != flattened
        )
    return units


def _visible_markdown_text(text: str) -> str:
    """Normalize the text a reviewer sees before checking business claims."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = "".join(
        " " if unicodedata.category(character) == "Cc" else character
        for character in normalized
        if unicodedata.category(character) != "Cf"
    )
    normalized = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", normalized)
    normalized = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", normalized)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    # Asterisks/tildes/backticks are presentation delimiters.  Underscores are
    # retained because the public status token ``partially_refunded`` uses one.
    normalized = normalized.translate(str.maketrans("", "", "*~`"))
    return html.unescape(normalized)


def _associated_unit(
    units: list[str],
    *,
    all_terms: tuple[str, ...] = (),
    any_terms: tuple[str, ...] = (),
    money: tuple[str, ...] = (),
    pattern: str = "",
) -> bool:
    for unit in units:
        folded = unit.casefold()
        if not all(term in folded for term in all_terms):
            continue
        if any_terms and not any(term in folded for term in any_terms):
            continue
        if money and not all(_money_is_mentioned(folded, value) for value in money):
            continue
        if pattern and not re.search(pattern, folded):
            continue
        return True
    return False


def _brief_is_complete(text: str, *, sql_executed: bool) -> bool:
    visible = _visible_markdown_text(text)
    low = " ".join(visible.casefold().split())
    units = _brief_units(visible)
    net_total = _associated_unit(
        units,
        all_terms=("net", "revenue"),
        money=("16750.00",),
    )
    product_leader = _associated_unit(
        units,
        all_terms=("atlas laptop",),
        any_terms=("leading", "leader", "top", "highest"),
    )
    region_leader = _associated_unit(
        units,
        all_terms=("north",),
        any_terms=("leading", "leader", "top", "highest"),
    )
    population = _associated_unit(
        units,
        all_terms=("included", "order"),
        pattern=r"\b(?:19|nineteen)\b",
    )
    status_exclusions = _associated_unit(
        units,
        all_terms=("status",),
        any_terms=("exclude", "excluded", "exclusion"),
        pattern=r"\b(?:6|six)\b",
    )
    date_exclusions = _associated_unit(
        units,
        all_terms=("date",),
        any_terms=("exclude", "excluded", "exclusion"),
        pattern=r"\b(?:5|five)\b",
    )
    reconciliation = _associated_unit(
        units,
        all_terms=("gross", "discount", "refund", "net"),
        money=("18075.00", "1000.00", "325.00", "16750.00"),
    )
    policy = _associated_unit(
        units,
        all_terms=(
            "paid",
            "partially_refunded",
            "completed",
            "2025-01-01",
            "2025-03-31",
            "2025-04-07",
        ),
        any_terms=("cutoff", "on or before", "through"),
    )
    no_tie_claim = bool(
        re.search(r"\bno (?:material )?ties?\b", low)
        or re.search(r"\b(?:revenues?|totals?|values?) (?:are|were) distinct\b", low)
        or re.search(r"\bnone\b.{0,35}\b(?:equal|tied)\b", low)
    )
    contradictions = (
        r"\bnet\s+revenue\b.{0,60}\b(?:is|was|equals?|totals?)\s+not\b"
        r".{0,40}(?:(?:usd|\$)\s*)?16,?750(?:\.00)?\b",
        r"(?:(?:usd|\$)\s*)?16,?750(?:\.00)?\b.{0,40}\b(?:is|was)\s+not\b"
        r".{0,60}\bnet\s+revenue\b",
        r"\b(?:does|do|did)\s+not\s+include\b.{0,100}"
        r"\b(?:paid|partially_refunded)\b",
        r"\b(?:paid|partially_refunded)\b.{0,100}"
        r"\b(?:are|were|is)\s+(?:not\s+)?(?:ineligible|excluded)\b",
        r"\batlas laptop\b.{0,80}\b(?:is|was)\s+not\b.{0,30}"
        r"\b(?:lead|leader|top)\b",
        r"\bnorth\b.{0,80}\b(?:is|was)\s+not\b.{0,30}"
        r"\b(?:lead|leader|top)\b",
    )
    return (
        sql_executed
        and net_total
        and product_leader
        and region_leader
        and population
        and status_exclusions
        and date_exclusions
        and reconciliation
        and policy
        and no_tie_claim
        and not any(re.search(pattern, low) for pattern in contradictions)
    )


def _workspace_integrity(workspace: Path) -> bool:
    try:
        return all(
            path.is_dir() or (path.is_file() and not path.is_symlink())
            for path in workspace.rglob("*")
        ) and all(
            (workspace / name).is_file()
            and not (workspace / name).is_symlink()
            and _file_sha256(workspace / name) == digest
            for name, digest in _SOURCE_HASHES.items()
        )
    except OSError:
        return False


def _observation(passed: bool, failure: str) -> dict[str, object]:
    return {"pass": passed, "detail": None if passed else failure}


def evaluate_cases(workspace: Path) -> dict[str, object]:
    """Evaluate coherent business outcomes; no individual field earns points."""
    try:
        report_sql = (workspace / "quarterly_report.sql").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        # A missing or malformed candidate artifact is an ordinary outcome
        # failure.  It must not masquerade as a source-integrity violation.
        report_sql = ""

    try:
        current_fixture = (workspace / "sales_snapshot.sql").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        current_fixture = ""

    # These files live in the hidden grader package.  If either is unavailable
    # the exception is intentionally allowed to surface as grader
    # infrastructure failure rather than candidate evidence.
    counterfactual_fixture = (_GROUND_TRUTH / "counterfactual_sales.sql").read_text(
        encoding="utf-8"
    )
    edge_fixture = (_GROUND_TRUTH / "edge_case_sales.sql").read_text(encoding="utf-8")

    try:
        brief = (workspace / "quarterly_revenue_brief.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        brief = ""

    empty_result: dict[str, object] = {
        "executed": False,
        "idempotent": False,
        "matches": {view: False for view in _VIEW_COLUMNS},
        "safe": True,
    }
    current = (
        _run_variant(current_fixture, report_sql)
        if current_fixture and report_sql
        else dict(empty_result)
    )
    counterfactual = (
        _run_variant(counterfactual_fixture, report_sql)
        if report_sql
        else dict(empty_result)
    )
    edge = _run_variant(edge_fixture, report_sql) if report_sql else dict(empty_result)
    current_matches = current["matches"]
    counterfactual_matches = counterfactual["matches"]
    edge_matches = edge["matches"]
    assert isinstance(current_matches, dict)
    assert isinstance(counterfactual_matches, dict)
    assert isinstance(edge_matches, dict)

    current_reporting = all(
        current_matches[view]
        for view in (
            "report_product_revenue",
            "report_region_revenue",
            "report_category_revenue",
        )
    )
    audit_reconciliation = all(
        current_matches[view]
        for view in ("report_order_audit", "report_reconciliation")
    )
    counterfactual_correct = (
        bool(counterfactual["executed"])
        and bool(counterfactual["idempotent"])
        and all(counterfactual_matches.values())
    )
    edge_correct = (
        bool(edge["executed"])
        and bool(edge["idempotent"])
        and all(edge_matches.values())
    )
    safe = (
        _workspace_integrity(workspace)
        and bool(current["safe"])
        and bool(counterfactual["safe"])
        and bool(edge["safe"])
    )

    return {
        "current_snapshot_reporting": _observation(
            current_reporting,
            "the current product, region, and category outcomes do not all agree",
        ),
        "audit_and_reconciliation": _observation(
            audit_reconciliation,
            "the current audit population and financial bridge do not both reconcile",
        ),
        "reusable_counterfactual_query": _observation(
            counterfactual_correct,
            "the SQL is not an idempotent, data-derived solution on a corrected extract",
        ),
        "finance_handoff": _observation(
            _brief_is_complete(brief, sql_executed=bool(current["executed"])),
            "the Finance brief omits or misstates part of the complete handoff",
        ),
        "edge_case_resilience": _observation(
            edge_correct,
            "the SQL does not jointly handle the hidden boundary, tie, and refund cases",
        ),
        "source_integrity": _observation(
            safe,
            "an input changed, an unsafe workspace entry exists, or SQL crossed the read-only boundary",
        ),
    }
