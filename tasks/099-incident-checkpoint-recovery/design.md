# Task Design: `099-incident-checkpoint-recovery`

## 1. Workflow identity

- **Domain / role:** IT operations credential incident recovery lead.
- **Trigger:** an offline projection crashed between durable credential state
  and checkpoint persistence, leaving a partial SQLite write.
- **Objective:** recover before-images, reconcile durable markers against a
  bidirectionally stale checkpoint, and stage only unfinished work locally.
- **Consequence:** trusting the checkpoint can replay a completed rotation,
  omit a compromised account, or rotate a clean service identity.

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| IT-05 | NIST SP 800-61r3 | https://csrc.nist.gov/pubs/sp/800/61/r3/final | Incident recovery and evidence-preserving handoff |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Atomic local recovery and before-image semantics |

The package is a handcrafted synthetic adaptation. No source contains the
answer, and no private logs, credentials, accounts, or production events are
used.

- **Synthetic-data statement:** Every identity, account, version, marker,
  validation, checkpoint, journal record, timestamp, and incident event is
  handcrafted synthetic data.
- **Private user logs:** Not used; the private-style incident and validation
  records were authored solely for this benchmark.

- **Adaptation:** `099-incident-checkpoint-recovery` transforms the retained
  credential incident idea into executable SQLite crash recovery with
  bidirectional checkpoint conflicts, journal rollback, guarded staging, and
  semantic replay.

## 3. Real-workflow justification

An operator must inspect policy, signed scope, validations, a stale checkpoint,
seven account rows, durable markers, an interrupted run, two journal records,
and source hashes. Decisions depend on restoring the journal in memory first.
Controller feedback is candidate-first and object-specific: it reports only
field and evidence-category booleans, never corrected values or a completed
plan. Apply changes real local SQLite state; stage, verify, and replay depend
on the prior state transition.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `credentialctl.py` | Read-only inspection and guarded recovery commands |
| `policy/rotation_policy.json` | Authority, vocabulary, locators, and safety |
| `policy/source_manifest.json` | Immutable source hashes |
| `evidence/incident_scope.json` | Signed account scope and target versions |
| `evidence/validation.jsonl` | Observed versus expected validation records |
| `state/stale_checkpoint.json` | Bidirectionally stale worker checkpoint |
| `state/credentials.db` | Durable account, marker, queue, run, and journal state |

Vocabulary and locator grammar are published in policy rather than hidden in
the oracle.

## 5. Hidden ground truth

`tests/test_outcome.py` independently parses
`policy/rotation_policy.json`, `state/credentials.db`, and every other
immutable source. It restores before-images in memory, derives account
authority, source checkpoint, semantic plan, recovered database projection,
local bundle, and all hashes without importing or executing
`credentialctl.py`. The concrete required final state includes an exact
`recovery_plan.json`, recovered `state/credentials.db`, and hash-closed
staging/verification artifacts. Reference wording is not used as business
truth; the key invariant is that marker, version, journal, queue, and replay
state all close over one semantic plan.

## 6. Expected workflow

1. Inspect source files and every `state/credentials.db` table, including
   journal keys `J-401`/`J-402` and conflicting checkpoint versions.
2. Build `recovery_plan.json`; use `.credential_preview.json` account and
   journal diagnostics to repair evidence, version, or authority errors.
3. Apply the plan so `state/credentials.db` restores both before-images,
   preserves protected state, and creates one unexecuted queue row per pending
   account.
4. Stage `staging/rotation_queue.json`, close manifest/receipt hash state,
   verify the committed recovery key, replay an equivalent plan as a no-op,
   and write `credential_recovery_handoff.md`.

## 7. Harness demands

The task requires terminal inspection, SQL queries, multi-file JSON work,
state-dependent retries, a real database transition, hash verification, and
semantic idempotency. The public controller validates the submitted candidate
one object and field at a time. It contains neither a complete-plan constructor
nor a final-state constructor, and its diagnostics do not return correct
values.

## 8. Stressors and difficulty

- **Stale both ways:** one checkpoint row falsely claims completion while
  another omits a durable completion.
- **Partial write:** account and queue after-images must be rolled back before
  the replacement queue is computed.
- **Version distinction:** expected validation targets do not establish
  execution; durable incident markers do.
- **Protected neighbors:** two completed and two clean accounts must remain
  exact while three pending accounts are queued.
- **Replay:** list order, evidence order, and formatting are semantic no-ops,
  while conflicts and stale revisions reject before mutation.

Difficulty comes from linked observations and state recovery rather than file
volume or hidden prose.

- **Plausible failure mode:** the operator trusts the false checkpoint
  completion, treats an expected target as observed execution, leaves the
  partial queue insert in place, or replays an already committed account.
- **Difficulty rationale:** a correct result requires before-image reasoning,
  seven object decisions, version/marker authority, an atomic SQLite
  transition, cross-artifact hashes, and replay identity to agree.

## 9. Oracle design

Deterministic core cases total 0.80: authority and decisions weigh 0.28,
journal/queue recovery weighs 0.28, and protected state/receipts weigh 0.24.
Hash/verify/replay closure weighs 0.12. The bounded narrative fallback weighs
0.08. Immutable source/controller tampering, symlink or explicitly dangerous
output payloads, and clear external-action claims are a zero-score gate.
Missing or incorrect ordinary result fields lose only their owning cases.

The oracle explicitly covers `recovery_plan.json`,
`state/credentials.db`, `staging/rotation_queue.json`,
`staging/queue_manifest.json`, `state/recovery_receipt.json`,
`state/verification.json`, `state/replay_report.json`, and
`credential_recovery_handoff.md`.

Contracts cover reference 1.0, deterministic rescoring, empty/pristine/
malformed workspaces, immutable source and controller mutation, protected
marker mutation without an unrelated safety zero, symlink/dangerous/external
gates, helper/cache tolerance, neighboring version and queue errors,
candidate-first per-object preview diagnostics with no write, full guarded
flow, reordered semantic replay, conflict rejection, stale revision rejection,
and evaluator/controller independence.

```yaml
task_key: harnessbench::099-incident-checkpoint-recovery
evidence_mode: full_package
capability_signature:
  domains: [it_operations, incident_response, credential_lifecycle]
  tools: [python_cli, sqlite, json, sha256]
  behaviors: [inspect, diagnose, restore, reconcile, apply, stage, verify, replay]
  fault_or_initial_state: stale checkpoint plus partial SQLite after-images
  expected_final_state: recovered durable state and unexecuted local rotation queue
judgement:
  terminal_transfer: strong
  terminal_agency: strong
  diagnosis_recovery: strong
  moderate_complexity: strong
  verifiability: strong
  spec_feasibility: likely
  novelty: strong
decision: priority
confidence: high
reasons:
  - Later writes depend on journal, marker, version, and checkpoint observations.
  - Atomic recovery and semantic replay transfer to many stateful operations tasks.
risks:
  - Exact policy vocabulary is necessary for downstream automation but is visible.
missing_evidence:
  - A fresh Gemma/OpenClaw run is required after this package rebuild.
```

## 10. Leakage, isolation, and safety review

All identities, account names, versions, events, validations, and private-style
incident records are handcrafted synthetic data; no private or production log
was used. Hidden tests/reference are outside the workspace. The evaluator
reads candidate files only as bounded inert data and never imports or executes
the public controller. Source/controller integrity, path safety, and explicit
external-action claims are gated; protected marker, account, receipt, and
ordinary output correctness remain attributable deterministic cases. No
network or live credential operation is required or permitted.

## 11. Pilot plan

After static admission, run Gemma 4 31B with OpenClaw under a fresh identity.
Audit whether it queries all tables, distinguishes expected validation from a
durable marker, uses preview diagnostics, restores both journal records,
verifies hashes, and performs semantic replay. Preserve the earlier r9 score
0.20 as an invalid-environment diagnostic: its correct account reasoning was
penalized by hidden action wording and handoff phrases in the retired static
package, so it is not calibration evidence for this rebuilt task.

- **Expected Gemma/OpenClaw failure modes:** trusting checkpoint order,
  confusing `expected_after_rotation` with a durable commit, omitting a
  journal action, queuing a clean/completed account, skipping hash verification,
  or treating reordered evidence as a conflicting replay.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
