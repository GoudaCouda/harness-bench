def run_isolated_suite(fixture, tests, seed, quarantines, day):
    """Broken runner: it shares state and skips all quarantined tests."""
    state = dict(fixture)
    quarantined = {item["test_id"] for item in quarantines}
    results = []
    random_state = seed
    for test in tests:
        if test["test_id"] in quarantined:
            results.append({"test_id": test["test_id"], "status": "passed", "failures": [], "observed": state})
            continue
        failures = []
        for index, operation in enumerate(test["operations"]):
            key = operation["key"]
            if operation["op"] == "set": state[key] = operation["value"]
            elif operation["op"] == "increment": state[key] += operation["amount"]
            elif operation["op"] == "assert_equal" and state[key] != operation["value"]:
                failures.append({"operation": index, "key": key, "expected": operation["value"], "actual": state[key]})
        results.append({"test_id": test["test_id"], "status": "failed" if failures else "passed", "failures": failures, "observed": state})
    return results
