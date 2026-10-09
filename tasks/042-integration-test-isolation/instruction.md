# Repair integration-test isolation

A lightweight local integration runner leaks fixture state between tests, uses
order-dependent randomness, and keeps expired quarantines suppressing genuine
regressions. Repair it without hiding failures.

Work only in `repo/`. Preserve
`run_isolated_suite(fixture, tests, seed, quarantines, day)`. Implement the
contract, create `isolation_report.json` for visible suites in order, and write
`REPAIR_NOTES.md` explaining isolation, stable seeding, quarantine expiry,
regression visibility, exact verification command/result, and risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`.
Do not edit visible suites, contract, or tests; do not claim CI configuration or
quarantine records were changed externally.
