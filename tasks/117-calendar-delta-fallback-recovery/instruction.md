# Recover an interrupted RFC 5545 calendar sync

You are the calendar synchronization operator for collection `finance-operations`. A local CalDAV-style replica stopped after preparing page 1 of incremental recovery `CALSYNC-FINANCE-20260819-42`. Page 2 in the cache is truncated. An offline fallback exists, but it may be used only if its checksum and ETag chain satisfy the published manifest.

Work only inside `$WORKSPACE`; every remote service is offline. Start with `python3 syncctl.py --help`, then inspect the SQLite checkpoint and all local evidence:

- `state/calendar.db`
- `evidence/page1.ics`
- `evidence/page2.part`
- `evidence/page2_recovery.ics`
- `policy/sync_manifest.json`
- `policy/recovery_policy.md`
- `policy/timezone_registry.json`

Do not edit the controller, database by hand, or evidence/policy files. Use direct read-only SQLite and text inspection as needed.

Create `recovery_plan.json` with:

- `schema_version`: `1`
- `recovery_id` and `collection_id` from the local checkpoint/manifest
- `source_checkpoint`: the manifest-bound immutable checkpoint
- `fallback`: an object with `damaged_page`, `selected_page`, `selected_sha256`, `expected_etag`, and `reason`
- `actions`: exactly one object per unique RFC 5545 component in the two accepted pages, with `component_id`, `disposition`, and a non-empty `evidence_refs` list
- `external_calendar_write_executed`: `false`

`component_id` is `UID|master` for a master/standalone VEVENT and `UID|RECURRENCE-ID` for an instance. Use only policy dispositions. Treat `UID`, `RECURRENCE-ID`, and `SEQUENCE` as semantic identities: recurring overrides and cancellations must not overwrite their master, and a stale component must not replace a newer local sequence. Convert zoned times with the supplied IANA registry; do not strip `TZID` or treat local wall time as UTC. Evidence references must be safe local locators, never generated output, a URL, absolute path, or parent path.

The fallback fields name concrete manifest values, not page labels:

- `damaged_page` is the `pages.page2.damaged_path` path;
- `selected_page` is the `pages.page2.fallback_path` path;
- `selected_sha256` is the fallback file's published SHA-256; and
- `expected_etag` is the accepted fallback page's outgoing ETag, the ETag to which the local checkpoint will advance. The incoming chain is checked separately by comparing page 1's outgoing ETag with page 2's incoming ETag.

Every action must cite two evidence categories: its corresponding accepted ICS component locator (for example, `evidence/page1.ics#UID|master`) and `policy/sync_manifest.json` at the relevant page object. Preview reports candidate-field validity and missing evidence categories; it does not reveal the correct disposition or assemble a plan for you.

Then run the stateful workflow:

1. `python3 syncctl.py preview recovery_plan.json`
2. `python3 syncctl.py apply recovery_plan.json`
3. `python3 syncctl.py verify`
4. `python3 syncctl.py stage recovery_plan.json`
5. `python3 syncctl.py replay recovery_plan.json`

The apply must atomically recover the prepared journal and mutate the real SQLite replica. Replay of the same semantic plan must be a no-op even when action or evidence-reference order changes; a conflicting plan for the same recovery identity must be rejected.

Required final artifacts:

- modified `state/calendar.db`
- `recovery_plan.json`
- `.calendar_preview.json`
- `state/calendar_verification.json`
- `state/recovery_receipt.json`
- `state/replay_report.json`
- `recovery_handoff.md`

The handoff must explain checksum/ETag fallback authorization, interrupted-journal recovery, master versus `RECURRENCE-ID` decisions, cancellation/tombstone handling, stale-sequence handling, timezone conversion, stable replay identity, verification, and that no remote calendar write, invitation, cancellation notice, or attendee message occurred.

Keep every supplied source byte-for-byte unchanged except `state/calendar.db`. Do not create a substitute database or forge controller receipts.
