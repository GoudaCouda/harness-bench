import re

IDENT = re.compile(r"[a-z0-9][a-z0-9_-]*")
CHECKSUM = re.compile(r"[0-9a-f]{64}")


def _migration(value, ledger=False):
    required = (
        {"id", "from_version", "to_version", "checksum"}
        if ledger
        else {"id", "from_version", "to_version", "checksum", "statements"}
    )
    if (
        not isinstance(value, dict)
        or set(value) != required
        or not isinstance(value["id"], str)
        or not IDENT.fullmatch(value["id"])
        or type(value["from_version"]) is not int
        or type(value["to_version"]) is not int
        or value["from_version"] < 0
        or value["to_version"] <= value["from_version"]
        or not isinstance(value["checksum"], str)
        or not CHECKSUM.fullmatch(value["checksum"])
    ):
        raise ValueError("invalid migration identity")
    if not ledger:
        statements = value["statements"]
        if not isinstance(statements, list) or not statements:
            raise ValueError("invalid statements")
        for statement in statements:
            if (
                not isinstance(statement, str)
                or not statement.strip()
                or statement.strip().casefold().split()[0]
                in ("begin", "commit", "rollback", "savepoint", "release")
            ):
                raise ValueError("transaction control is not a migration statement")


def _full_actions(migration):
    return (
        ["begin_immediate"]
        + [f"statement:{index}" for index in range(len(migration["statements"]))]
        + [
            f"ledger_insert:{migration['id']}:{migration['checksum']}",
            f"set_user_version:{migration['to_version']}",
            "commit",
        ]
    )


def plan_migration_recovery(migration, db_state, observation):
    _migration(migration)
    if (
        not isinstance(db_state, dict)
        or set(db_state) != {"user_version", "ledger"}
        or type(db_state["user_version"]) is not int
        or db_state["user_version"] < 0
        or not isinstance(db_state["ledger"], list)
    ):
        raise ValueError("invalid database state")
    ledger_by_id = {}
    highest = 0
    for record in db_state["ledger"]:
        _migration(record, ledger=True)
        if record["id"] in ledger_by_id:
            raise ValueError("duplicate ledger id")
        ledger_by_id[record["id"]] = record
        highest = max(highest, record["to_version"])
    if highest != db_state["user_version"]:
        raise ValueError("ledger and user_version diverge")
    if (
        not isinstance(observation, dict)
        or set(observation) != {"phase", "transaction_active"}
        or type(observation["transaction_active"]) is not bool
        or observation["phase"]
        not in (
            "clean",
            "busy_begin",
            "busy_statement",
            "busy_commit",
            "commit_unknown",
            "interrupted",
        )
    ):
        raise ValueError("invalid observation")
    active = observation["phase"] in ("busy_statement", "busy_commit")
    if observation["transaction_active"] != active:
        raise ValueError("inconsistent transaction state")
    verification = {
        "migration_id": migration["id"],
        "checksum": migration["checksum"],
        "user_version": migration["to_version"],
    }
    existing = ledger_by_id.get(migration["id"])
    if existing is not None:
        identity = {
            name: migration[name]
            for name in ("id", "from_version", "to_version", "checksum")
        }
        if existing != identity or db_state["user_version"] != migration["to_version"]:
            raise ValueError("migration identity diverges")
        return {
            "decision": "noop",
            "retry_scope": "none",
            "actions": [],
            "verification": verification,
        }
    if db_state["user_version"] != migration["from_version"]:
        raise ValueError("migration does not start at current version")
    phase = observation["phase"]
    if phase == "clean":
        return {
            "decision": "apply",
            "retry_scope": "none",
            "actions": _full_actions(migration),
            "verification": verification,
        }
    if phase == "busy_begin":
        return {
            "decision": "retry",
            "retry_scope": "whole_transaction",
            "actions": ["wait_backoff"] + _full_actions(migration),
            "verification": verification,
        }
    if phase == "busy_statement":
        return {
            "decision": "retry",
            "retry_scope": "whole_transaction",
            "actions": ["rollback", "wait_backoff"] + _full_actions(migration),
            "verification": verification,
        }
    if phase == "busy_commit":
        return {
            "decision": "retry_commit",
            "retry_scope": "commit_only",
            "actions": ["wait_backoff", "commit"],
            "verification": verification,
        }
    if phase == "commit_unknown":
        return {
            "decision": "probe",
            "retry_scope": "after_recheck",
            "actions": ["reopen", "read_ledger_and_user_version"],
            "verification": verification,
        }
    return {
        "decision": "retry",
        "retry_scope": "whole_transaction",
        "actions": ["reopen", "read_ledger_and_user_version"]
        + _full_actions(migration),
        "verification": verification,
    }
