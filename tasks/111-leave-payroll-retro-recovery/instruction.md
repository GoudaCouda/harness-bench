# Recover a late leave revision across a frozen payroll boundary

You are the HRIS/payroll operations analyst taking over synthetic leave-retro
batch `RB-2026-08-A`. The source payroll was paid and locked. A previous worker
durably inserted one valid reversal, then stopped before finishing the batch.
Later approval records include a cross-midnight correction, an overlapping
leave reclassification, a lower-authority request, and an eligibility conflict.

Work only in `$WORKSPACE`. The SQLite database is the durable operational state;
the JSON evidence and policy files establish approval, time-zone, eligibility,
and immutable-payment rules.

1. Read every file under `policy/` and `evidence/`, then inspect the real state:

   ```bash
   python3 payrollctl.py inspect
   ```

   You may also query `state/hris_payroll.db` with Python's `sqlite3` module.
2. Create `retro_plan.json` with these top-level fields:

   - `schema_version`, `batch_id`, `source_period_id`, `target_period_id`,
     `strategy`, `frozen_source_action`, `approval_boundary`,
     `dispositions`, `adjustments`, and `external_actions_executed`;
   - exactly one disposition per current request, with `request_id`,
     `selected_approval_id`, `selected_revision`, `disposition`, `reason_code`,
     and `evidence`;
   - zero or more adjustment rows containing `adjustment_id`, `request_id`,
     `source_line_id`, `source_revision`, `target_period_id`, `pay_code`, and
     `hours_delta`.

   Use the highest numbered revision per request. Then apply verified signature,
   signer status, payroll-retro authority, eligibility, overlap/reclassification,
   and paid-period rules in the policy order. Compute hours from the signed
   offset-aware interval; do not group by UTC date. Evidence locators must be
   workspace-relative stable record references; `file#record` and
   `file/record` are equivalent when both uniquely name the same visible local
   record. `strategy` is
   `authoritative_revision_retro`; the source action is `preserve_paid_locked`;
   the approval boundary is `staged_pending_payroll_approval`; no external
   action has been executed.
3. Preview the candidate plan without changing durable state:

   ```bash
   python3 payrollctl.py preview --plan retro_plan.json
   ```

   Repair any stated contract error. Preview validates your plan but does not
   select approvals or write adjustment rows for you.
4. Resume the interrupted operation and verify it:

   ```bash
   python3 payrollctl.py apply --plan retro_plan.json
   python3 payrollctl.py verify --plan retro_plan.json
   ```

   Use the controller only; do not update SQLite or `state/batch.json` by hand.
   The already committed adjustment and journal prefix must be reconciled, not
   duplicated. The paid payroll period and every source payroll line are
   immutable.
5. Create `retro_handoff.md`, stage the local batch, and verify the receipt
   twice:

   ```bash
   python3 payrollctl.py stage --plan retro_plan.json
   python3 payrollctl.py verify-stage --plan retro_plan.json
   python3 payrollctl.py verify-stage --plan retro_plan.json
   ```

   A second identical `apply` and `stage` must also be idempotent: no duplicate
   adjustment or journal row, no new revision, and no receipt change.

The handoff must explain the selected signed revisions, local-time interval
math, the overlap reclassification, held authority and eligibility cases, the
recovered partial commit, preservation of paid payroll and unrelated lines,
the target-period stage, hashes/receipt verification, replay result, and the
remaining payroll-approval boundary.

Treat `policy/`, `evidence/`, `payrollctl.py`, and the paid-period contents of
the database as protected inputs. Do not edit or replace them. Do not release
payroll, alter a paid line, issue payment, approve leave, notify anyone, use the
network, or claim any external, financial, or employment action occurred.
