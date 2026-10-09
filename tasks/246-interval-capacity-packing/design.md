# Task Design: `246-interval-capacity-packing`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** shift planner packing interval jobs onto limited cutters
- **Trigger:** five mill cut jobs overlap on two capacity-5 machines
- **Objective:** emit a deterministic feasible assignment or leave jobs unplaced
- **Irreversible boundary:** no mill dispatch or cutter start is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| HB-S200-BOUNDED-ALLOCATION | bounded-capacity scheduling family | https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/ | 2026-09-11 | Grounds refusing work that does not fit remaining capacity |
| K8S-POD-PRIORITY | Kubernetes pod priority and preemption | https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/ | 2026-09-11 | Motivates a published placement order rather than arrival order |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file, commit, SQL statement, and JSON record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** Integer half-open intervals plus per-machine capacity make first-fit packing executable without a cluster.

## 3. Real-workflow justification

Interval packing is not calendar conflict detection: two jobs may overlap on different machines, and a job that never fits must stay unplaced rather than double-book a cutter.

## 4. Agent-visible inputs

`docs/packing_contract.md` is the highest authority. `jobs.json` and `machines.json` are protected. Identifiers are the `job_id` and `machine_id` fields already in those files.

## 5. Hidden ground truth

The evaluator recomputes the assignment from the protected JSON with an independent kernel and does not import a candidate packer. Hidden expected unplaced identifiers are cut-c and cut-e.

The required final workspace state is `assignment.json`.
The durable record keeps a stable key for each decision in `assignment.json`.

## 6. Expected workflow

1. Read the contract and both JSON inputs.
2. Sort jobs by end then job_id.
3. Assign the lexicographically smallest machine that never exceeds capacity on overlapping minutes.
4. Write assignment.json and notes.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `011-calendar-scheduling-conflict` | time intervals | 011 finds a meeting slot across time zones; 246 bins capacity on machines |
| `041-capacity-planning` | capacity | 041 is a planning narrative; 246 emits a concrete interval assignment |

1. Read the protected inputs and record their state before editing `assignment.json`.
2. Apply the published rule to the key fields that determine `assignment.json`.
3. Write `assignment.json` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires combining two JSON sources, applying overlap arithmetic, writing an exact assignment, and staying offline.

## 8. Stressors and difficulty

- **Stressors:** overlapping intervals, capacity 5, earliest-deadline order versus arrival order
- **Difficulty:** hard; first-fit by start time places a different set than earliest-deadline then lex machine
- **Plausible failure mode:** process jobs in file order or ignore overlap and sum sizes globally

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`machine_assignment` (0.50 core) checks the job-to-machine map. `unplaced_jobs` (0.30 core) checks the unplaced list. `verification_handoff` (0.20 optional) checks notes. The gate protects the JSON inputs.

### Adjacent examples

- **Nearest valid:** place cut-b on m-east, cut-a on m-west, cut-d on m-east; leave cut-c and cut-e unplaced.
- **Nearest wrong 1:** place by start time and put cut-e on a machine.
- **Nearest wrong 2:** treat overlap as pairwise exclusion regardless of remaining capacity.

`assignment.json` is a required final artifact checked by the hidden evaluator.
`PACKING_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

The prompt does not print the assignment map. The evaluator recomputes from jobs.json and machines.json.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect greedy-by-start or exclusive interval coloring.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
