# Incident INC-8842 offline recovery handoff

The interrupted local run was restored from both before-images before a single
atomic projection. Deliveries were de-duplicated by event ID before sequence
authority was applied; the foreign incident and bad-hash payload were not used.

Volatile memory for `ws-fin-17` precedes its dependent disk snapshot. Each
preserved object is addressed by SHA-256, while the bad hash and broken
predecessor chain remain quarantined. `ws-ops-08` remains ambiguous: its signed
dual-use binary and valid ticket do not resolve the operator mismatch.

The source records show `ws-fin-17` was already isolated before this offline
task. The only pending identity containment is `sess-7x`; it is staged as a
session-level request and is not expanded to account `user-7` or its clean
session. No containment is staged for the ambiguous or clean hosts.

All controller changes are local evidence preservation and offline staging.
No host was isolated, no session or account was disabled, no evidence was
deleted, and no external containment, cleanup, contact, or notification
occurred in this task. Verification closes the bundle digest, database state,
source checkpoint, and semantic replay identity.
