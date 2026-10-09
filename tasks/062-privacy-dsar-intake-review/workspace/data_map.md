# DSAR system and retention data map

The `system_inventory.csv` records which systems currently contain a record for
each account. Absence from the inventory means the system is not present and
must not be added to the intake route.

## DM-1 — Holder-owned systems eligible for deletion review

- `profile_store` — owner: Privacy Fulfillment
- `marketing_prefs` — owner: Lifecycle Operations
- `support_history` — owner: Support Data Operations
- `analytics_events` — owner: Analytics Privacy

Only systems marked `present` in the inventory are eligible. Intake review does
not mean that deletion is permitted or executed; the system owner performs a
later review.

## DM-2 — Current hold mappings

List the mapped system under `retained_systems` only when both the account has
the current hold and the inventory marks the mapped system `present`.

| Account hold | Retained system | Review owner | Requester-facing category |
|---|---|---|---|
| `open_billing_dispute` | `billing_ledger` | Finance Records | billing dispute records |
| `active_chargeback` | `chargeback_casework` | Payments Legal | chargeback records |
| `tax_retention` | `billing_ledger` | Finance Records | records subject to tax retention |
| `legal_hold` | `legal_hold_archive` | Privacy Legal | records subject to legal hold |

## DM-3 — Linked-person systems

`household_links` and `emergency_contact_registry` contain another person's
data. They are never eligible under the account holder's request and must not
be named in requester-facing drafts.
