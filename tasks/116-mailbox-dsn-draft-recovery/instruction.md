# Recover an interrupted mailbox DSN and draft reconciliation

You are the mail-operations engineer recovering an offline customer-communications
mailbox after a local reconciliation crashed. The Maildir contains original
messages, copied originals, multipart delivery-status notifications (DSNs), a
duplicate DSN delivery, and DSNs whose claimed linkage is unsafe. The SQLite
journal shows a prepared transaction that changed some local state before the
crash. Reconcile delivery state and local review drafts without sending,
resending, forwarding, deleting source mail, or contacting anyone.

All work is offline in the current workspace. Start with:

```bash
python3 mailctl.py inspect
```

Read the raw `.eml` files in `maildir/cur/`, including their MIME
`message/delivery-status` parts. Identity is based on the original `Message-ID`,
not Maildir filename, file order, subject, or thread label. Deduplicate copied
originals and semantically identical DSNs. A DSN is usable only when its
`Original-Message-ID` names a known original and its final recipient matches
that original. Quarantine orphan, conflicting, or recipient-mismatched DSNs.

Read `evidence/approvals.json` and `evidence/approval_trust.json`. Only an
active-key approval with a valid local signature can authorize a corrected
recipient. A hard bounce with that approval may create a local replacement
draft, but must not send it. Ignore invalid or retired-key approvals. Apply
`policy/recovery_policy.json`. Its `delivery_state_vocabulary`,
`action_vocabulary`, and `delivery_actions` are the complete public vocabulary:
a usable failed DSN is `hard_bounced` whether or not an approval exists, and an
original with no usable DSN is `pending`. Close a delivered item and remove its
stale retry draft; stage one approved replacement after a hard bounce; monitor
a delayed delivery; preserve pending state and any existing local draft when no
usable DSN exists. For an approved replacement, `target_recipient` is the
verified approval's corrected recipient; otherwise it is the original `To`
recipient.

Create `recovery_plan.json` with exactly these top-level fields:

```json
{
  "schema_version": 1,
  "recovery_id": "the policy recovery ID",
  "mailbox_checkpoint": "the evidence checkpoint ID",
  "decisions": [],
  "quarantined_dsn_ids": [],
  "ignored_approval_ids": [],
  "external_messages_sent": false
}
```

Include one decision per unique original `Message-ID`, with exactly:

```text
message_id, thread_id, delivery_state, dsn_ids, action,
target_recipient, approval_id, draft_id, evidence_refs
```

Arrays are sets for comparison. Use the policy vocabulary. A nullable field is
JSON `null`. Evidence references are workspace-relative source paths. A bare
Maildir path and that same path followed by `#message-id=ID`, `#dsn-id=ID`, or
the corresponding underscore spelling are equivalent when the fragment names
the object actually stored in that file. Approval references may use
`evidence/approvals.json#APPROVAL_ID`, `#approval_id=APPROVAL_ID`,
`#approval-id=APPROVAL_ID`, or `#approvals/APPROVAL_ID`. Cite every Maildir copy
that participates in an identity or duplicate-DSN set. No synthetic evidence
locator is required for the absence of a usable DSN. A replacement
`draft_id` is `draft-` followed by the first 12 lowercase hexadecimal characters
of SHA-256 over the compact, sorted-key UTF-8 JSON object containing
`approval_id` and `message_id`.

Use the guarded workflow:

```bash
python3 mailctl.py preview recovery_plan.json
python3 mailctl.py apply recovery_plan.json
python3 mailctl.py verify recovery_plan.json
python3 mailctl.py stage recovery_plan.json
python3 mailctl.py replay recovery_plan.json
```

`preview` validates the MIME identity graph, approval authority, vocabulary,
and offline boundary. On failure it reports each message object and the names of
the mismatching fields, plus categories of missing evidence; it does not print
the correct values. `apply` first rolls back the interrupted prepared journal,
then atomically updates the local delivery projection and draft table. `verify`
writes `state/verification.json`; `stage` writes a local pending-human-review
receipt; `replay` proves that an equivalent plan is a no-op with byte-stable
database and receipt. The stable recovery identity is the pair of recovery ID
and mailbox checkpoint: a semantically equivalent ordering must replay safely,
while changed business decisions under that identity are a conflict.

Finally, write `recovery_handoff.md`. Explain the Message-ID linkage, copied
message and duplicate-DSN handling, quarantines, signed versus ignored
approvals, delivered/bounced/delayed/pending decisions, resulting local drafts,
prepared-journal rollback, verification and replay, and the external-action
boundary.

Keep the controller, Maildir, evidence, policy, source-hash manifest, and
protected initial-state record byte-for-byte unchanged. Do not hand-edit the
SQLite journal or controller-generated artifacts. Do not use the network. No
part of this task authorizes a real message, resend, forward, deletion of source
mail, or customer contact.
