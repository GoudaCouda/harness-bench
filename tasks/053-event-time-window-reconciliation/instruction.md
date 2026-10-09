# Repair event-time window reconciliation

A streaming backfill assigns records by ingestion time, double-counts replays,
and mutates already-final windows. Repair the deterministic local reconciler.

Work only in `repo/`. Read the contract, prior-window snapshots, visible batches,
and public tests. Preserve
`reconcile_event_windows(events, prior_windows, watermark_ms, allowed_lateness_ms, window_ms)`.

Deliver the repaired source, an ordered `repo/window_report.json` for every
visible `case_id`, and `repo/REPAIR_NOTES.md`. Explain event-time assignment,
watermark and exact allowed-lateness boundaries, replay/conflict behavior,
revision rules, exact verification command/result, and risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. Do not edit evidence or claim a stream replay, checkpoint commit, or
production deployment.
