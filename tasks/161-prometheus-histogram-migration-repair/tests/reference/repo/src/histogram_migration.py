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


def _metric_name(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and (value[0].isalpha() or value[0] in "_:")
        and all(char.isalnum() or char in "_:" for char in value)
    )


def _number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value >= 0
        and value < float("inf")
    )


def _text(value):
    return str(int(value)) if int(value) == value else str(value)


def _classic(metric, window):
    name = metric["metric_name"]
    if metric["query_kind"] == "quantile":
        return f"histogram_quantile({_text(metric['quantile'])}, sum by (le) (rate({name}_bucket[{window}])))"
    if metric["query_kind"] == "average":
        return f"sum(rate({name}_sum[{window}])) / sum(rate({name}_count[{window}]))"
    return "unavailable"


def _native(metric, window):
    inner = f"sum(rate({metric['metric_name']}[{window}]))"
    if metric["query_kind"] == "quantile":
        return f"histogram_quantile({_text(metric['quantile'])}, {inner})"
    if metric["query_kind"] == "average":
        return f"histogram_avg({inner})"
    return f"histogram_fraction({_text(metric['lower'])}, {_text(metric['upper'])}, {inner})"


def plan_histogram_migration(metrics, policy):
    policy_keys = (
        "max_parity_error_pct",
        "max_counter_resets",
        "required_stable_windows",
        "required_quiet_windows",
        "min_native_schema",
        "max_native_schema",
        "rate_window",
    )
    if not _exact(policy, policy_keys) or not _number(policy["max_parity_error_pct"]):
        raise ValueError("invalid policy")
    integer_policy = (
        "max_counter_resets",
        "required_stable_windows",
        "required_quiet_windows",
        "min_native_schema",
        "max_native_schema",
    )
    if (
        any(
            not isinstance(policy[key], int) or isinstance(policy[key], bool)
            for key in integer_policy
        )
        or policy["max_counter_resets"] < 0
        or policy["required_stable_windows"] <= 0
        or policy["required_quiet_windows"] <= 0
        or policy["min_native_schema"] > policy["max_native_schema"]
    ):
        raise ValueError("invalid policy limits")
    window = policy["rate_window"]
    if (
        not isinstance(window, str)
        or len(window) < 2
        or not window[:-1].isdigit()
        or window[-1] not in "mhd"
        or int(window[:-1]) <= 0
    ):
        raise ValueError("invalid rate window")
    if not isinstance(metrics, list):
        raise ValueError("invalid metrics")
    metric_keys = (
        "metric_id",
        "metric_name",
        "query_kind",
        "quantile",
        "lower",
        "upper",
        "total_targets",
        "native_targets",
        "native_schema",
        "parity_error_pct",
        "counter_resets",
        "current_query_mode",
        "consumer_native_ready",
        "stable_windows",
        "classic_emit_enabled",
        "classic_quiet_windows",
    )
    decisions = []
    identifiers = []
    counts = {"settled": 0, "ready": 0, "blocked": 0}
    native_queries = 0
    classic_queries = 0
    for metric in metrics:
        if (
            not _exact(metric, metric_keys)
            or not _token(metric["metric_id"])
            or not _metric_name(metric["metric_name"])
        ):
            raise ValueError("invalid metric identity")
        integers = (
            "total_targets",
            "native_targets",
            "native_schema",
            "counter_resets",
            "stable_windows",
            "classic_quiet_windows",
        )
        if (
            any(
                not isinstance(metric[key], int) or isinstance(metric[key], bool)
                for key in integers
            )
            or metric["total_targets"] <= 0
            or metric["native_targets"] < 0
            or metric["native_targets"] > metric["total_targets"]
            or metric["counter_resets"] < 0
            or metric["stable_windows"] < 0
            or metric["classic_quiet_windows"] < 0
        ):
            raise ValueError("invalid metric counts")
        if (
            not _number(metric["parity_error_pct"])
            or metric["current_query_mode"] not in ("classic", "native")
            or not isinstance(metric["consumer_native_ready"], bool)
            or not isinstance(metric["classic_emit_enabled"], bool)
        ):
            raise ValueError("invalid metric state")
        kind = metric["query_kind"]
        if kind == "quantile":
            valid_parameters = (
                _number(metric["quantile"])
                and 0 < metric["quantile"] < 1
                and metric["lower"] is None
                and metric["upper"] is None
            )
        elif kind == "average":
            valid_parameters = (
                metric["quantile"] is None
                and metric["lower"] is None
                and metric["upper"] is None
            )
        elif kind == "fraction":
            valid_parameters = (
                metric["quantile"] is None
                and _number(metric["lower"])
                and _number(metric["upper"])
                and metric["lower"] < metric["upper"]
            )
        else:
            valid_parameters = False
        if not valid_parameters:
            raise ValueError("invalid query parameters")
        identifiers.append(metric["metric_id"])
        query = (
            _classic(metric, window)
            if metric["current_query_mode"] == "classic"
            else _native(metric, window)
        )
        if (
            metric["native_targets"] > 0
            and not policy["min_native_schema"]
            <= metric["native_schema"]
            <= policy["max_native_schema"]
        ):
            status, action, reason = "blocked", "hold_migration", "incompatible_schema"
        elif metric["counter_resets"] > policy["max_counter_resets"]:
            status, action, reason = "blocked", "hold_migration", "counter_resets"
        elif metric["current_query_mode"] == "classic" and kind == "fraction":
            status, action, reason = (
                "blocked",
                "hold_migration",
                "classic_query_unsupported",
            )
        elif (
            metric["native_targets"] < metric["total_targets"]
            and metric["current_query_mode"] == "native"
        ):
            status, action, reason = (
                "blocked",
                "hold_migration",
                "premature_native_query",
            )
        elif metric["native_targets"] < metric["total_targets"]:
            status, action, reason = "ready", "roll_out_native", "coverage_incomplete"
        elif metric["parity_error_pct"] > policy["max_parity_error_pct"]:
            status, action, reason = "blocked", "hold_migration", "parity_error"
        elif not metric["consumer_native_ready"]:
            status, action, reason = "blocked", "hold_migration", "consumer_not_ready"
        elif (
            metric["current_query_mode"] == "classic"
            and metric["stable_windows"] < policy["required_stable_windows"]
        ):
            status, action, reason = "ready", "validate_parity", "stability_window"
        elif metric["current_query_mode"] == "classic":
            status, action, reason = (
                "ready",
                "switch_query_to_native",
                "native_cutover_ready",
            )
            query = _native(metric, window)
        elif not metric["classic_emit_enabled"]:
            status, action, reason = "settled", "keep_native", "migration_complete"
        elif metric["classic_quiet_windows"] < policy["required_quiet_windows"]:
            status, action, reason = (
                "ready",
                "observe_classic_retirement",
                "retirement_observation",
            )
        else:
            status, action, reason = (
                "ready",
                "disable_classic_emission",
                "classic_quiet",
            )
        decisions.append(
            {
                "metric_id": metric["metric_id"],
                "status": status,
                "action": action,
                "reason": reason,
                "query": query,
            }
        )
        counts[status] += 1
        if query == _native(metric, window):
            native_queries += 1
        elif query == _classic(metric, window) and query != "unavailable":
            classic_queries += 1
    if identifiers != sorted(identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("metrics must be sorted and unique")
    return {
        "decisions": decisions,
        "summary": {
            "metric_count": len(metrics),
            "settled": counts["settled"],
            "ready": counts["ready"],
            "blocked": counts["blocked"],
            "native_queries": native_queries,
            "classic_queries": classic_queries,
        },
    }
