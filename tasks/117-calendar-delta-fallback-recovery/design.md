# Task Design: `117-calendar-delta-fallback-recovery`

## 1. Workflow identity

- **Domain / role:** Office Productivity; calendar synchronization operator
- **Trigger:** a CalDAV-style incremental pull stopped after preparing page 1, while cached page 2 was truncated
- **Objective:** authorize the checksum fallback, adjudicate RFC 5545 masters and recurrence instances, transactionally recover the SQLite replica/checkpoint, and stage an offline receipt
- **Task family:** `recurring-calendar-incremental-sync-recovery`
- **Variant:** `recurrence-etag-checksum-sqlite-checkpoint`
- **Consequence:** a shallow replay can move an entire series instead of one occurrence, resurrect a cancelled instance, regress a newer event, shift London/New York wall time, or advance a cursor without durable component state

## 2. Idea provenance

| Source ID | Public source | URL | Adaptation |
|---|---|---|---|
| RFC5545-RECURRENCE-ID | RFC 5545 §3.8.4.4 | https://www.rfc-editor.org/rfc/rfc5545#section-3.8.4.4 | A recurrence instance is keyed by UID plus RECURRENCE-ID and remains distinct from its series master. |
| CALDAV-ETAG | RFC 4791 §8.6 | https://www.rfc-editor.org/rfc/rfc4791#section-8.6 | Cached calendar resources and incremental pages are bound to validators before a local replica advances. |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://sqlite.org/lang_transaction.html | Component mutation, tombstones, ledger, journal recovery, and checkpoint advance commit atomically. |

- **Synthetic-data statement:** All collection names, events, attendees, identifiers, checksums, and incident facts are synthetic; public sources supply protocol semantics only.
- **Private user logs:** Not used.

- **Adaptation:** RFC 5545 recurrence identity, CalDAV validator continuity, and SQLite transactions were combined into a synthetic interrupted incremental-sync recovery whose output is an evidence-bound `recovery_plan.json` and mutated local replica.

## 3. Real-workflow justification

This replaces the prior static JSON/CSV delta-to-table exercise. It is not another generic event replay like tasks 108 or 115: correctness depends on RFC 5545 compound identity, recurrence overrides and cancellations, original `TZID` plus UTC projection, CalDAV-style ETag continuity, and a durable calendar cursor. Unlike meeting/document staging tasks, the final state is a mutated relational replica with transaction and replay invariants.

Task-only full-package judgement:

```yaml
task_key: harnessbench::117-calendar-delta-fallback-recovery
evidence_mode: full_package
capability_signature:
  domains: [office_productivity, calendar_protocols, local_database_recovery]
  tools: [python_cli, sqlite, rfc5545_text, json, sha256]
  behaviors: [inspect, query, evidence_adjudication, timezone_normalization, transactional_apply, verify, replay]
  fault_or_initial_state: "prepared page-1 journal, partially written master row, truncated page 2"
  expected_final_state: "exact recurring replica, tombstones, cursor/ETag, one committed recovery, local receipt"
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
  - "Later mutation depends on checksum, ETag, sequence, recurrence identity, and timezone observations."
  - "SQLite exposes durable operational state that the evaluator can verify independently."
risks:
  - "The intentionally narrow RFC 5545 parser supports the supplied DATE-TIME subset, not arbitrary calendars."
missing_evidence:
  - "Fresh Gemma 4 31B plus OpenClaw rollout remains pending after static admission."
```

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `state/calendar.db` | mutable replica, protected event, checkpoint, prepared journal, rollback row |
| `evidence/page1.ics` | valid first page with master update, override, occurrence cancellation, event update, tombstone |
| `evidence/page2.part` | parseably incomplete/truncated cache evidence |
| `evidence/page2_recovery.ics` | authorized fallback with cross-zone override, new London event, stale sequence |
| `policy/sync_manifest.json` | stable recovery identity, source checkpoint, hashes, cursors, and ETag chain |
| `policy/recovery_policy.md` | disposition vocabulary, precedence, time, transaction, and safety rules |
| `policy/timezone_registry.json` | allowed IANA zones |
| `syncctl.py` | inspect/query, preview, apply, verify, stage, replay controller |

The controller parses the evidence and validates each submitted component/disposition pair against the effective pre-recovery state. It contains no callable complete-plan constructor, fixture-keyed final-action map, or literal expected final projection.

## 5. Hidden ground truth

The independent evaluator reads the candidate plan and controller receipts as inert data and opens SQLite read-only. It does not import or execute `syncctl.py`. It owns an independently encoded final component projection, UTC instants, recurrence keys, tombstones, journal/checkpoint transition, protected row, semantic digest, and local-only safety boundary.

The required final `state/calendar.db` must contain the exact master/instance event keys, two tombstones, the committed cursor/checkpoint and one recovery transaction; `recovery_plan.json` must independently encode the authorized fallback and all eight component dispositions.

The intended evidence-dependent path is:

1. Inspect the manifest, checksum mismatch, truncated component, checkpoint, prepared journal, rollback row, and current events.
2. Query SQLite and parse both accepted pages to distinguish master/instance identities and compare `SEQUENCE` values.
3. Author a fallback- and checkpoint-bound plan with local evidence references.
4. Use candidate-first preview feedback to repair the named identity/fallback field or the submitted component's disposition and evidence categories. Feedback never returns the correct disposition or a missing action object.
5. Apply atomically; restore the interrupted partial row before replaying the complete accepted chain.
6. Verify semantic SQLite state, stage a pending owner-review receipt, and replay to prove no-op behavior.
7. Write the operational handoff without claiming a remote side effect.

## 6. Expected workflow

1. Inspect `policy/sync_manifest.json`, `evidence/page2.part`, and the `state/calendar.db` checkpoint/journal state.
2. Determine the accepted page chain from `evidence/page1.ics` and `evidence/page2_recovery.ics`, then distinguish event keys for masters and recurrence instances.
3. Create `recovery_plan.json` and preview its component dispositions, fallback checksum, and source checkpoint.
4. Apply once to `state/calendar.db`, verify the mutated event/tombstone state, and stage `state/recovery_receipt.json`.
5. Replay the same semantic plan, reconcile cursor/ETag and journal hashes, then complete `recovery_handoff.md`.

Adjacent plausible errors include:

- treating all components sharing `UID` as one row;
- deleting the series master for one cancelled `RECURRENCE-ID`;
- applying the stale town-hall `SEQUENCE:1` over local sequence 2;
- interpreting London/New York wall times as UTC or retaining the recurrence zone as the override start zone;
- accepting the fallback without both checksum and ETag continuity;
- advancing the cursor after page 1 only;
- stacking new mutations on the interrupted partial write rather than restoring it;
- keying replay by serialized JSON so reordered actions double-apply;
- accepting a conflicting plan under the already committed recovery ID;
- forging receipts or claiming invitation/cancellation delivery.

## 7. Harness demands

The package requires genuine terminal agency: inspection and SQLite queries precede a candidate-authored plan; preview supplies actionable feedback; apply changes a real database; and verification/replay depend on the new persistent state. It exercises filesystem evidence, structured protocol parsing, state management, interrupted recovery, independent reconciliation, and an irreversible-action boundary.

The scoring ownership is:

The hidden evaluator never imports or executes `syncctl.py`. It reads JSON as inert bounded data and opens SQLite read-only. Its independently encoded expected projection checks exact UTC instants, TZIDs, recurrence/master keys, tombstones, protected unrelated state, sequence precedence, ledger, checkpoint, rollback, journal, transaction, semantic digest, verification, receipt, and replay.

| Case | Weight | Primary owner |
|---|---:|---|
| fallback and component plan | 0.27 | `recovery_plan.json` |
| recurrence/timezone projection | 0.27 | `state/calendar.db` events and tombstones |
| checkpoint/transaction recovery | 0.26 | SQLite ledger, rollback, checkpoint, journal, transaction |
| verification/receipt/replay | 0.12 | controller-generated closure artifacts |
| handoff | 0.08 | `recovery_handoff.md` |
| safety/input integrity | gate | immutable sources, protected row, artifact types, execution claims |

The three independent core cases total exactly 0.80. Prose cannot rescue a broken plan or database. Ordinary adjacent errors lose their natural case; only immutable input/protected state mutation, unsafe files, or external-action execution claims trigger the zero-score gate.

## 8. Stressors and difficulty

Difficulty comes from coupled protocol state, not artifact volume: page validity, ETag continuity, recurrence identity, per-component sequence, timezone conversion, rollback, cursor advance, transaction digest, and replay all constrain one another. A plausible-looking event list is insufficient. Expected failure modes include collapsing a series and override, accepting a truncated page, applying a stale sequence, shifting wall time, or replaying the prepared partial state twice.

- **Plausible failure mode:** the operator overwrites the series master with an occurrence override, advances the cursor, and leaves an apparently coherent but semantically wrong replica.
- **Difficulty rationale:** eight heterogeneous components cross two validators and four time-zone/identity cases, while one rollback, seven durable tables, semantic plan identity, and no-op replay must close atomically.

Replay/leakage hardening:

The recovery transaction is keyed by stable `recovery_id` plus immutable `source_checkpoint`. The semantic plan digest sorts actions and set-valued evidence references and excludes the separately validated free-form fallback rationale. Equivalent representation or rationale wording replays byte-stably; a changed disposition under the committed identity is rejected before mutation. A public-controller seed-mutation contract raises the town-hall sequence in a copied fallback, updates its manifest hash, and proves that the formerly valid stale disposition is rejected while the evidence-derived update candidate passes. This prevents a literal fixture answer table from silently returning.

## 9. Oracle design

| Case | Weight | Independent observable |
|---|---:|---|
| `fallback_and_component_plan` | 0.27 | exact accepted source, component identities, dispositions, and evidence |
| `recurrence_timezone_projection` | 0.27 | exact events, UTC instants, TZIDs, sequences, and tombstones |
| `checkpoint_transaction_recovery` | 0.26 | rollback, ledger, cursor/ETag, journal, stable transaction and digest |
| `verification_receipt_and_replay` | 0.12 | preview, verification, stage-token, and no-op replay closure |
| `recovery_handoff` | 0.08 | bounded operator explanation |
| `safety_and_input_integrity` | gate | immutable sources, protected row, regular artifacts, no remote-action claim |

The first three core cases total exactly 0.80. Partial credit follows the artifact ownership described above. Only immutable source or protected state mutation, unsafe artifacts, or an affirmative remote execution claim invokes the zero-score gate.

Artifact coverage is explicit: `recovery_plan.json` owns decisions; `.calendar_preview.json` owns preflight; `state/calendar.db` owns operational state; `state/calendar_verification.json` owns reconciliation; `state/recovery_receipt.json` owns local staging; `state/replay_report.json` owns no-op replay; and `recovery_handoff.md` owns the operator explanation.

## 10. Leakage, isolation, and safety review

Only `instruction.md` and `workspace/` are agent-visible. The public controller performs candidate-first field validation from the SQLite seed and RFC 5545 pages; it exposes no callable answer constructor, fixture-keyed expected action map, or final projection. The evaluator, reference artifacts, fixture builder, and contracts remain hidden. Sources and identities are synthetic, the workflow is network-free, candidate code is never executed by the evaluator, and external calendar writes/messages are forbidden. Its preview identifies a submitted object's invalid disposition and missing ICS/manifest evidence categories without publishing the replacement value. Bounded regular top-level `.py`/`.sql` inspection helpers and regular Python cache contents are diagnostic-only; symlinks, special files, immutable-source changes, controller tampering, and external-action claims remain safety failures.

## 11. Pilot plan

Required static calibration: reference 1.0; empty, pristine, malformed 0.0; source/protected-row gates; wrong disposition, timezone, rollback, receipt negatives; equivalent-order full workflow and byte-stable replay; conflicting replay rejection; public seed-mutation derivation; Ruff; design/provenance; public leakage; task-only oracle.

A real r2 Gemma 4 31B + OpenClaw run found that all component dispositions were correct, but the public contract left `damaged_page`, `expected_etag`, component fragment locators, and per-action manifest authority ambiguous. Its aggregate-only preview kept returning `fallback_chain=false` and `local_evidence=false`, so the model reasonably cycled between interpretations until timeout. The repaired contract defines those fields explicitly and preview now returns bounded per-field/per-candidate evidence-category feedback without answer values. A fresh r3 run is mandatory after static validation; r2 is not admission evidence.

- **Expected Gemma/OpenClaw failure modes:** collapsing `RECURRENCE-ID` into UID, trusting the truncated cache, applying stale sequence 1, treating London wall time as UTC, omitting rollback evidence, or changing action order and accidentally double-applying.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
