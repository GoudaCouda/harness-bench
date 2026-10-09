# Audit trail

- Decision `blocked` for `REL-2026-05-CHECKOUT-88` follows `approval_policy.md`: any hard blocker blocks release.
- `RR-DB-REV` maps `approval_policy.md` to `preflight_checks.json#PF-DB-REV` and `rollback_runbook.md#CH-DB-1`.
- `RR-CANARY` maps `approval_policy.md` to `preflight_checks.json#PF-CANARY-ERR` (2.3 percent versus 1.5 percent).
- `RR-SEC` maps `approval_policy.md` to `preflight_checks.json#PF-SEC` and `release_manifest.json#CH-API-1`.
- `RR-FREEZE` maps `approval_policy.md` to `change_calendar.csv#FRZ-2026-05-07` and `release_manifest.json#2026-05-07T03:00:00Z`.
- `RR-INCIDENT` maps `approval_policy.md` to `incident_history.json#INC-2026-04-29-17`.

No production change was made; all actions remain pending.
