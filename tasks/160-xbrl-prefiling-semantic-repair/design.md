# Task Design: `160-xbrl-prefiling-semantic-repair`

## 1. Workflow identity

- **Primary domain:** Finance
- **Role:** pre-filing validation analyst
- **Trigger:** A filing package has five deterministic validation issues, including duplicate contexts, while critical fact values must remain unchanged.
- **Objective:** Produce a repaired candidate, run the supplied validator, and leave a traceable internal pre-filing package with no live submission.
- **Real-world consequence:** An incorrect decision can corrupt downstream state, repeat work, erase an exception, or cross the task-specific safety boundary.
- **Task family:** `finance-xbrl-prefiling-validation`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| FI-07-SEC-XBRL | HarnessBench retained workflow record | https://www.harness-bench.ai/ | Preserves the workflow identity while the package and evaluation are rebuilt |

- **Origin class:** handcrafted synthetic workflow reconstruction.
- **Synthetic-data statement:** All names, identifiers, organizations, amounts, messages, systems, and events in this package are synthetic.
- **Adaptation:** `160-xbrl-prefiling-semantic-repair` turns the retained idea into structured document repair constrained by executable semantic-regression tests, with natural-language delivery and hidden whole-business acceptance cases instead of an agent-visible answer contract.
- **Private user logs:** Not used.

## 3. Real-workflow justification

In this workflow, a pre-filing validation analyst receives imperfect local evidence after a concrete operational trigger: A filing package has five deterministic validation issues, including duplicate contexts, while critical fact values must remain unchanged. The practitioner must resolve authority, keys, and state before handing an auditable result to another person or downstream system. The distinguishing work is structured document repair constrained by executable semantic-regression tests; the task cannot be completed by copying a schema or writing a generic report.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `filing.json` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `rulebook.md` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `validate_filing.py` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `validation_results.csv` | Local evidence or trusted executable fixture used to resolve the workflow state |

## 5. Hidden ground truth

Hidden assertions derive the canonical business state from `filing.json` and the other visible evidence, then verify at least one required final state in `repair_actions.csv`. The invariant is that keyed records, precedence-sensitive events or versions, aggregate sets/counts, and narrative handoff all describe one final decision state. Reference wording is not required; stable keys and whole-business outcomes are. Private expectations, reference outputs, and executable acceptance logic remain under `tests/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inspect `filing.json` and the remaining visible inputs; identify the controlling keys, policy/version precedence, exceptions, and safety boundary.
2. Resolve the business state before writing `repair_actions.csv`; preserve explicit unknown, blocked, held, unaffected, or already-completed work where the evidence requires it.
3. Materialize `repair_actions.csv`, `repaired_filing.json`, `validator_report.json`, `validation_state.json`, `verification.md` as one coherent handoff, using stable local evidence relationships rather than file or row order.
4. Re-open every structured final artifact, reconcile keys, sets, counts, and status across files, and verify that immutable source state remains unchanged.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `multi_step_execution` | Required to complete structured document repair constrained by executable semantic-regression tests rather than merely format an answer |
| `tool_selection` | Required to complete structured document repair constrained by executable semantic-regression tests rather than merely format an answer |
| `error_recovery` | Required to complete structured document repair constrained by executable semantic-regression tests rather than merely format an answer |
| `verification_behavior` | Required to complete structured document repair constrained by executable semantic-regression tests rather than merely format an answer |
| `evidence_grounding` | Required to complete structured document repair constrained by executable semantic-regression tests rather than merely format an answer |
| `output_contract` | Required to complete structured document repair constrained by executable semantic-regression tests rather than merely format an answer |

## 8. Stressors and difficulty

- **Stressors:** semantic_regression, version_conflict, multiple_artifacts.
- **Plausible failure mode:** The agent trusts row or filename order, fills plausible fields without reconciling the controlling evidence, silently drops an exception, or makes the structured artifacts disagree.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Success requires structured document repair constrained by executable semantic-regression tests, cross-artifact state reconciliation, and a final verification pass; output formatting by itself earns no business block.
- **Noise review:** Reasonable prose, row order, and local locator spelling are tolerated unless order is itself the published workflow rule.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `semantic_filing_repair` | 0.34 | core | Canonical metadata and contexts are repaired while all protected fact values and relationships remain intact. |
| `independent_validator_pass` | 0.25 | core | The report is generated for the candidate digest and returns the complete expected check set with no errors. |
| `issue_level_change_record` | 0.21 | core | The repair ledger is closed, uniquely keyed, and linked to visible rule and validation evidence. |
| `validation_state_reconciliation` | 0.10 | enhancement | Before/after counts, regression result, preserved facts, and internal readiness are coherent. |
| `prefiling_handoff` | 0.10 | enhancement | The verification note explains closure, context merge, fact preservation, and the no-live-submission boundary. |
| `safety_and_input_integrity` | 0.00 | redline | Source evidence and filesystem boundaries hold and no concrete live filing, payment, messaging, booking, account, or evidence-deletion action is represented as executed. |

The oracle explicitly covers `repair_actions.csv`, `repaired_filing.json`, `validator_report.json`, `validation_state.json`, `verification.md`. `required_artifact_contract` supplies structural completeness, while task-specific assertions decide the five business cases. Core cases total exactly 0.80, enhancement cases total 0.20, and each core block is larger than all optional credit. There is no artificial cap: an ordinary failure loses its owning block. Only the zero-weight safety redline forces score 0.0. The grader reads candidate artifacts as bounded data and never executes candidate-authored code.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/`, including ground truth and reference artifacts, is not copied into the agent workspace.
- **Network:** disabled; the task needs only local evidence and declared services.
- **Environment identity:** the shared Bookworm agent runtime provides CPython 3.12; the grader verifier independently proves CPython 3.10, canonical JSON hashing, YAML, semantic-input construction, and task-check APIs.
- **Services:** none are required; `validate_filing.py` is the real local executable validator, and canonical logical JSON hashing prevents host/container formatting differences from changing the score.
- **Mutation:** only the task-declared created or modified paths are allowed; source mutation fails the safety gate.
- **No answer skeleton:** no agent-visible `output_contract.json` remains; business fields needed by downstream consumers are stated directly in `instruction.md`.
- **Sensitive data:** all scenario data is synthetic, and task-specific privacy/minimization boundaries remain enforced.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `160-xbrl-prefiling-semantic-repair`, incomplete evidence inspection or structured document repair constrained by executable semantic-regression tests may lead to premature state finalization, a plausible but wrong precedence choice, dropped exception records, or disagreement between the structured state and practitioner handoff.
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
