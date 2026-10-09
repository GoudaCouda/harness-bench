# Repair S3 event reconciliation

An object-index worker trusts notification arrival time, so duplicate and
out-of-order S3 events can resurrect deleted objects or roll back metadata.
Work only in `/workspace/repo`.

Read `docs/event_contract.md`, inspect initial objects, events, policy, runner,
and public tests, then repair `src/event_reconciler.py` as a general pure
implementation. Run public tests and `python bin/reconcile_events.py`; re-parse
all three files in `out/`. Write `EVENT_NOTES.md` covering at-least-once and
unordered delivery, same-key sequencer comparison and hex padding, duplicate
fingerprints, event-ID/sequencer conflicts, stale events, versions, delete
markers, sequential checkpoint updates, validation, commands/results, and the
offline/no-AWS boundary.

Do not access S3, consume a queue, mutate objects, acknowledge events, or claim
production reconciliation.
