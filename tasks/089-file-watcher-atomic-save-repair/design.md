# Task Design: `089-file-watcher-atomic-save-repair`

## 1. Workflow identity

- **Role:** platform engineer repairing a configuration file watcher.
- **Trigger:** atomic saves replace inodes, duplicate events reload twice, and null filenames miss changes.
- **Objective:** reconcile advisory event batches against authoritative final snapshots and durable state.
- **Boundary:** offline replay only; no real watcher, signal, or service reload.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| NODE-FS-WATCH | Node.js file-system `fs.watch` documentation | https://nodejs.org/api/fs.html#fswatchfilename-options-listener | 2026-08-27 |

- **Adaptation:** documented cross-platform event, missing filename, and inode caveats become a deterministic offline reconciliation repair.
- **Private user logs:** None.
- **Synthetic-data statement:** All paths, inode numbers, digests, events, and snapshots are synthetic.

## 3. Real-workflow justification

File watchers are edge-triggered hints, while a stable post-debounce probe is
needed to establish current state. Atomic-save workflows may replace the inode
even when content is unchanged, requiring a watcher rebind without a needless
application reload.

## 4. Agent-visible inputs

The repository exposes an exact contract, policy, initial checkpoint, replay
batches, broken pure reconciler, protected runner, and public regressions.

## 5. Hidden ground truth

Hidden cohorts cover changed and unchanged inode replacement, duplicate and
out-of-order path hints, delete/recreate, null-filename full scans, unmanaged
and temporary paths, non-regular nodes, exact sorted actions, sequential
checkpoint propagation, malformed state, path traversal, stale sequence, and
immutable evidence.

Required final workspace state is repaired `repo/src/watch_reconciler.py`, an
exact sequential `repo/out/actions.json` ledger, the durable final
`repo/out/checkpoint.json`, and a verified `repo/WATCHER_NOTES.md` handoff.

## 6. Expected workflow

1. Inspect `repo/docs/watcher_contract.md`, `repo/policy.json`,
   `repo/checkpoint.json`, `repo/batches.json`, and the broken reconciler.
2. Repair canonical validation, managed-path selection, snapshot precedence,
   and reload/rebind/delete/block transitions in `repo/src/watch_reconciler.py`.
3. Run public tests and `repo/bin/replay_watch.py`, propagating each batch's
   returned checkpoint into the next batch.
4. Re-parse `repo/out/actions.json` and `repo/out/checkpoint.json`, then record
   event caveats, safety behavior, and exact verification in
   `repo/WATCHER_NOTES.md`.

## 7. Harness demands

Executable state-machine repair, path safety, evidence precedence, replay,
exact structured outputs, verification, and action restraint are required.

## 8. Stressors and difficulty

- **Plausible failure mode:** A solution trusts `rename` as deletion, reacts to
  temp files, equates inode change with content change, omits rebind, replays
  duplicates, ignores null filename, or advances stale batches.
- **Difficulty rationale:** The implementation must combine canonical path and
  state validation, advisory-event candidate selection, authoritative snapshot
  reconciliation, inode/content distinctions, sequential replay, and unsafe
  node preservation across multiple dependent transitions.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `atomic_save_and_coalescing` | 0.30 | core | Atomic saves and duplicate hints produce one correct durable transition |
| `deletion_rescan_and_node_safety` | 0.25 | core | Deletes, null-filename rescans, creation, and unsafe nodes follow snapshot authority |
| `visible_sequential_replay` | 0.10 | core | Protected replay outputs exactly follow sequential checkpoints |
| `verification_handoff` | 0.20 | handoff | The watcher handoff explains state authority and verified behavior |
| `evidence_and_action_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/watch_reconciler.py`, `repo/out/actions.json`, `repo/out/checkpoint.json`, `repo/WATCHER_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cases and references are excluded. Candidate code runs through a pure
function sandbox with no filesystem, process, network, private attributes, or
dynamic execution. The only permitted module capability is
`os.path.basename`; snapshots are data, not host probes.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, Docker reference 1.0, then fresh
Gemma + OpenClaw calibration and trajectory review.

- **Expected Gemma/OpenClaw failure modes:** event-type-driven actions,
  duplicate reloads, missed null-filename changes, incorrect same-digest inode
  handling, unsafe symlink adoption, stale checkpoints, or incomplete replay
  evidence.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and model calibration replace manual acceptance.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `atomic_save_and_coalescing`.
- `validation_and_replay`: `deletion_rescan_and_node_safety`, `visible_sequential_replay`, `evidence_and_action_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
