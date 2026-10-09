# Offline calendar delta recovery policy

## Identity and precedence

- A component identity is `UID|master` unless `RECURRENCE-ID` is present; an instance uses `UID|RECURRENCE-ID` and never replaces its series master.
- `SEQUENCE` is monotonic for each component identity. A lower sequence is `ignore_stale`; equal content is `ignore_duplicate`; a conflicting equal sequence is invalid.
- A non-cancelled recurring master is `upsert_master`. A non-cancelled instance is `upsert_override`. A non-recurring component is `upsert_event` when already present and `insert_event` when new.
- `STATUS:CANCELLED` on an instance is `cancel_occurrence`; on a master/standalone component it is `tombstone_event`.

## Time and source authority

- Parse `TZID` with the IANA registry in `timezone_registry.json`, retain the original TZID, and store UTC instants. A value ending in `Z` is UTC.
- Accept page 1 only when its SHA-256, incoming ETag, and outgoing ETag match the manifest and current checkpoint.
- A damaged page may be replaced only by the named fallback whose SHA-256 equals `fallback_sha256`; the fallback incoming ETag must equal page 1's outgoing ETag. Advance only to the fallback cursor and outgoing ETag.
- In `recovery_plan.json`, `fallback.damaged_page` means the manifest's `damaged_path`, not the logical label `page2`; `selected_page` means `fallback_path`; and `expected_etag` means the selected page's outgoing ETag after the accepted chain.

## Evidence locator contract

- Every action must cite the exact accepted ICS component as `accepted ICS path#component_id`.
- Every action must also cite the page-chain authority as `policy/sync_manifest.json#pages.page1` or `policy/sync_manifest.json#pages.page2`, matching the component's accepted page.
- Extra evidence is permitted only when it is another safe locator to an accepted ICS file or the manifest. A path must be relative, must not contain a parent traversal, and must not be a URL or generated output.
- Preview validates only the submitted candidate. Its field and evidence-category diagnostics do not disclose a correct disposition or construct missing actions.

## Transaction and replay

- Recovery is keyed by the stable `recovery_id` plus immutable `source_checkpoint`, not by JSON byte order.
- Restore the prepared page-1 rollback row before applying the complete accepted page chain in one SQLite transaction.
- Semantically equivalent action and evidence ordering is a replay no-op. A changed disposition, source checkpoint, or fallback for an already committed recovery ID is a conflict and must not mutate state.
- Verification and staging remain local. Remote writes, invitations, cancellations, attendee notices, and messages are forbidden.
