# Royalty usage allocation recovery handoff

## Intake and canonical event set

The Q2 North usage package was processed as an offline DDEX-like source, not as
an instruction to deliver a statement. The duplicate `USE-100` version 1 rows
were byte-equivalent deliveries and therefore collapsed to one logical event.
For `USE-101`, version 2 superseded the out-of-order version 1 row, so the
canonical statement contains eight events rather than ten physical lines.

## Identifier, rights, and split authority

ISRC `QZAAA2600001` resolves through mapping version 2 to recording `REC-A` and
ISWC `T-100.000.002-0` for both May and June. The US streaming right is active
during those usage dates. `USE-100` occurred before the ownership revision and
therefore uses split version 1 at 60/40; `USE-101` occurred after 1 June and
uses split version 2 at 50/50. The GB download `USE-102` uses its effective
mapping, GB download right, and 70/30 split.

`USE-106` is a same-statement negative adjustment of `USE-100`. It inherits the
target's mapping, rights authority, and split version 1, rather than incorrectly
using the newer split effective on the adjustment date. The signed negative
allocation is -60 units/-6000 cents to RIGHTHOLDER-A and -40 units/-4000 cents
to RIGHTHOLDER-B.

## Quarantines and conservation

Four events remain in local quarantine. `USE-103` has an unknown recording;
`USE-104` has an ambiguous highest-version recording-to-work mapping;
`USE-105` is outside the applicable rights window; and `USE-107` is a
cross-statement adjustment because its target is absent from this statement.
No guess or current-date substitution was made for any of those events.

Allocated events conserve 1530 signed units and 185000 royalty cents.
Quarantined events conserve 950 signed units and 95000 royalty cents. Together
they reconcile to the canonical input totals of 2480 units and 280000 cents.
Each allocated event also conserves its own signed units and cents across its
rightsholder rows.

## Interrupted recovery and closure

The pre-existing journal identified one interrupted partial allocation for
`USE-100`. The guarded apply removed that row inside the same immediate SQLite
transaction that wrote all eight dispositions, the final allocation rows, four
quarantines, one statement run, and the committed journal state. This recovered
the partial work rather than adding a second allocation.

Verification bound the protected source checkpoint, normalized semantic plan,
and logical ledger digest. The receipt is only an internal stage in
`pending_rights_accounting_review`. Semantic replay returned idempotent status;
the database and internal stage receipt were byte-for-byte stable.

No payment was executed. No statement was sent or delivered. No rightsholder
was contacted. The operator used no network service and made no irreversible
external action; accounting and rights reviewers must separately approve any
later business process.
