# Task Design: `033-rate-limit-lease-reconciliation`

## 1. Workflow identity

- **Role:** platform engineer repairing a regional quota allocator.
- **Trigger:** retry and expiry races oversubscribe fixed capacity.
- **Objective:** restore deterministic lease accounting and fencing.
- **Boundary:** no production quota mutation or deployment is authorized.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| KUBERNETES-LEASE-V1 | Kubernetes Lease v1 API | https://kubernetes.io/docs/reference/kubernetes-api/coordination/lease-v1/ | 2026-08-26 |
| KUBERNETES-API-CONCURRENCY | Kubernetes API concepts | https://kubernetes.io/docs/reference/using-api/api-concepts/ | 2026-08-26 |

- **Adaptation:** Kubernetes holder, renewal, duration, and resource-version concepts become a bounded divisible-capacity reconciler whose replay, FIFO admission, expiry, and fencing invariants can be tested offline.
- **Private user logs:** None were used; all owners, requests, clocks, and capacities are synthetic.

## 3. Real-workflow justification

Distributed limiters often pass happy-path tests while retries mint duplicate
grants or exact-boundary expiry disagrees across workers. Repairing reusable code,
replaying incidents, and handing off clock risk is a recognizable platform task.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/lease_contract.md` | authoritative transition contract |
| `repo/src/lease_reconciler.py` | broken implementation |
| `repo/reconciliation_cases.json` | visible incident batches |
| `repo/tests/test_public.py` | public regression tests |

## 5. Hidden ground truth

The evaluator recomputes state from `repo/reconciliation_cases.json` and hidden
cohorts. `expires_ms <= now_ms` releases capacity; an identical active request
replay preserves its fence; conflicts fail; new grants follow FIFO and conserve
capacity. Final `repo/src/lease_reconciler.py` and
`repo/reconciliation_report.json` must encode those invariants without changing
visible records.

## 6. Expected workflow

1. Read `repo/docs/lease_contract.md` and inventory lease state and keys.
2. Run `repo/tests/test_public.py` and trace expiry, replay, and fence state.
3. Repair `repo/src/lease_reconciler.py` and rerun reordered/capacity cases.
4. Generate `repo/reconciliation_report.json` from the repaired function.
5. Record verification and clock-risk state in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

The harness must support repository inspection, local execution, exact JSON
artifacts, multi-step state reasoning, verification, and external-action restraint.

## 8. Stressors and difficulty

- **Plausible failure mode:** use `<` at expiry, allocate in input order, mint a
  new fence on replay, partially grant, or mutate the caller's state.
- **Difficulty rationale:** each shortcut passes simple capacity examples but
  fails independent hidden state transitions and conservation checks.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `capacity_expiry_and_fencing` | 0.40 | core | Capacity, exact expiry, and fencing remain safe |
| `replay_conflict_and_fairness` | 0.20 | core | Retries and FIFO contention reconcile deterministically |
| `visible_batch_report` | 0.05 | core | Visible incident batches are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Repair reasoning and verification are handed off |
| `source_and_workspace_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/lease_reconciler.py`, `repo/reconciliation_report.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden cohorts and reference outputs are excluded. Candidate code is AST-audited
and executed without import, file, network, process, or dynamic-call capability.
Protected evidence and external-action claims fail closed.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, then run a fresh
Gemma + OpenClaw trial on a qualified worker and inspect case attribution.

- **Expected Gemma/OpenClaw failure modes:** exact-expiry error, replay refencing,
  input-order allocation, capacity drift, or incomplete verification notes.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic gates and a model pilot are required; this does not claim human approval.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `capacity_expiry_and_fencing`.
- `validation_and_replay`: `replay_conflict_and_fairness`, `visible_batch_report`, `source_and_workspace_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
