# Event reconciliation contract

`reconcile_object_events(objects, events, policy)` is pure and returns exactly
`{"decisions": [...], "objects": [...], "summary": {...}}`.

Objects are sorted uniquely by `(bucket,key)` and use exact fields `bucket`,
`key`, `sequencer`, `state`, `version_id`, `etag`, and `size`. Events use the
sample exact schema and contiguous `arrival_index` starting at zero. Bucket,
key, ID, version, and etag strings are ASCII lowercase tokens (keys may contain
`/` and `.`); sequencers are non-empty lowercase hexadecimal with no fixed
width. Size is non-negative. Present state/create events require etag and may
have positive or zero size; deleted state/delete events require null etag and
zero size.

Policy has exactly `allow_delete_markers`, `require_version_id`, and
`max_key_bytes`. Key length is measured in UTF-8 bytes and all input here is
ASCII. Event names are `ObjectCreated:Put`,
`ObjectCreated:CompleteMultipartUpload`, `ObjectRemoved:Delete`, or
`ObjectRemoved:DeleteMarkerCreated`.

Replay arrival order. An event ID seen earlier with the exact same event
fingerprint is ignored as `duplicate`; the same ID with different content is
blocked as `event_id_conflict`. For a given bucket/key, compare sequencers as
hex integers (equivalent to left-padding the shorter value with zeroes). A
lower value is `stale`; equal value is `duplicate` only when the resulting
object exactly equals the checkpoint, otherwise `sequencer_conflict`.

Before applying a higher sequencer, enforce required version IDs and delete
marker policy. Create applies `upsert`; remove applies `delete`; blocked events
do not advance checkpoints. Decisions have exactly `arrival_index`,
`event_id`, `status`, `action`, and `reason`. Summary has exactly
`event_count`, `applied`, `ignored`, `blocked`, and `object_count`.
