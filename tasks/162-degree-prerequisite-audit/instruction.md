# Audit student S-42 against catalog 2026-CS

You are a registrar analyst working with a synthetic, offline record. The audit
must reconcile a current transfer equivalency, an expired unrelated
equivalency, an approved humanities substitution, no-double-count rules, and
prerequisite order.

1. Read `degree_policy.md`; run `python3 degreectl.py transcript S-42`,
   `python3 degreectl.py requirements 2026-CS`, and
   `python3 degreectl.py graph CS-301`.
2. Create `degree_plan.json` with one row per requirement containing
   `requirement`, `status`, `applied_course`, and `evidence_ids`; also include
   `eligible_next_courses` and `unused_courses`.
3. Run `python3 degreectl.py validate degree_plan.json`. Correct any expired
   equivalency, double-count, substitution, or prerequisite failure.
4. Run `python3 degreectl.py finalize degree_plan.json`, which generates
   `degree_audit.json`; then run `python3 degreectl.py verify` to create
   `audit_receipt.json`. Finalize again to prove byte-identical idempotency.
5. Write `advising_handoff.md` explaining satisfied and missing requirements,
   transfer/substitution decisions, CS-301 eligibility, unused coursework,
   verification, and that this is not registration or degree conferral.

Do not edit source records, policy, or the controller. Do not claim enrollment,
registration, graduation, or a live student-record update.
