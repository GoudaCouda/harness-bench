# Task Design: `001-meeting-summary`

## 1. Workflow identity

This task measures whether an agent can recover an interrupted DNSSEC rollover
staging transaction by reconciling key inventory, DNS observations, parent DS
observations, zone serials, a stale checkpoint, and SQLite before-images; then
commit an idempotent local-only queue without signing or publishing DNS.

- **Domain / role:** IT operations, DNS/DNSSEC operations engineer.
- **Trigger:** offline staging crashed between durable writes and checkpointing.
- **Consequence:** trusting the checkpoint can retire a KSK before parent DS
  propagation, activate an under-dwelled ZSK, or preserve a partial queue write.

## 2. Idea provenance

| Source ID | Source | URL | Adaptation |
|---|---|---|---|
| RFC-6781 | DNSSEC Operational Practices, Version 2 | https://www.rfc-editor.org/rfc/rfc6781 | KSK/ZSK rollover sequencing and operational safeguards |
| RFC-7583 | DNSSEC Key Rollover Timing Considerations | https://www.rfc-editor.org/rfc/rfc7583 | Publication dwell and propagation reasoning |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Local atomic recovery and before-image semantics |

All zones use the reserved `.example` namespace; public keys, observations,
timestamps, and incidents are synthetic. No source contains fixture answers.

- **Private user logs:** none; no private user or production logs were used.
- **Synthetic-data statement:** all zones, keys, observations, checkpoints, and
  SQLite records are handcrafted synthetic fixtures.

- **Adaptation:** the retired static meeting-summary task is replaced by an
  executable DNSSEC crash-recovery workflow that adapts public rollover timing
  guidance and SQLite transaction semantics to synthetic local state.

## 3. Real-workflow justification

The retired task 001 was a static meeting summary overlapping task 012. This
replacement keeps only the broad need for an auditable handoff. It changes the
role, trigger, authoritative inputs, executable tools, state transition,
feedback, and downstream state.

The nearest portfolio mechanisms are task 099 (SQLite crash recovery), task
101 (PKI trust-store rotation), and task 091 (service endpoint repair). Task 001
differs from each across at least four dimensions: DNSSEC KSK/ZSK role-specific
rules, zone/key/DS/RRSIG evidence, serial preservation, parent-versus-child
authority, an offline DNS change queue, and no-publish verification. Its main
information gain is separating KSK parent-DS propagation from ZSK DNSKEY/RRSIG
prepublication inside a recoverable transaction.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `dnssecctl.py` | inspect, read-only SQL, object-diagnostic preview, guarded apply/stage/verify/replay |
| `policy/rollover_policy.json` | timing, probes, safety, schema, vocabulary, locator grammar |
| `evidence/key_inventory.json` | role and old/new key identity per zone |
| `evidence/parent_ds_observations.jsonl` | three-probe parent DS snapshots for KSKs |
| `evidence/dns_observations.jsonl` | DNSKEY dwell, RRSIG coverage, and expiry |
| `zones/*.zone`, `keys/*.key` | real text zone snapshots and synthetic public DNSKEY records |
| `state/stale_checkpoint.json` | deliberately wrong phase/queue claims in both directions |
| `state/dnssec.db` | zones, key state, queue, receipts, runs, journal, and counters |

The intended loop is inspect sources and all tables, draft a candidate-first
plan, consume per-zone preview feedback, apply transactional rollback and queue
rebuild, stage hash-closed local artifacts, independently verify, and replay an
equivalent reordered plan.

## 5. Hidden ground truth

- `alpha.example`: KSK DNSKEY/RRSIG exists, but every parent probe has old DS
  only; monitor double-sign instead of trusting the checkpoint.
- `bravo.example`: three-probe old+new DS quorum has exceeded dwell; stage old
  KSK retirement locally.
- `golf.example`: parent probes conflict; preserve double-sign and monitor.
- `charlie.example`: ZSK prepublication dwell is too short despite key presence.
- `delta.example`: ZSK dwell and new-key RRSIG coverage are valid; stage activation.
- `echo.example`: recover the partial zone/queue before-images, then hold because
  signature expiry violates the safety window.
- `foxtrot.example`: preserve an unrelated zone.

Difficulty comes from role-specific authority, temporal thresholds, stale
state, a partial commit, exact protected-state preservation, transaction/hash
closure, and semantic replay—not hidden enum spellings or output bulk.

The hidden evaluator independently reconstructs the recovered pre-transaction
zone and queue state from `state/dnssec.db` before-images while reading
`policy/rollover_policy.json`, `evidence/key_inventory.json`, both observation
streams, `state/stale_checkpoint.json`, `zones/*.zone`, and `keys/*.key`. It
recomputes the source
checkpoint, role-specific decisions, local queue, receipts, semantic digests,
bundle hashes, and replay closure directly from source evidence; it neither
imports the controller nor treats the reference as business truth.

The required final workspace state includes `rollover_recovery.json`, a
recovered `state/dnssec.db`, exact local staging and receipt files, verification
and replay reports, and `dnssec_recovery_handoff.md`; all serial/key facts stay
at their recovered source values and all queued actions remain unexecuted.

## 6. Expected workflow

1. Inspect `policy/rollover_policy.json`, `zones/*.zone`, `keys/*.key`, both
   observation streams, and every table in `state/dnssec.db`.
2. Recover `J-DNS-801` and `J-DNS-802` in reasoning, write
   `rollover_recovery.json`, and submit it to `dnssecctl.py preview`.
3. Correct per-zone KSK/ZSK/serial/evidence failures in `.dnssec_preview.json`
   without receiving a completed answer row from the controller.
4. Apply the rollback and atomic `staging_queue` transaction in
   `state/dnssec.db`.
5. Stage `staging/dnssec_change_queue.json`, independently verify hashes,
   reorder the semantically equivalent plan, prove replay is a no-op, and write
   `dnssec_recovery_handoff.md`.

## 7. Harness demands

The public controller has no `derive`, `target`, `expected`, `build`,
`reference`, or one-shot final-plan export. It validates a submitted row against
visible inputs and returns only the zone plus failed field/evidence category;
it never returns a correct row or plan. `inspect` exposes the stable source
checkpoint and identities, not business decisions. Apply consumes only a fully
validated candidate and stages its local actions.

The contract performs AST/export review and seed mutation. Reading or importing
the module cannot emit the reference plan. Hidden evaluator logic independently
parses every authoritative source and SQLite before-image without importing or
executing the controller.

## 8. Stressors and difficulty

The natural stressors are a checkpoint that is ahead for some zones and behind
for another, two partial writes, KSK observations split across parent probes,
ZSK evidence with independent dwell and signature-expiry failures, a protected
unrelated zone, and a stable recovery identity that must distinguish equivalent
serialization from a semantic conflict.

- **Plausible failure mode:** an operator trusts the checkpoint, treats child
  DNSKEY presence as parent DS propagation, fails to restore echo's serial, or
  queues a ZSK whose signatures expire inside the policy window.
- **Difficulty rationale:** success requires seven linked decisions across two
  key-role algorithms, multiple temporal observations, journal recovery, an
  atomic SQLite transition, cross-artifact hashes, and semantic replay.

## 9. Oracle design

Deterministic core totals 0.80: role-specific zone decisions weigh 0.30,
journal/queue recovery 0.27, and protected DNS state/receipts 0.23. Hash,
verification, and semantic replay weigh 0.12. Bounded handoff semantics weigh
0.08. Source mutation, affirmative execution flags, or unambiguously positive
external-action claims fail the zero-weight safety gate. Missing closure
artifacts and incorrect protected-state projections remain attributable scored
failures; they do not masquerade as safety violations.

The oracle explicitly covers `rollover_recovery.json`, `state/dnssec.db`,
`staging/dnssec_change_queue.json`, `staging/queue_manifest.json`,
`state/recovery_receipt.json`, `state/verification.json`,
`state/replay_report.json`, and `dnssec_recovery_handoff.md`.

The closest correct solution may reorder decisions, journals, and evidence or
use the published `#SOA` equivalent zone locator. Closest wrong solutions
include treating DNSKEY presence as KSK parent propagation, applying parent DS
logic to ZSKs, ignoring signature expiry, failing to restore echo's serial, or
replaying the same recovery under a conflicting semantic plan.

Contracts cover reference 1.0, deterministic repeatability, empty/pristine/
malformed states, every core mutation, policy/source changes, normal helper and
runtime cache tolerance, preview no-write and object diagnostics, equivalent
locator/order replay, conflict and stale no-write, protected neighbor state,
controller export/AST leakage, seed mutation, and bounded semantic builder
fail-closed behavior. Focused oracle targets are 0/0/0/1.

```yaml
task_key: harnessbench::001-meeting-summary
evidence_mode: full_package
capability_signature:
  domains: [it_operations, dnssec, pki_operations]
  tools: [python_cli, sqlite, dns_zone_files, jsonl, sha256]
  behaviors: [inspect, reconcile, diagnose, rollback, apply, stage, verify, replay]
  fault_or_initial_state: stale checkpoint plus partial zone and queue writes
  expected_final_state: restored DNS state and an unexecuted local rollover queue
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
  - Later mutations depend on role-specific observation and before-image recovery.
  - DNSSEC evidence authority and transaction replay transfer to stateful operations.
risks:
  - DNSSEC terminology is specialized, but every scored vocabulary and threshold is visible.
missing_evidence:
  - A fresh Gemma 4 31B plus OpenClaw pilot is required after package freeze.
```

## 10. Leakage, isolation, and safety review

The task is offline, synthetic, and local-only. The evaluator reads candidate
artifacts as bounded data. Source hashes, zone/key state, system publish
counters, archived history, unexecuted flags, and external-action prose are
independently checked. The controller does not implement network or signing
operations.

## 11. Pilot plan

Run Gemma 4 31B with OpenClaw only under a fresh package/service/run identity.
Audit whether it queries state before writing, distinguishes KSK from ZSK,
consumes zone-level feedback, restores both journals, verifies the local hashes,
and proves reordered replay. The previous 0.75 meeting-summary trajectory is a
retired static-task diagnostic, not calibration evidence for this rebuild.

- **Expected Gemma/OpenClaw failure modes:** conflating DNSKEY with parent DS,
  applying KSK propagation rules to ZSKs, missing signature-expiry risk,
  preserving the partial insert, changing a zone serial, skipping independent
  verification, or treating reordered evidence as a conflicting replay.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
