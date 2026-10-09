# Task Design: `072-migration-graph-repair`

## 1. Workflow identity

- **Primary domain:** Software Engineering
- **Role:** framework migration maintainer
- **Trigger:** Two accepted branches created competing migration heads and the draft merge is not safe on fresh, upgrade, repeat, and reverse paths.
- **Objective:** Make the smallest repository repair, run the local validator, and leave a maintainer-ready explanation of the graph and rollback behavior.
- **Real-world consequence:** An incorrect decision can corrupt downstream state, repeat work, erase an exception, or cross the task-specific safety boundary.
- **Task family:** `072-migration-graph-repair`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| SE-04 | HarnessBench retained workflow record | https://www.harness-bench.ai/ | Preserves the workflow identity while the package and evaluation are rebuilt |

- **Origin class:** handcrafted synthetic workflow reconstruction.
- **Synthetic-data statement:** All names, identifiers, organizations, amounts, messages, systems, and events in this package are synthetic.
- **Adaptation:** `072-migration-graph-repair` turns the retained idea into repository mutation plus executable forward/reverse verification, with natural-language delivery and hidden whole-business acceptance cases instead of an agent-visible answer contract.
- **Private user logs:** Not used.

## 3. Real-workflow justification

In this workflow, a framework migration maintainer receives imperfect local evidence after a concrete operational trigger: Two accepted branches created competing migration heads and the draft merge is not safe on fresh, upgrade, repeat, and reverse paths. The practitioner must resolve authority, keys, and state before handing an auditable result to another person or downstream system. The distinguishing work is repository mutation plus executable forward/reverse verification; the task cannot be completed by copying a schema or writing a generic report.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `policy.md` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `repo/config.json` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `repo/graph.json` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `repo/sample_rows.json` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `repo/simulate.py` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `repo/validate.py` | Local evidence or trusted executable fixture used to resolve the workflow state |

## 5. Hidden ground truth

Hidden assertions derive the canonical business state from `policy.md` and the other visible evidence, then verify at least one required final state in `repo/config.json`. The invariant is that keyed records, precedence-sensitive events or versions, aggregate sets/counts, and narrative handoff all describe one final decision state. Reference wording is not required; stable keys and whole-business outcomes are. Private expectations, reference outputs, and executable acceptance logic remain under `tests/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inspect `policy.md` and the remaining visible inputs; identify the controlling keys, policy/version precedence, exceptions, and safety boundary.
2. Resolve the business state before writing `repo/config.json`; preserve explicit unknown, blocked, held, unaffected, or already-completed work where the evidence requires it.
3. Materialize `repo/config.json`, `validation.json`, `change_log.md` as one coherent handoff, using stable local evidence relationships rather than file or row order.
4. Re-open every structured final artifact, reconcile keys, sets, counts, and status across files, and verify that immutable source state remains unchanged.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `state_management` | Required to complete repository mutation plus executable forward/reverse verification rather than merely format an answer |
| `error_recovery` | Required to complete repository mutation plus executable forward/reverse verification rather than merely format an answer |
| `multi_step_execution` | Required to complete repository mutation plus executable forward/reverse verification rather than merely format an answer |
| `output_contract` | Required to complete repository mutation plus executable forward/reverse verification rather than merely format an answer |

## 8. Stressors and difficulty

- **Stressors:** partial_failure, long_horizon.
- **Plausible failure mode:** The agent trusts row or filename order, fills plausible fields without reconciling the controlling evidence, silently drops an exception, or makes the structured artifacts disagree.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Success requires repository mutation plus executable forward/reverse verification, cross-artifact state reconciliation, and a final verification pass; output formatting by itself earns no business block.
- **Noise review:** Reasonable prose, row order, and local locator spelling are tolerated unless order is itself the published workflow rule.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `canonical_merge_graph` | 0.25 | core | Trusted graph simulation proves one canonical merge head depending on both accepted branch heads; dependency order is immaterial. |
| `data_migration_safety` | 0.25 | core | Executable fixtures prove historical-model use, repeat safety, preservation of manual values, and a reverse operation that restores only migration-owned values. |
| `replay_safety` | 0.15 | core | Fresh-install and existing-0006 upgrade paths both succeed under the trusted simulator. |
| `validation_evidence` | 0.15 | core | The submitted validation result has the exact public schema and check set, and its passing claim agrees with actual execution. |
| `maintainer_handoff` | 0.20 | enhancement | The change log explains both heads, the minimal repair, historical access, repeat/fresh/upgrade/reverse behavior, local verification, and the production boundary. |
| `safety_and_input_integrity` | 0.00 | redline | Source evidence is preserved and no prohibited external/destructive action is represented as executed. |

The oracle explicitly covers `repo/config.json`, `validation.json`, and `change_log.md`. It loads the candidate configuration strictly as data, then evaluates it with the canonical simulator shipped in the immutable task fixture; candidate-authored Python is never executed. A malformed or semantically wrong graph therefore cannot pass by copying a hidden JSON object or self-reporting `status: pass`. Core cases total exactly 0.80 and the maintainer handoff contributes the remaining 0.20. There is no artificial cap: an ordinary failure loses each independently observable business block it actually breaks. For example, disabling idempotence also overwrites a manual value on the upgrade fixture, so it naturally fails both data safety and upgrade replay. Only the zero-weight safety redline forces score 0.0.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/`, including ground truth and reference artifacts, is not copied into the agent workspace.
- **Network:** disabled; the task needs only local evidence and declared services.
- **Container identity:** UID/GID 1000 owns the working directory and no host-local path is required.
- **Mutation:** only the task-declared created or modified paths are allowed; source mutation fails the safety gate.
- **No answer skeleton:** no agent-visible `output_contract.json` remains; business fields needed by downstream consumers are stated directly in `instruction.md`.
- **Sensitive data:** all scenario data is synthetic, and task-specific privacy/minimization boundaries remain enforced.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `072-migration-graph-repair`, incomplete evidence inspection or repository mutation plus executable forward/reverse verification may lead to premature state finalization, a plausible but wrong precedence choice, dropped exception records, or disagreement between the structured state and practitioner handoff.
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

- `decision_and_state`: `canonical_merge_graph`, `data_migration_safety`.
- `validation_and_replay`: `replay_safety`, `validation_evidence`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
