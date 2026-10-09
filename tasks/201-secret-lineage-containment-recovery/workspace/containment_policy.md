# Nimbus synthetic credential containment policy v3.1

This offline exercise follows a revoke/rotate, locate, contain, rewrite,
rescan, and coordinate workflow. A clean current file does not make reachable
history or copied artifacts clean. Rewriting history does not clean existing
clones or caches; record those as residual coordination risk.

## Authority and precedence

- `incident.json` identifies the incident, credential ID, SHA-256 fingerprint,
  detector, replacement *reference*, permitted replacement scope, and owners.
- `repository.db` is the authoritative exported repository graph. `refs` point
  to commits, `commits.parent_id` defines reachability, and `files` stores a
  full tree snapshot for each commit. A ref is impacted if any commit reachable
  through its parent chain contains a byte sequence matching the detector and
  the incident fingerprint.
- `artifact_lineage.json` names local payloads and directed lineage edges.
  A direct detector match propagates only across edges whose
  `payload_inherited` field is `true`. Metadata-only descendants are not secret
  copies. Scan the named local bytes; do not infer exposure from a later ID.
- `distribution_baseline.json` is the protected revision-12 channel baseline;
  `distribution_state.json` is its mutable offline working copy. Detach every
  channel that targets an impacted node by setting `artifact_id` to `null` and
  `status` to `quarantined_pending_rebuild`. Preserve every unaffected channel
  byte-for-byte at the field level.
- `revocation_registry.jsonl` and `quarantine_events.jsonl` are append-only.
  Existing rows must remain in order. The controller owns deterministic event
  IDs and refuses duplicate or contradictory replay.

## Plan schema

Create `containment_plan.json` as one JSON object:

```json
{
  "incident_id": "incident identifier",
  "credential_id": "credential identifier",
  "impacted_refs": ["complete set of refs/heads/... and refs/tags/..."],
  "quarantine_nodes": ["complete propagated payload-node set"],
  "detach_channels": ["complete affected channel-ID set"],
  "rewrite": {
    "replacement_text": "${RELEASE_PUBLISHER_TOKEN}",
    "preserve_ref_names": true,
    "preserve_unaffected_history": true
  },
  "replacement": {
    "secret_ref": "reference from incident.json; never a secret value",
    "scope": ["exact permitted scopes from incident.json"],
    "owner": "owner from incident.json",
    "activate": false
  },
  "evidence": ["local-file#stable-object-or-field locator", "..."]
}
```

Array order is not significant. Evidence must contain at least one local
locator for repository history, each quarantined node, channel selection,
revocation authority, and replacement authority. Locators may use stable IDs,
paths, ref names, or JSON/SQLite field names; they may not contain credential
material.

## Controller-produced state

`rewrite` creates a SQLite repository with the same `refs`, logical commits,
parents, subjects, timestamps, paths, modes, and non-secret bytes. It adds an
`original_commit_id` mapping and changes content-addressed IDs only where a
rewritten ancestor requires it. Every exact incident-token occurrence becomes
`${RELEASE_PUBLISHER_TOKEN}`.

`apply` is a local, idempotent transaction. It appends one revocation event for
the old credential, one staged-not-activated event for the replacement
reference, and one quarantine event per impacted payload node. It creates
`replacement_credential.json` without a `value`, `token`, or plaintext secret.
No local event proves an external provider action.

`verify` independently reopens the rewritten repository, rescans reachable
content, checks distribution closure and append-only ledgers, and binds source
and final artifact SHA-256 values in `recovery_receipt.json`. A second verify
must leave the receipt and every state file byte-identical.
