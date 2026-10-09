# Task Design: `239-dag-priority-scheduler-repair`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** build-graph engineer repairing a mill scheduler
- **Trigger:** a cyclic recipe hung the board and equal-priority jobs ran in input order
- **Objective:** repair topological scheduling with priority-stable ties and fail closed on cycles
- **Irreversible boundary:** no mill dispatch, remote build farm, or production recipe publish is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| K8S-POD-PRIORITY | Kubernetes pod priority and preemption | https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/ | 2026-09-11 | Grounds higher numeric priority winning among ready work |
| TIKV-PD-SCHEDULER | TiKV Placement Driver architecture | https://tikv.org/docs/latest/concepts/architecture/ | 2026-09-11 | Motivates a local scheduler that must refuse cyclic placement graphs |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file, commit, SQL statement, and JSON record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** A small job DAG with explicit priorities makes the ordering executable without a cluster.

## 3. Real-workflow justification

Build and mill schedulers fail when ready-set ordering is FIFO instead of priority, or when a cycle is treated as a partial order. The task changes reusable code and reconciles a concrete mill snapshot.

## 4. Agent-visible inputs

`repo/docs/schedule_contract.md` is the highest authority. `repo/jobs.json` is the protected mill snapshot. Public examples live in `repo/tests/test_public.py`. `repo/src/schedule.py` is writable.

## 5. Hidden ground truth

Hidden cases cover diamonds, equal-priority lexicographic ties, self-edges, two-cycles, unknown dependency identifiers, and duplicate `job_id`s. `schedule.json` must match an independent kernel on the visible jobs. The evaluator does not import the public tests or a candidate helper module; it audits and executes `schedule_jobs` in a restricted worker.

The required final workspace state is `repo/src/schedule.py`.

## 6. Expected workflow

1. Read the contract and `jobs.json`.
2. Run the public unittest and identify FIFO or cycle-blind failures.
3. Implement `schedule_jobs` and re-run the unittest command.
4. Write `schedule.json` from the visible mill jobs.
5. Record decisions, verification, and residual risk in `IMPLEMENTATION_NOTES.md`.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `010-layered-config-resolution` | repository code repair plus public unittest | 010 resolves typed config layers; 239 schedules a job DAG |
| `002-monorepo-affected-build` | build graph | 002 selects affected packages; 239 must emit a total order or fail closed |
| `249-airflow-sensor-deadlock-repair` | Airflow wording | 249 is a clerk drain; 239 is a code-repair scheduler |

## 7. Harness demands

The task requires reading a contract and mill snapshot, repairing code, running tests, emitting an exact JSON order, and staying offline.

## 8. Stressors and difficulty

- **Stressors:** cycles, unknown edges, equal-priority ties, duplicate identifiers
- **Difficulty:** hard; compact implementations pass the public diamond while using input order or ignoring cycles
- **Plausible failure mode:** Kahn FIFO, DFS preorder, or treating a cycle as a blocked subset instead of ValueError

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`scheduler_behavior` (0.50 core) executes hidden acyclic and fail-closed cases in a restricted worker. `visible_schedule` (0.30 core) checks `repo/schedule.json` against an independent kernel. `verification_handoff` (0.20 optional) checks notes. `source_and_workspace_boundary` is a zero-weight integrity gate.

### Adjacent examples

- **Nearest valid:** equal-priority ready jobs sort by `job_id`.
- **Nearest wrong 1:** ready jobs keep `jobs.json` input order.
- **Nearest wrong 2:** a two-cycle returns a partial `order` instead of raising ValueError.

`repo/src/schedule.py` is a required final artifact checked by the hidden evaluator.
`repo/IMPLEMENTATION_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

Hidden cases and the reference implementation are not agent-visible. Candidate source is AST-audited before restricted execution. Fixtures are immutable. No mill endpoint exists.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw on this package alone. Target a first-pass score around 0.30–0.80; a clean 1.0 without running tests triggers a shallow-task review.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
