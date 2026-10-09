# Repair consumer-driven API compatibility analysis

A schema gate reports harmless response additions as breaking while missing
required request fields and enum changes for older consumers. Repair the local
analyzer using the explicit contract and consumer evidence.

Work only in `repo/`. Preserve
`assess_compatibility(baseline, candidate, consumers)`. Create the repaired
source, `compatibility_report.json` for visible cases in order, and
`REVIEW_NOTES.md` covering directionality, required/null, enums, consumer scope,
the exact verification command/result, and risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`.
Do not edit schemas, consumer snapshots, or tests, and do not claim an API
deployment or consumer notification.
