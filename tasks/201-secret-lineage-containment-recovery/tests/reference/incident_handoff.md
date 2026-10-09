# INC-114 local containment handoff

Detector DET-REL-7 and `incident.json` bind this response to synthetic credential SYN-CRED-REL-PUB-A. Direct matches occurred in repository commits reachable from main, release/2.7, and build-2026.08.12, in ART-417, and in LOG-418. Payload lineage also carries ART-417 into opaque mirror MIR-417-A; IDX-418 is metadata-only. ART-419 is partially redacted but has no matching fingerprint, ART-420 is clean, and ART-DEMO is a different training fingerprint.

The affected refs were rewritten into `sanitized_repository.db`; exact matches became the environment reference while ref names, logical commits, files, parents, subjects, and the unrelated ops-docs history were preserved. Production and rollback-west were detached and ART-417, LOG-418, and MIR-417-A were quarantined. Nightly, QA, training, IDX-418, ART-419, ART-420, and ART-DEMO were left unchanged.

The append-only local registry now records the old credential as revoked for containment. The replacement is only staged at `vault://synthetic/nimbus/release-publisher@v3`, scoped to `release:publish:nimbus`, owned by release-automation, and not activated. No plaintext replacement was created.

The controller rescan found no incident fingerprint in reachable rewritten history or any distributable payload. It verified preserved history, exact channel closure, append-only events, hashes, and replay stability. Existing developer clones and remote caches remain a coordination risk after a history rewrite; owners must re-clone or clean them before any later authorized publication. This exercise performed no provider revocation, force-push, remote deletion, credential activation, publication, or contact.
