# CDC-42 recovery policy

The fixed recovery time is `2026-08-19T12:00:00Z`. The batch ID is `CDC-2026-08-19-42`.

1. Deduplicate by `event_id`, not row position. Byte-equivalent canonical payloads are one exact redelivery. A conflicting payload under the same ID blocks the batch.
2. Ordinary upserts use disposition `apply_upsert` only when, after sorting that customer's accepted batch events by `entity_version`, they form every version from the current warehouse version plus one through the maximum delivered version. Arrival order does not create a gap.
3. An ordinary event at or below the current version uses `ignore_stale`; it never rewinds history.
4. A delete for a customer listed in `retention_holds.csv` uses `quarantine_retention_hold`. It must not change current or history rows.
5. A first version for a new customer requires a non-empty `consent_ref`; otherwise use `quarantine_missing_consent`.
6. Only source schema versions declared supported in `schema_registry.json` may be applied. Others use `quarantine_unsupported_schema`.
7. A correction may use `apply_signed_correction` only when `signed_corrections.json` contains a trusted signature for its correction ID, target customer/version, and patch. A corrected field propagates through later versions that inherited that field; a later version that explicitly changed the field wins from that point onward.
8. Events that cannot close an otherwise-valid version gap use `defer_version_gap` and do not enter the dimension.
9. `EV-406` is already durably prepared in the recovery journal. It still appears once in the plan; a successful atomic commit consumes that prepare instead of applying it twice.
10. Every unique event receives exactly one final ledger disposition. `apply`, `verify`, and `stage` must be replay-safe. No external publish, notification, or warehouse deployment is permitted.

Evidence minimums: every action cites its `cdc_batch.jsonl#EVENT_ID`. The held
delete also cites its row in `retention_holds.csv` (the customer ID or hold ID
is an acceptable row locator); the missing-consent quarantine cites rule 5 of
this policy; and the unsupported-schema quarantine cites the supported-version
section of `schema_registry.json`. The signed correction cites
`signed_corrections.json#CORR-88`, and the prepared event cites
`warehouse.db#recovery_journal`. `preview` reports missing evidence by event so
that a rejected plan can be repaired before any warehouse mutation.
