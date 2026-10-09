# Isolation runner contract

`run_isolated_suite(fixture, tests, seed, quarantines, day)` accepts JSON values.
Fixture is an object whose values may be nested objects/lists/scalars. Every test
has unique `test_id` and an `operations` list. Supported operations are:

- `{"op":"set","key":string,"value":JSON}`
- `{"op":"append","key":string,"value":JSON}` (target must be a list)
- `{"op":"increment","key":string,"amount":integer}` (target integer)
- `{"op":"random_below","key":string,"upper":positive integer}`
- `{"op":"assert_equal","key":string,"value":JSON}`
- `{"op":"assert_not_equal","key":string,"value":JSON}`

Keys address top-level fixture fields. Each test starts from an independent deep
copy, including nested values. Process operations in order. Collect assertion
failures as `{"operation": index, "key": key, "expected": value,
"actual": value}`; for `assert_not_equal`, expected is `{"not": value}`.

Random values use a per-test unsigned 32-bit state: start with FNV-1a over UTF-8
bytes of `"<seed>:<test_id>"` (offset 2166136261, multiply by 16777619 after
XOR, modulo 2^32). For each draw update
`state = (1664525 * state + 1013904223) modulo 2^32`, then use `state % upper`.
Thus reordering tests cannot change their values.

Status is `passed` when there are no failures. Otherwise it is
`quarantined_failed` only when exactly one quarantine exists for that test and
`day <= expires_day`; otherwise `failed`. Quarantine never skips execution or
turns failure into pass. Return results in input order as
`{"test_id", "status", "failures", "observed"}`, where observed is the final
test-local fixture.

Reject malformed roots, duplicate IDs/quarantines, unknown operations, missing
keys, invalid operand types, invalid UTF-8 surrogate IDs, or invalid expiry with
`ValueError`. Inputs are immutable.
