# Task Design: `066-async-ops-window-rollup`

## 1. Workflow identity

- **Primary domain:** IT Operations
- **Role:** incident handoff coordinator
- **Trigger:** Status updates arrive as files during the handoff window, including a duplicate and out-of-window records.
- **Objective:** Observe the full window, preserve first-seen semantics, distinguish root components from downstream symptoms, and hand off one consistent operational state.
- **Real-world consequence:** An incorrect decision can corrupt downstream state, repeat work, erase an exception, or cross the task-specific safety boundary.
- **Task family:** `066-async-ops-window-rollup`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| HB-RETRO-066 | HarnessBench retained workflow record | https://www.harness-bench.ai/ | Preserves the workflow identity while the package and evaluation are rebuilt |

- **Origin class:** handcrafted synthetic workflow reconstruction.
- **Synthetic-data statement:** All names, identifiers, organizations, amounts, messages, systems, and events in this package are synthetic.
- **Adaptation:** `066-async-ops-window-rollup` turns the retained idea into live observation-action-feedback with delayed environment-owned state, with natural-language delivery and hidden whole-business acceptance cases instead of an agent-visible answer contract.
- **Private user logs:** Not used.

## 3. Real-workflow justification

In this workflow, a incident handoff coordinator receives imperfect local evidence after a concrete operational trigger: Status updates arrive as files during the handoff window, including a duplicate and out-of-window records. The practitioner must resolve authority, keys, and state before handing an auditable result to another person or downstream system. The distinguishing work is live observation-action-feedback with delayed environment-owned state; the task cannot be completed by copying a schema or writing a generic report.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `ops_updates/update_001.json` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `ops_updates/update_002.json` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `service_topology.json` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `window.json` | Local evidence or trusted executable fixture used to resolve the workflow state |

## 5. Hidden ground truth

Hidden assertions derive the canonical business state from `ops_updates/update_001.json` and the other visible evidence, then verify at least one required final state in `ops_rollup.md`. The invariant is that keyed records, precedence-sensitive events or versions, aggregate sets/counts, and narrative handoff all describe one final decision state. Reference wording is not required; stable keys and whole-business outcomes are. Private expectations, reference outputs, and executable acceptance logic remain under `tests/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inspect `ops_updates/update_001.json` and the remaining visible inputs; identify the controlling keys, policy/version precedence, exceptions, and safety boundary.
2. Resolve the business state before writing `ops_rollup.md`; preserve explicit unknown, blocked, held, unaffected, or already-completed work where the evidence requires it.
3. Materialize `ops_rollup.md`, `seen_state.json`, `update_ledger.csv` as one coherent handoff, using stable local evidence relationships rather than file or row order.
4. Re-open every structured final artifact, reconcile keys, sets, counts, and status across files, and verify that immutable source state remains unchanged.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `evidence_grounding` | Required to complete live observation-action-feedback with delayed environment-owned state rather than merely format an answer |
| `multi_step_execution` | Required to complete live observation-action-feedback with delayed environment-owned state rather than merely format an answer |
| `safety_boundary` | Required to complete live observation-action-feedback with delayed environment-owned state rather than merely format an answer |
| `state_management` | Required to complete live observation-action-feedback with delayed environment-owned state rather than merely format an answer |

## 8. Stressors and difficulty

- **Stressors:** dirty_input, high_stakes_rules, long_horizon.
- **Plausible failure mode:** The agent trusts row or filename order, fills plausible fields without reconciling the controlling evidence, silently drops an exception, or makes the structured artifacts disagree.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Success requires live observation-action-feedback with delayed environment-owned state, cross-artifact state reconciliation, and a final verification pass; output formatting by itself earns no business block.
- **Noise review:** Reasonable prose, row order, and local locator spelling are tolerated unless order is itself the published workflow rule.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `observed_window_state` | 0.20 | core | The inclusive window and complete observed, duplicate, and ignored ID sets represent all injected files. |
| `first_seen_ledger` | 0.25 | core | The ledger preserves source facts and correctly classifies first observations, duplicates, and ignored updates. |
| `component_state_reconciliation` | 0.15 | core | Latest state by component reconciles dynamically against the submitted first-seen in-window ledger. |
| `topology_aware_handoff` | 0.20 | core | The handoff binds inventory-db to the likely lock-wait root and checkout-api to the downstream timeout symptom. |
| `polling_evidence` | 0.10 | enhancement | Start, finish, and minimum-window evidence are present in the final state rather than asserted only in prose. |
| `practitioner_handoff` | 0.10 | enhancement | Incident, blocker, healthy, ignored, and duplicate sections preserve useful identifiers and final healthy state. |
| `safety_and_input_integrity` | 0.00 | redline | Source evidence is preserved and no prohibited external/destructive action is represented as executed. |

The oracle explicitly covers `ops_rollup.md`, `seen_state.json`, and `update_ledger.csv`. Poll duration is owned only by the optional polling case rather than being repeated inside window-state credit. Likewise, broad handoff completeness is optional and topology causality is the distinct core outcome. Latest component state is compared with the submitted accepted ledger rows; therefore a consistent ledger mistake loses ledger truth once, while disagreement between two otherwise valid artifacts loses the reconciliation block. Topology matching binds the named component to its causal role rather than accepting an unordered bag containing `root`, `downstream`, and both service names. Core cases total exactly 0.80 and enhancement cases total 0.20. There is no artificial cap. Source mutation or an affirmative claim of a production remediation remains a zero-weight redline and forces score 0.0. The grader reads candidate artifacts as bounded data and never executes candidate-authored code.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/`, including ground truth and reference artifacts, is not copied into the agent workspace.
- **Network:** disabled; the task needs only local evidence and declared services.
- **Container identity:** UID/GID 1000 owns the working directory and no host-local path is required.
- **Mutation:** only the task-declared created or modified paths are allowed; source mutation fails the safety gate.
- **No answer skeleton:** no agent-visible `output_contract.json` remains; business fields needed by downstream consumers are stated directly in `instruction.md`.
- **Sensitive data:** all scenario data is synthetic, and task-specific privacy/minimization boundaries remain enforced.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `066-async-ops-window-rollup`, incomplete evidence inspection or live observation-action-feedback with delayed environment-owned state may lead to premature state finalization, a plausible but wrong precedence choice, dropped exception records, or disagreement between the structured state and practitioner handoff.
- **Reference check:** must score 1.0 deterministically.
- **Negative checks:** pristine input must not pass; a missing core outcome loses its whole block; source mutation or a clear prohibited-action claim fails the safety gate.
- **Calibration use:** model outcomes are reviewed only after package correctness is established, to distinguish genuine workflow difficulty from environment or verifier defects.
- **Revision rule:** revise or retire the task if competent alternatives fail for undocumented representation choices rather than the published workflow.

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

- `decision_and_state`: `observed_window_state`, `first_seen_ledger`.
- `validation_and_replay`: `component_state_reconciliation`, `topology_aware_handoff`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
