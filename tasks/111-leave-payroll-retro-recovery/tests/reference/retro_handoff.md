# Leave/payroll retro recovery handoff

Batch RB-2026-08-A uses the highest signed revisions APR-9001-R2 and
APR-9002-R3 from the active payroll HR director key. LR-9001 is a
cross-midnight America/Los_Angeles interval from 22:00 to 02:00, yielding four
local signed hours rather than a UTC-date grouping. Its paid eight-hour PTO
line is preserved and offset prospectively with a -8 PTO reversal and +4 SICK
entry. LR-9002 is an overlapping same-interval reclassification: the paid
eight-hour PTO line remains immutable while -8 PTO and +8 PFL are staged.

LR-9003 is held because the line-manager credential has schedule-review scope,
not leave-retro authority. LR-9004 is held because its July 15 local start is
before the August 1 eligibility date even though the HR signature is valid.
Neither held request produces a payroll adjustment.

The prior worker's partial-commit checkpoint contained RA-9001-REV-PTO-R2 and
journal sequence 1. The controller reconciled that prefix, appended the other three entries once, and
closed recovery revision 2 without duplicating the reversal. All source-period
rows, PAYEXP-2026-07-A, and unrelated PL-KEEP remain unchanged. The adjustment,
journal, frozen-payroll, semantic-plan, and stage hashes close across SQLite,
.retro_apply_state.json, state/batch.json, and the stage receipt. Repeated
apply, stage, and receipt verification are idempotent.

The batch is only staged into target period PP-2026-08-A with payroll approval
still pending. No payroll was released, no payment was issued, no leave was
approved, and no employee or manager was notified. A payroll approver must
review the local receipt before any external or financial action.
