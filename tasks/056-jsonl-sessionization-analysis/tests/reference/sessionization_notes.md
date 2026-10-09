# Sessionization notes

Anonymous identity `a1` is stitched to `U100` when the later login supplies
the durable user id. Exactly 30 minutes of inactivity remains in the same
session; more than 30 minutes creates a new session. The first mapped campaign
is used and a prior non-direct campaign may carry forward to a later session.

Malformed JSON, missing timestamps, unknown event types, bot traffic, and
duplicate event ids are rejected exactly once in the documented precedence.
