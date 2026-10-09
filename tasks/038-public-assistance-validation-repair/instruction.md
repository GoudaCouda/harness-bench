# Repair a Public Assistance payment-validation sample

You are a disaster-grant analyst performing an offline Validate As You Go-style review for the synthetic Pine County Public Works payment request. The five sampled cost lines cross force-account labor, contracted debris work, equipment rental, and emergency supplies. Evidence arrived from several systems and includes a superseded invoice, a missing approval, an unapplied vendor credit, an insurance allocation, and another federal award.

Work only inside `$WORKSPACE`. Do not use the network. Treat `evidence/`, `policy/`, `grant_lib.py`, and `grantctl.py` as immutable. The only existing file you may modify is `state/payment_request.json`, and you must transition it through `grantctl.py` rather than editing it directly.

Begin with `python3 grantctl.py --help`, `status`, `sample`, and targeted `line --id <line-id>` inspection. Reconcile records by stable IDs and policy authority, not filename order or a single aggregate total.

Create:

- `work/line_review.json`
- `work/exception_register.json`
- `work/validation_receipt.json` through the protected controller
- the policy-correct final `state/payment_request.json`
- `work/grant_handoff.md`

`line_review.json` must contain `request_id`, `policy_version`, and a top-level
`lines` array with exactly one row per sampled line. Each row needs `line_id`,
`cost_type`, `claimed_amount`, `validated_gross`, `correction_source` (or
`null`), `reductions` (an array of keyed rows with `type`, `source_id`, and `amount`; use an empty array when there is no reduction),
`net_eligible`, `status`, `reason`, and `evidence_ids`. Use one of the
controller's workflow states for `status`: `ready`, `ready_with_reduction`,
`hold_documentation`, or `excluded_duplicate_benefit`. Record the gross amount
before reductions or exclusions in `validated_gross`; the disposition belongs
in `net_eligible`, `reductions`, and `status`.

`exception_register.json` must contain the same `request_id` and
`policy_version`, a `holds` row for each unresolved documentation condition,
and an `exclusions` row for each cost that cannot enter this request because of
a duplication or other policy exclusion. A hold row uses `line_id`,
`exception_type`, `amount`, `missing_evidence`, and `requested_action`; an
exclusion row uses `line_id`, `exception_type`, `amount`, `source_id`, and
`requested_action`. Use `missing_supervisor_approval` for the documentation
exception type and `duplicate_federal_benefit` for the duplication exception
type; `requested_action` is concise free prose. Derive the values from the
evidence rather than copying a prose label into every field. Do not invent an
approval or edit source evidence to eliminate an exception.

Use the controller feedback:

- `python3 grantctl.py validate --review work/line_review.json --exceptions work/exception_register.json`
- `python3 grantctl.py stage --review work/line_review.json --exceptions work/exception_register.json`
- `python3 grantctl.py replay --review work/line_review.json --exceptions work/exception_register.json`

Run `replay` twice and verify that the request and receipt bytes are unchanged. The allowed final state is staged locally for review; this task must not disburse, post, submit, notify, or claim an external action.

In `work/grant_handoff.md`, explain every line outcome, authoritative correction, insurance/credit/other-award treatment, held-document request, control totals, replay result, and next actions. State explicitly that this is an offline synthetic validation, the request is staged but not disbursed or submitted, and no external communication occurred.
