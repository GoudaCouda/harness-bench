def run_isolated_suite(fixture, tests, seed, quarantines, day):
    def clone(value):
        if type(value) is dict:
            return {key: clone(item) for key, item in value.items()}
        if type(value) is list:
            return [clone(item) for item in value]
        if value is None or type(value) in (str, int, float, bool):
            return value
        raise ValueError("non-json")

    def valid_text(value):
        return (
            type(value) is str
            and bool(value)
            and all(not (55296 <= ord(char) <= 57343) for char in value)
        )

    if (
        type(fixture) is not dict
        or type(tests) is not list
        or type(seed) is not int
        or type(quarantines) is not list
        or type(day) is not int
    ):
        raise ValueError("root")
    clone(fixture)
    qmap = {}
    for item in quarantines:
        if (
            type(item) is not dict
            or set(item) != {"test_id", "expires_day"}
            or not valid_text(item["test_id"])
            or type(item["expires_day"]) is not int
            or item["test_id"] in qmap
        ):
            raise ValueError("quarantine")
        qmap[item["test_id"]] = item["expires_day"]
    seen = set()
    clean = []
    for test in tests:
        if (
            type(test) is not dict
            or set(test) != {"test_id", "operations"}
            or not valid_text(test["test_id"])
            or test["test_id"] in seen
            or type(test["operations"]) is not list
        ):
            raise ValueError("test")
        seen.add(test["test_id"])
        clean.append(test)
    if any(name not in seen for name in qmap):
        raise ValueError("unknown quarantine")
    results = []
    for test in clean:
        state = clone(fixture)
        failures = []
        random_state = 2166136261
        for byte in (str(seed) + ":" + test["test_id"]).encode("utf-8"):
            random_state = ((random_state ^ byte) * 16777619) % 4294967296
        for index, operation in enumerate(test["operations"]):
            if (
                type(operation) is not dict
                or type(operation.get("op")) is not str
                or type(operation.get("key")) is not str
                or not operation.get("key")
                or operation["key"] not in state
            ):
                raise ValueError("operation")
            op = operation["op"]
            key = operation["key"]
            if op in ("set", "append", "assert_equal", "assert_not_equal") and set(
                operation
            ) != {"op", "key", "value"}:
                raise ValueError("operation")
            if op == "increment" and (
                set(operation) != {"op", "key", "amount"}
                or type(operation["amount"]) is not int
                or type(state[key]) is not int
            ):
                raise ValueError("increment")
            if op == "random_below" and (
                set(operation) != {"op", "key", "upper"}
                or type(operation["upper"]) is not int
                or operation["upper"] <= 0
            ):
                raise ValueError("random")
            if op == "set":
                state[key] = clone(operation["value"])
            elif op == "append":
                if type(state[key]) is not list:
                    raise ValueError("append")
                state[key].append(clone(operation["value"]))
            elif op == "increment":
                state[key] += operation["amount"]
            elif op == "random_below":
                random_state = (1664525 * random_state + 1013904223) % 4294967296
                state[key] = random_state % operation["upper"]
            elif op == "assert_equal":
                if state[key] != operation["value"]:
                    failures.append(
                        {
                            "operation": index,
                            "key": key,
                            "expected": clone(operation["value"]),
                            "actual": clone(state[key]),
                        }
                    )
            elif op == "assert_not_equal":
                if state[key] == operation["value"]:
                    failures.append(
                        {
                            "operation": index,
                            "key": key,
                            "expected": {"not": clone(operation["value"])},
                            "actual": clone(state[key]),
                        }
                    )
            else:
                raise ValueError("unknown operation")
        status = (
            "passed"
            if not failures
            else "quarantined_failed"
            if test["test_id"] in qmap and day <= qmap[test["test_id"]]
            else "failed"
        )
        results.append(
            {
                "test_id": test["test_id"],
                "status": status,
                "failures": failures,
                "observed": state,
            }
        )
    return results
