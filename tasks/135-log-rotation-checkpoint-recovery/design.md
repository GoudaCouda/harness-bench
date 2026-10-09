# Task Design: 135-log-rotation-checkpoint-recovery

## 1. Workflow identity

This task models an on-host file tailer recovering after a ledger-ahead crash followed by log rotation. The byte checkpoint names the rotated file and stops after r401, while the durable processed ledger already contains r400 through r404.

## 2. Idea provenance

The workflow adapts logrotate state and inode-aware tailing practices documented at https://man7.org/linux/man-pages/man8/logrotate.8.html. The retained source ID is `LOGROTATE-STATE`.

- **Private user logs:** None were used; records and crash state are authored benchmark fixtures.
- **Synthetic-data statement:** Log messages, record IDs, timestamps, paths, and host identities are synthetic.

- **Adaptation:** logrotate and inode-aware tailing practice are transformed into an offline crash recovery where a durable processed-ID ledger is ahead of a stale checkpoint and the active path has rotated to a new file identity.

## 3. Real-workflow justification

Path names are not stable file identities across rotation. A consumer that resumes only from a stale path/offset can lose current-file records or duplicate already-ledgered records. Recovery must reconcile device/inode, byte offset, rotated ordering, and durable IDs, then prove the new checkpoint and no-op replay.

## 4. Agent-visible inputs

The runtime creates a checkpoint with actual device/inode identity for `service.log.1`. Immutable rotated and active JSONL logs span r400-r406. The processed ledger is ahead through r404. Policy identifies the ledger as the dedup authority. A guarded local utility inspects and recovers state.

## 5. Hidden ground truth

The evaluator binds visible rotated/active logs, policy, `repo/state/checkpoint.json`, `repo/state/processed.jsonl`, and `repo/tools/tailer_recovery.py` to final state in `repo/state/checkpoint.json`, `repo/state/processed.jsonl`, `repo/out/recovered.jsonl`, and `repo/TAILER_HANDOFF.md`. The invariant is ID-ledger deduplication plus device/inode/EOF checkpoint identity: only r405-r406 are newly recovered, and a second replay changes nothing.

## 6. Expected workflow

1. Inspect both log paths, actual device/inode state, `repo/state/checkpoint.json`, `repo/state/processed.jsonl`, policy, and utility help.
2. Reconcile the rotated-file offset event with durable record IDs and diagnose why the ledger is ahead of the checkpoint.
3. Invoke `repo/tools/tailer_recovery.py` with the explicit stale-state acknowledgement so only IDs absent from the ledger are recovered.
4. Verify `repo/out/recovered.jsonl` contains only r405-r406 and `repo/state/processed.jsonl` contains one copy of every processed ID.
5. Verify `repo/state/checkpoint.json` names the current log device/inode and exact EOF offset, then run recovery against copied state and require an empty delta.
6. Write `repo/TAILER_HANDOFF.md` with crash boundary, inode/offset reasoning, duplicate suppression, commands, and evidence.

## 7. Harness demands

The task requires file discovery, stat inspection, JSONL reasoning, stateful guarded execution, duplicate suppression, post-change verification, and durable handoff. It is not a pure-function repair.

## 8. Stressors and difficulty

- **Stressors:** stale offset on a real rotated inode; ledger-ahead crash boundary; duplicate suppression; active-path identity change; no-op replay.
- **Plausible failure mode:** resuming by pathname/offset alone can duplicate r402-r404 or skip r405-r406; replacing only the checkpoint, forging EOF, or appending duplicate ledger IDs leaves state superficially plausible but non-idempotent.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** the operator must reconcile filesystem identity, physical byte positions, durable logical IDs, ordered logs, and copied-state replay before declaring convergence.

## 9. Oracle design

Recovered delta weighs 0.35, ledger/checkpoint convergence 0.25, no-op replay 0.20, and handoff 0.20. The oracle explicitly grades `repo/state/checkpoint.json`, `repo/state/processed.jsonl`, `repo/out/recovered.jsonl`, and `repo/TAILER_HANDOFF.md`; core weight is 0.80. A zero-weight gate protects logs, policy, and utility.

## 10. Leakage, isolation, and safety review

All work is offline on synthetic local logs. The public utility gives diagnostics but not hidden scores. The grader independently parses files and checks filesystem identity. Ordinary mistakes lose weighted cases; source tampering reaches the gate.

## 11. Pilot plan

Acceptance requires untouched and malformed zero, reference one, and failures for path-only resume, cursor-only edits, duplicate output, ledger omission, forged EOF, utility tampering, and non-idempotent replay.

- **Expected Gemma/OpenClaw failure modes:** trust the stale rotated offset, deduplicate by position instead of record ID, rerecover r402-r404, omit r405-r406, checkpoint the wrong inode, or claim no-op behavior without rerunning on copied state.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, reference, discrimination, leakage, environment, Docker, and trajectory checks own admission.
- **Model calibration:** a fresh model/harness run remains useful difficulty evidence, not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval is not part of benchmark admission.
