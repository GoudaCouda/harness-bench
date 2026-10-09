# Task Design: `138-prior-authorization-packet-recovery`

## 1. Workflow identity

- **Domain / role:** healthcare prior-authorization operations specialist.
- **Trigger:** a local projection crashed between attempt and queue writes.
- **Objective:** reconcile authoritative events and minimum-necessary evidence,
  restore before-images, and stage one offline packet without reopening history.
- **Consequence:** an identity mismatch, sensitive disclosure, or changed payer
  boundary can route the wrong evidence or falsify submission history.

## 2. Idea provenance

The workflow adapts concepts from the CMS electronic prior-authorization
overview and SQLite transaction recovery. The source-to-task adaptation turns
public workflow concepts into a deterministic offline state machine; no source
provides the answer.

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| HEALTH-PA-01 | CMS electronic prior authorization overview | https://www.cms.gov/priorities/electronic-prior-authorization/overview | Packet and administrative workflow context. |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Atomic projection and journal recovery. |

- **Adaptation:** identity, evidence minimization, event reconciliation, and
  SQLite recovery are combined in a synthetic offline portal snapshot.
- **Synthetic-data statement:** all patients, members, payers, documents,
  attempts, dates, events, hashes, and identifiers are synthetic.
- **Private user logs:** not used.

## 3. Real-workflow justification

The agent must inspect policy, hashed evidence, out-of-order events, and several
SQLite tables before constructing a plan. Controller feedback is object-specific;
apply restores an interrupted journal and commits dependent rows atomically.
Later actions depend on observed identity, sequencing, and before-images.

## 4. Agent-visible inputs

Policy and source manifest, document records and files, JSONL events, an
interrupted `state/portal.db`, and a read-only query plus guarded
preview/apply/stage/verify/replay controller are visible.

## 5. Hidden ground truth

`tests/test_outcome.py` independently derives current event authority, evidence
eligibility, source checkpoint, protected attempts, exact SQLite projection,
and artifact hashes without importing or executing `pa_ctl.py`. The required
final workspace state includes the recovered `state/portal.db`, one local queue
packet, restored journal entries, preserved submitted/denied attempts, and
hash-bound verification and replay artifacts.

## 6. Expected workflow

1. Inspect `policy/`, `evidence/events.jsonl`, documents, and every relevant
   table in `state/portal.db`; query attempts and journal before-images.
2. Create and repair `recovery_plan.json` using `.pa_preview.json` diagnostics,
   then atomically apply the exact source checkpoint and semantic plan.
3. Stage the local packet and manifest, verify state/hash closure, replay an
   equivalent plan as a no-op, and write `authorization_handoff.md`.

Deterministic core cases total 0.80. Closure weighs 0.12 and the bounded handoff
fallback weighs at most 0.08; source/protected-state safety is a zero-score gate.

## 7. Harness demands

Contracts cover reference 1.0, determinism, empty/pristine/malformed candidates,
source mutation, identity and evidence neighboring errors, protected-record
tampering, preview no-mutation, equivalent replay, conflict and stale rejection,
evaluator independence, hash closure, and semantic input construction.

## 8. Stressors and difficulty

- **Plausible failure mode:** trust delivery order, accept a wrong member, include
  a newer psychotherapy note, overwrite an already-submitted payer reference,
  or replay reordered business-equivalent JSON as a new revision.
- **Difficulty rationale:** identity authority, event de-duplication/sequence,
  current signed least-necessary evidence, temporal windows, journal recovery,
  immutable boundaries, and cross-artifact hashes must agree.

No live payer, credentials, clinical judgment, notification, or network is
needed. The oracle proves package feasibility, not model success.

## 9. Oracle design

The oracle explicitly covers `recovery_plan.json`, `.pa_preview.json`,
`state/portal.db`, `staging/prior_auth_packet.json`,
`staging/packet_manifest.json`, `state/recovery_receipt.json`,
`state/verification.json`, `state/replay_report.json`, and
`authorization_handoff.md`. Reference is 1.0; empty, pristine, and malformed are
0.0; semantic fallback is at most 0.08.

```yaml
task_key: harnessbench::138-prior-authorization-packet-recovery
evidence_mode: full_package
capability_signature:
  domains: [business_operations, healthcare_administration]
  tools: [python_cli, sqlite, json, sha256]
  behaviors: [inspect, reconcile, minimize, recover, stage, verify, replay]
  fault_or_initial_state: duplicate/out-of-order events and interrupted SQLite projection
  expected_final_state: one exact offline packet with preserved payer-facing history
judgement:
  terminal_transfer: strong
  terminal_agency: strong
  diagnosis_recovery: strong
  moderate_complexity: strong
  verifiability: strong
  spec_feasibility: likely
  novelty: useful
decision: priority
confidence: high
reasons:
  - Each write depends on evidence, event, identity, and journal observations.
  - Semantic replay and irreversible boundaries transfer beyond healthcare.
risks:
  - Dense identity and evidence records require careful local inspection.
missing_evidence:
  - Real Gemma/OpenClaw calibration remains pending.
```

## 10. Leakage, isolation, and safety review

All data is synthetic. Reference and hidden evaluator remain outside the agent
workspace. The evaluator rejects source mutation, protected-history changes,
unsafe database shapes, unknown or linked paths, and affirmative
external-action claims. The public controller validates the submitted plan one
object and field at a time; it has no callable constructor that returns the
complete plan or final state, and failed preview feedback names only check
categories rather than corrected values. Small regular `.py`/`.sql` analysis
helpers and ordinary Python bytecode caches are diagnostic-neutral.

## 11. Pilot plan

Run Gemma 4 31B plus OpenClaw after static admission. Audit inspection depth,
query use, first-write timing, preview repairs, event/evidence decisions, journal
recovery, protected boundaries, stage hashes, and replay.

- **Expected Gemma/OpenClaw failure modes:** following delivery order, selecting
  sensitive or wrong-member evidence, skipping journal restoration, altering a
  payer reference, stale checkpoint use, or formatting-dependent replay.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
