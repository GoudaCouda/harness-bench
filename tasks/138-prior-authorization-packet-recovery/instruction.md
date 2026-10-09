# Recover an interrupted offline prior-authorization packet

Recover synthetic case `PA-502` after a local portal projection crashed between
an attempt update and queue completion. The SQLite snapshot also contains an
already-submitted attempt and a denied attempt whose payer-facing facts are
irreversible. Event deliveries are duplicated, out of order, and include a
wrong-member record. Evidence includes stale, unsigned, wrong-member,
unnecessary, and specially sensitive documents.

Everything is offline and synthetic. Start with:

```bash
python3 pa_ctl.py inspect
python3 pa_ctl.py query "SELECT * FROM attempts ORDER BY attempt_id"
python3 pa_ctl.py requirements PA-502
```

Inspect `policy/`, `evidence/`, every relevant SQLite table, source hashes, and
the interrupted journal. De-duplicate by event ID before selecting the highest
sequence per event type. Preserve patient, member, payer, service, diagnosis,
service dates, and authorization window. Select exactly one current, signed,
unexpired, identity-matching document per required type and nothing more.

Create `recovery_plan.json` with exactly these top-level fields:

```text
schema_version, recovery_id, source_checkpoint, case_id,
event_dispositions, packet, attempt_actions, external_actions_executed
```

Each event disposition has exactly `delivery_id`, `event_id`, `event_type`,
`sequence`, and `disposition`. `packet` has exactly `patient_id`, `member_id`,
`payer_id`, `service_code`, `diagnosis_code`, `service_window`,
`authorization_window`, `documents`, and `evidence_refs`. Each attempt action
has exactly `attempt_id`, `action`, and `protected_boundary`. Document IDs and
evidence references are sets for comparison; use stable local `file#record`
locators. Use controller/policy vocabulary verbatim.

Run the guarded workflow; do not hand-edit SQLite or generated artifacts:

```bash
python3 pa_ctl.py preview recovery_plan.json
python3 pa_ctl.py apply recovery_plan.json
python3 pa_ctl.py stage recovery_plan.json
python3 pa_ctl.py verify recovery_plan.json
python3 pa_ctl.py replay recovery_plan.json
```

`apply` restores all interrupted before-images and commits one atomic local
projection. `stage` creates a local packet, manifest, and receipt only. Stable
recovery ID, source checkpoint, and normalized semantic plan define replay
identity: reordered events, attempts, documents, evidence references, or JSON
formatting are equivalent no-ops; conflicting content under that identity and
stale checkpoints must be rejected without mutation.

Write `authorization_handoff.md` explaining event ordering, identity and
minimum-necessary evidence decisions, exclusions, service/authorization
windows, before-image recovery, submitted and denied boundaries, hash closure,
and replay. State that no payer transmission, clinical or coverage decision,
patient notification, scheduling, or external contact occurred.

Do not modify policy, evidence, controller, or protected source fields. Do not
use the network or represent an external action as completed.
