def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char in "-_" for char in value)
    )


def _keys(values):
    return (
        isinstance(values, list)
        and bool(values)
        and values == sorted(values)
        and len(set(values)) == len(values)
        and all(_token(value) for value in values)
    )


def plan_transaction_recovery(batches, policy):
    policy_keys = (
        "max_retries",
        "require_read_committed",
        "require_transactional_offsets",
        "transactional_id_prefix",
    )
    if (
        not _exact(policy, policy_keys)
        or not isinstance(policy["max_retries"], int)
        or isinstance(policy["max_retries"], bool)
        or policy["max_retries"] <= 0
    ):
        raise ValueError("invalid policy")
    if (
        not isinstance(policy["require_read_committed"], bool)
        or not isinstance(policy["require_transactional_offsets"], bool)
        or not _token(policy["transactional_id_prefix"])
    ):
        raise ValueError("invalid policy")
    if not isinstance(batches, list):
        raise ValueError("invalid batches")
    row_keys = (
        "batch_id",
        "transactional_id",
        "group_id",
        "topic",
        "partition",
        "first_offset",
        "last_offset",
        "committed_offset",
        "expected_output_keys",
        "visible_output_keys",
        "transaction_state",
        "attempt",
        "producer_epoch",
        "owner_epoch",
        "consumer_isolation",
        "offset_commit_mode",
    )
    decisions = []
    identifiers = []
    counts = {"settled": 0, "ready": 0, "blocked": 0}
    replay_records = 0
    for batch in batches:
        if not _exact(batch, row_keys) or not all(
            _token(batch[key])
            for key in ("batch_id", "transactional_id", "group_id", "topic")
        ):
            raise ValueError("invalid batch identity")
        numbers = (
            "partition",
            "first_offset",
            "last_offset",
            "committed_offset",
            "attempt",
            "producer_epoch",
            "owner_epoch",
        )
        if any(
            not isinstance(batch[key], int)
            or isinstance(batch[key], bool)
            or batch[key] < 0
            for key in numbers
        ):
            raise ValueError("invalid numeric field")
        if (
            batch["first_offset"] > batch["last_offset"]
            or batch["producer_epoch"] > batch["owner_epoch"]
        ):
            raise ValueError("invalid offset or epoch")
        if (
            not _keys(batch["expected_output_keys"])
            or not isinstance(batch["visible_output_keys"], list)
            or batch["visible_output_keys"] != sorted(batch["visible_output_keys"])
            or len(set(batch["visible_output_keys"]))
            != len(batch["visible_output_keys"])
            or not set(batch["visible_output_keys"]).issubset(
                set(batch["expected_output_keys"])
            )
        ):
            raise ValueError("invalid output evidence")
        if (
            batch["transaction_state"]
            not in (
                "not_started",
                "open",
                "commit_unknown",
                "committed",
                "aborted",
                "fenced",
            )
            or batch["consumer_isolation"] not in ("read_committed", "read_uncommitted")
            or batch["offset_commit_mode"] not in ("transactional", "independent")
        ):
            raise ValueError("invalid transaction controls")
        if not batch["transactional_id"].startswith(policy["transactional_id_prefix"]):
            raise ValueError("transactional id outside policy scope")
        identifiers.append(batch["batch_id"])
        complete = (
            batch["committed_offset"] == batch["last_offset"] + 1
            and batch["visible_output_keys"] == batch["expected_output_keys"]
        )
        empty = (
            batch["committed_offset"] <= batch["first_offset"]
            and not batch["visible_output_keys"]
        )
        if (
            not policy["require_read_committed"]
            or batch["consumer_isolation"] != "read_committed"
        ):
            status, action, reason, next_offset = (
                "blocked",
                "halt",
                "unsafe_isolation",
                batch["committed_offset"],
            )
        elif (
            not policy["require_transactional_offsets"]
            or batch["offset_commit_mode"] != "transactional"
        ):
            status, action, reason, next_offset = (
                "blocked",
                "halt",
                "non_atomic_offset_commit",
                batch["committed_offset"],
            )
        elif complete:
            status, action, reason, next_offset = (
                "settled",
                "acknowledge_committed",
                "atomic_commit_visible",
                batch["last_offset"] + 1,
            )
        elif not empty or batch["transaction_state"] == "committed":
            status, action, reason, next_offset = (
                "blocked",
                "halt",
                "atomicity_violation",
                batch["committed_offset"],
            )
        elif batch["producer_epoch"] < batch["owner_epoch"]:
            status, action, reason, next_offset = (
                "blocked",
                "halt",
                "producer_fenced",
                batch["committed_offset"],
            )
        elif batch["attempt"] >= policy["max_retries"]:
            status, action, reason, next_offset = (
                "blocked",
                "halt",
                "retry_budget",
                batch["committed_offset"],
            )
        elif batch["transaction_state"] == "open":
            status, action, reason, next_offset = (
                "ready",
                "abort_and_replay",
                "safe_replay",
                batch["first_offset"],
            )
        elif batch["transaction_state"] in ("commit_unknown", "fenced"):
            status, action, reason, next_offset = (
                "ready",
                "reinitialize_and_replay",
                "safe_replay",
                batch["first_offset"],
            )
        else:
            status, action, reason, next_offset = (
                "ready",
                "replay_batch",
                "safe_replay",
                batch["first_offset"],
            )
        decisions.append(
            {
                "batch_id": batch["batch_id"],
                "status": status,
                "action": action,
                "reason": reason,
                "next_offset": next_offset,
            }
        )
        counts[status] += 1
        if status == "ready":
            replay_records += batch["last_offset"] - batch["first_offset"] + 1
    if identifiers != sorted(identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("batches must be sorted and unique")
    return {
        "decisions": decisions,
        "summary": {
            "batch_count": len(batches),
            "settled": counts["settled"],
            "ready": counts["ready"],
            "blocked": counts["blocked"],
            "replay_records": replay_records,
        },
    }
