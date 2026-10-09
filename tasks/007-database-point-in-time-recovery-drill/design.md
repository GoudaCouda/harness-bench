# Task Design: `007-database-point-in-time-recovery-drill`

## 1. Workflow identity

- **Primary domain:** IT Operations
- **Role:** database reliability engineer
- **Trigger:** a destructive PostgreSQL batch committed on production timeline 2 while a newer, divergent drill timeline also exists
- **Objective:** select and verify the correct physical base backup and WAL path, recover to an unambiguous named point in isolation, prove business invariants twice, and close a manual-promotion review gate
- **Real-world consequence:** choosing the wrong timeline or timestamp can silently preserve damage or discard valid work
- **Task family:** `database-point-in-time-recovery-drill`
- **Variant:** `named-target-divergent-timeline`

## 2. Idea provenance

| Source ID | Public source | URL | Adaptation |
|---|---|---|---|
| PG-PITR | PostgreSQL continuous archiving and point-in-time recovery | https://www.postgresql.org/docs/current/continuous-archiving.html | Adapted base-backup, WAL-continuity, named-target, and timeline-selection mechanics into a synthetic offline incident. |
| PG-VERIFYBACKUP | PostgreSQL `pg_verifybackup` | https://www.postgresql.org/docs/current/app-pgverifybackup.html | Adapted manifest/file/WAL verification followed by an isolated restore and data checks. |

- **Synthetic-data statement:** Every backup, WAL record, incident, business row, and identifier is synthetic; public sources supply workflow mechanics only.
- **Private user logs:** Not used.
- **Adaptation:** The two PostgreSQL workflows are combined with a protected local recovery state machine, two-pass business probes, normalized plan closure, and a no-production-action review boundary.

## 3. Real-workflow justification

Physical recovery is a dependent operational process rather than a report. Backup integrity, cluster identity, timeline ancestry, WAL continuity, target semantics, replayed rows, business invariants, and promotion readiness must agree. The local controller exposes rejected-state feedback and prevents an unverified candidate from crossing the review gate.

## 4. Agent-visible inputs

| Input | Purpose and authority |
|---|---|
| `evidence/backups.json` | candidate backup identity, timeline, completion time, and verification statuses |
| `evidence/timeline_history.json` | production and divergent timeline ancestry |
| `evidence/wal_archive.json` | readable WAL ranges, restore points, and replayable events |
| `evidence/incident.json` | affected cluster/timeline and the last-known-safe named point |
| `evidence/expected_invariants.json` | business probes that must hold after recovery |
| `policy/recovery_policy.json` | target-action, restore-command, and manual-gate rules |
| `state/recovery_state.json` | mutable local recovery state |
| `pitrctl.py` | inspect, verify, validate, restore, probe, close-gate, and replay interface |

## 5. Hidden ground truth

The evaluator independently selects the latest verified backup on the incident cluster and timeline before the named target, derives the required readable WAL sequence, replays ordered events through that target, recomputes business invariants, and verifies normalized plan/probe/input/state digests. It does not import or execute the public controller.

The concrete required final workspace state is an isolated, unpromoted `state/recovery_state.json` closed on the evidence-derived backup, timeline, target name, target LSN, and two identical passing probes. `work/recovery_receipt.json` must bind that state to immutable input hashes and a replay-stable normalized plan; production remains unchanged.

## 6. Expected workflow

1. Inspect `evidence/incident.json`, backup candidates, timeline history, WAL archive, policy, and the seed `state/recovery_state.json`.
2. Reject corrupt and divergent candidates, then verify the evidence-derived backup with `pitrctl.py verify-backup`.
3. Author `work/recovery_plan.json` with the named target, target LSN, exact WAL set, invariants, rejected alternatives, and isolation rationale.
4. Run `pitrctl.py validate-plan` and repair any evidence, target, WAL, or policy mismatch from its feedback.
5. Execute the local isolated restore and run `pitrctl.py probe` twice so the same business result set is observed twice.
6. Close the manual review gate to produce `work/recovery_receipt.json`, then replay the same plan and prove byte-stable state and receipt closure.
7. Write `work/recovery_handoff.md` with the chosen path, rejected alternatives, evidence, probe results, and an explicit statement that no production promotion or routing occurred.

## 7. Harness demands

The task requires multi-source evidence grounding, timeline and target reasoning, candidate-authored structured state, protected controller transitions, actionable validation feedback, repeated verification, normalized digest closure, replay behavior, and respect for a production safety boundary. Later commands depend on artifacts and state produced by earlier commands.

## 8. Stressors and difficulty

- the newest verified-looking backup is newer but belongs to divergent timeline 3;
- an older timeline-2 backup has corrupt verification evidence;
- the incident timestamp is shared by valid and destructive work, so timestamp recovery is unsafe;
- WAL continuity must be derived from the selected base through the named point;
- two identical probes and digest-bound replay are required before the review gate closes;
- local recovery is required while promotion and client routing remain forbidden.

- **Plausible failure mode:** An agent chooses the newest backup, targets the ambiguous timestamp, omits a WAL segment, performs only one probe, edits receipt fields, or claims production promotion.
- **Difficulty rationale:** Backup selection, timeline ancestry, target semantics, ordered WAL, restored business state, two-pass probes, six artifacts, and replay-safe hashes must agree; a plausible plan document alone cannot score highly.

## 9. Oracle design

The structured core totals exactly 0.80. `backup_and_timeline_selection` owns the evidence-derived backup and timeline; `wal_and_target_plan` owns named-target and exact WAL facts in `work/recovery_plan.json`; `isolated_restore_and_probes` owns restored `state/recovery_state.json` and two-pass `work/probe_report.json`; and `gate_receipt_and_replay` owns bound `work/recovery_receipt.json` and replay closure. `work/recovery_handoff.md` supplies only bounded semantic reviewer communication. Immutable evidence, declared artifact types, protected local state, and no-production-action claims form the safety gate.

IDs, system identifier, backup, timeline, target, LSN, WAL segments, invariants, state, and digests are exact. Keyed list order is semantically irrelevant. Only handoff wording may use a bounded semantic fallback; prose cannot repair machine-state failures.

## 10. Leakage, isolation, and safety review

Only `instruction.md` and `workspace/` are exposed. Tests, reference artifacts, and semantic rubric remain hidden. The public controller derives its selected backup, rejected alternatives, WAL path, and target from visible evidence rather than containing an item-keyed answer map; a seed-mutation contract verifies this. The environment is synthetic and offline with no PostgreSQL server, credential, network endpoint, or production control plane. The evaluator treats candidate artifacts as bounded inert data and rejects source mutation, hazardous workspace entries, protected-state violations, and affirmative promotion or routing claims. Ordinary extra regular files remain diagnostic rather than zeroing an otherwise valid recovery.

## 11. Pilot plan

Contract calibration requires reference=1.0 and empty, pristine/untouched, and malformed=0.0; adjacent divergent-backup, corrupt-backup, timestamp-target, missing-WAL, single-probe, business-invariant, stale-receipt, source-mutation, hazardous-workspace, and production-claim negatives; an ordinary-extra-file diagnostic check; equivalent list ordering; generic controller derivation under mutated seed evidence; and byte-stable replay. A fresh model pilot may follow static validation, with trace review for evidence inspection, rejected-state feedback use, two probes, and replay.

- **Expected Gemma/OpenClaw failure modes:** preferring recency over timeline authority, treating a timestamp as unambiguous, skipping backup verification, overlooking WAL continuity, closing after one probe, or claiming an external promotion.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `backup_and_timeline_selection`, `wal_and_target_plan`.
- `validation_and_replay`: `isolated_restore_and_probes`, `gate_receipt_and_replay`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
