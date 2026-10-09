# Recover an interrupted incident-evidence acquisition and containment handoff

Take over synthetic incident `INC-8842` after a local evidence-preservation
projection crashed between two SQLite writes. The snapshot contains applied
before-images, a host whose isolation was already observed before this task, a
compromised session whose disablement is still pending externally, an account
with another clean session, and an ambiguous dual-use-tool alert. Event
deliveries are duplicated, out of sequence, from an adjacent incident, and
linked to both valid and invalid content-addressed evidence.

Everything is offline and synthetic. Begin by using the controller rather than
guessing from filenames:

```bash
python3 incidentctl.py inspect
python3 incidentctl.py query "SELECT * FROM acquisition_requests ORDER BY request_id"
python3 incidentctl.py query "SELECT * FROM containment_state ORDER BY entity_id"
```

Inspect the policy, source manifest, event stream, evidence catalog, acquisition
dependencies, containment state, interrupted recovery run, and complete
before-image journal. De-duplicate an event ID before choosing the highest
sequence in each matching incident stream. Validate every blob against its
content hash and predecessor custody link. Preserve ambiguity when signed
dual-use software and a valid ticket conflict with the observed operator.

Create `recovery_plan.json` with exactly these top-level fields:

```text
schema_version, incident_id, recovery_id, source_checkpoint,
event_dispositions, acquisitions, scope_actions, external_actions_executed
```

- Each event disposition has exactly `delivery_id`, `event_id`, `stream`,
  `sequence`, and `disposition`.
- Each acquisition has exactly `request_id`, `target_type`, `target_id`,
  `blob_id`, `phase`, `depends_on`, `order`, `action`, `custody_state`, and
  `evidence_refs`. Cite each blob with its visible local path or actual
  `sha256:<digest>`; references are not plan identity.
- Each scope action has exactly `entity_type`, `entity_id`, `action`, and
  `boundary`.

Use the vocabulary published in `policy/incident_policy.json`. Acquisition
order follows the published phase order while retaining dependency order.
`external_actions_executed` must remain false.

Run the guarded recovery workflow; do not edit SQLite or generated receipts by
hand:

```bash
python3 incidentctl.py preview recovery_plan.json
python3 incidentctl.py apply recovery_plan.json
python3 incidentctl.py stage recovery_plan.json
python3 incidentctl.py verify recovery_plan.json
python3 incidentctl.py replay recovery_plan.json
```

`preview` reports errors by delivery, request, or entity and performs no state
mutation. `apply` restores every interrupted before-image and commits one local
projection. `stage` creates an offline evidence bundle only. Stable recovery ID,
source checkpoint, and the normalized semantic plan define replay identity:
row order, JSON formatting, evidence-reference order, and equivalent local-path
versus SHA-256 references are no-ops. A conflict under the same identity or a
stale source checkpoint must be rejected without mutation.

Write `containment_handoff.md` explaining event authority, acquisition order,
hash and custody quarantines, the ambiguous dual-use evidence, before-image
recovery, observed host isolation, session-versus-account scope, offline
staging, verification, and replay. Clearly state that this task did not isolate
a host, disable a session or account, delete evidence, clean a system, contact
any party, or execute any external containment.

Do not modify policy, evidence, the controller, protected source state, or
observed external facts. Do not use the network or perform a real containment,
disablement, cleanup, deletion, contact, or notification.
