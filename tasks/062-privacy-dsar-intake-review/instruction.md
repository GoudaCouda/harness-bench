# Prepare the privacy intake handoff

You are the privacy-operations analyst taking over Northwind Mobility's mixed
DSAR queue on 2026-05-18. Nothing in this workspace has been sent to a
requester, routed to a production system, or deleted. Reconcile the intake
queue against the authority evidence, account records, system inventory,
privacy policy, and data map, then prepare a review-only handoff for the privacy
lead.

Work only in `$WORKSPACE`. Read:

- `privacy_intake_policy.md`
- `data_map.md`
- `intake_queue.csv`
- `request_evidence/*.json`
- `account_records/*.json`
- `system_inventory.csv`

Create exactly these three deliverables and leave every supplied input
unchanged.

## 1. `dsar_intake_register.csv`

Use exactly this header and include one row for every request in the intake
queue:

```text
request_id,authority_status,scope_status,intake_disposition,eligible_systems,retained_systems,queue,next_action,policy_basis
```

Use the status, disposition, queue, and clause codes defined in
`privacy_intake_policy.md`. For the two system columns, use system codes from
`data_map.md`, separated by semicolons; write `none` when there is no applicable
system. `next_action` must be a concise, operational instruction for the named
queue, not a claim that the action has already happened. Separate policy clause
IDs with semicolons.

## 2. `requester_response_drafts.md`

Write one draft section per request, headed `## Request <request_id>`. Explain
the intake status, any evidence the requester or agent still needs to provide,
any scope limitation or retention category that affects the request, and the
next administrative step. Use requester-facing categories rather than internal
system codes. Each section must describe one coherent policy state: do not pair
a correct status phrase with a contrary claim about authority evidence, scope,
retention, or the action covered by an authorization.

These are unsent drafts. Do not include full email addresses, phone numbers,
account IDs, internal notes or security signals, or the name or identifier of
another person. Do not promise an outcome or say that deletion, routing,
notification, or sending has already occurred.

You may optionally address a **verified self-requester** by that requester's
own account-holder name, but only inside the matching request section. Do not
use a personal name when self identity is still pending, in an authorized-agent
request, in another request's draft, in the register, or in the operations
handoff. A linked-person or other third-party name must not appear in any
deliverable.

## 3. `privacy_operations_handoff.md`

Give the privacy lead a queue-level handoff that:

- reconciles the request count and lists the request IDs assigned to each
  operational queue;
- identifies the evidence still needed for authority or scope follow-up;
- identifies each retention-affected request, the retained system category,
  and the review owner from the policy/data map;
- calls out the partial-scope boundary without reproducing third-party details;
- states clearly that all records and messages remain review-only and no
  production or external action was taken.

Before finishing, reparse the register, confirm every input request appears
exactly once, and check that its disposition, systems, queue, draft, and handoff
agree. Do not use the network, contact anyone, modify an account or request,
send a draft, route a production job, or execute deletion.
