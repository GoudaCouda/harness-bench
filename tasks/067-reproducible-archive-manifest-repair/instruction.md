# Repair a reproducible release-archive manifest

Two release builds from different work directories produce different archive
metadata despite identical content. Repair the canonical member planner used
before the archive writer runs.

Work only in `repo/`. Preserve
`canonical_archive_manifest(entries, source_date_epoch, build_root)`. Read the
contract, broken source, visible incidents, and public tests.

Deliver repaired `repo/src/archive_manifest.py`, ordered
`repo/archive_report.json` with every visible `case_id` and exact result, and
`repo/REPAIR_NOTES.md`. Explain build-root stripping, `SOURCE_DATE_EPOCH`, ZIP
timestamp bounds/rounding, stable ordering, normalized modes, duplicate and
unsafe member rejection, exact verification, and residual writer risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. Do not edit evidence, build an external artifact, publish, or deploy.
