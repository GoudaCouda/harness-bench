# S3 event reconciliation handoff

S3 notifications are at-least-once and unordered, so arrival time is retained
only as evidence and never used to roll an object forward. Sequencers are
compared only for the same key. They are hexadecimal values of variable width:
left-padding the shorter value with zeroes (or integer hex comparison) makes
`100` newer than `ff`. Each applied event immediately updates that per-object
checkpoint before the next arrival is evaluated.

The reconciler fingerprints every event ID. An exact redelivery is an ignored
duplicate; reuse of the event ID with different content is a conflict and is
quarantined. A lower sequencer is stale. At an equal sequencer, only an object
payload identical to the checkpoint is duplicate evidence; any create/delete,
version, etag, or size disagreement is a sequencer conflict. Higher events
still pass the version ID requirement and delete marker policy before applying.
Blocked evidence never advances a checkpoint, so later events compare with the
last trusted state.

Verification passed with `python -m unittest discover -s tests -v` and
`python bin/reconcile_events.py`. I parsed decisions, objects, and summary:
six events produced two applied, two ignored, and two blocked outcomes; two
object checkpoints remain, with `photos/a.jpg` deleted at `0d`. This was an
offline, no-AWS replay. I did not access S3, consume or acknowledge a queue,
mutate an object, or claim production reconciliation.
