# Recover an Interrupted Product Recall and Stop-Sale Staging Transaction

You are the product-safety operations coordinator recovering recall
`RC-2026-0417`. Its local worker stopped after durably preparing one shipment
event. Since then, a signed scope revision superseded the earlier scope, and an
out-of-order feed was redelivered with an exact duplicate and an unknown
shipment. The local database also contains a mixed lot, a verified descendant
batch, an out-of-window lot, and an unresolved parent batch.

Work only inside `$WORKSPACE`. External systems are offline. Read all declared
sources before deciding anything:

- `recall.db`
- `recall_checkpoint.json`
- `recall_seed.sql`
- `signed_scope_revisions.json`
- `shipment_events.jsonl`
- `recall_policy.md`

`recallctl.py` is the local recovery controller. Start with
`python3 recallctl.py --help`, inspect the database through its `inspect` and
read-only `query` commands, and do not edit the controller or evidence files.

Create `recall_plan.json` with these top-level fields:

- `schema_version`: `1`
- `recall_id`
- `source_state_sha256`: the immutable source digest published in the checkpoint
- `scope_revision_id`: the controlling trusted signed revision
- `lot_actions`: exactly one object per source lot, with `lot_id`,
  `disposition`, and a non-empty `evidence_refs` list
- `event_actions`: exactly one object per unique `event_id`, with `event_id`,
  `disposition`, and a non-empty `evidence_refs` list
- `external_actions_executed`: `false`

Use only dispositions defined by `recall_policy.md`. Each action must cite its
database entity, the applicable visible scope/event source, and any policy
section needed to support the decision. Evidence must be a local locator such
as `recall.db#lots/LOT-X`; do not cite outputs, tests, URLs, absolute paths, or
parent paths. For an event whose shipment is absent, cite the event and policy;
do not invent a database locator for the nonexistent shipment. Policy heading
locators are case/spacing/hyphen insensitive, and all of
`signed_scope_revisions.json#SCOPE-02`, `#revisions/SCOPE-02`, and `#revisions`
identify the controlling revision when `scope_revision_id` is `SCOPE-02`.

Then complete the executable workflow:

1. `python3 recallctl.py preview recall_plan.json`
2. `python3 recallctl.py apply recall_plan.json`
3. reorder the two action lists and their evidence lists without changing their
   business meaning, run `apply` again, and confirm an idempotent no-op
4. `python3 recallctl.py verify recall_plan.json`
5. create `recall_handoff.md`
6. `python3 recallctl.py stage recall_plan.json`
7. run `stage` again and confirm the local receipt is unchanged

Required final artifacts:

- modified `recall.db`
- `recall_plan.json`
- `recall_verification.json`
- `recall_stage_receipt.json`
- `recall_handoff.md`

The handoff must explain signed revision precedence; direct, mixed, descendant,
out-of-window, and unresolved genealogy; every feed disposition; final lot,
inventory, shipment, and channel state; interrupted-journal recovery;
equivalent replay; conservation checks; and the offline external-action
boundary.

Do not replace or directly edit the database. Do not forge controller receipts.
Keep the seed, checkpoint, revisions, event feed, policy, hashes, and controller
byte-for-byte unchanged. Do not send notices, execute a real stop-sale, reroute
shipments, refund, repair, or perform any other external channel action.
