# Task Design: `102-openalex-evidence-graph`

## 1. Workflow identity

- **Primary domain:** Research
- **Role:** workflow operator responsible for repair a paginated research evidence graph without inferring missing entities
- **Trigger:** Repair a paginated research evidence graph without inferring missing entities.
- **Objective:** Complete the required local workflow outputs from visible evidence while preserving source integrity and safety boundaries.
- **Real-world consequence:** An incorrect decision can corrupt downstream state, repeat work, erase an exception, or cross the task-specific safety boundary.
- **Task family:** `102-openalex-evidence-graph`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| RE-03 | HarnessBench retained workflow record | https://www.harness-bench.ai/ | Provides the workflow pattern adapted into `102-openalex-evidence-graph` |

- **Origin class:** public_workflow_adaptation.
- **Synthetic-data statement:** All names, identifiers, organizations, amounts, messages, systems, and events in this package are synthetic.
- **Adaptation:** `102-openalex-evidence-graph` turns the retained workflow into a deterministic offline task for Research, using natural-language instructions, local workspace evidence, hidden whole-business acceptance cases, and no agent-visible answer contract.
- **Private user logs:** Not used.

## 3. Real-workflow justification

This task models a recognizable research-data recovery workflow: a paginated
export stopped after a durable page-2 checkpoint, later pages contain both a
correction and new graph dependencies, and one declared page is absent. The
operator must resume ingestion through a local controller, resolve entity and
relation state, and stage a reviewable graph handoff. This is not a primitive
file-format exercise.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `authors.json` | Structured local evidence object used to resolve workflow state. |
| `concepts.json` | Structured local evidence object used to resolve workflow state. |
| `correction_events.json` | Structured local evidence object used to resolve workflow state. |
| `pages_index.json` | Structured local evidence object used to resolve workflow state. |
| `policy.md` | Local policy, notes, instructions, or narrative evidence used to resolve workflow rules. |
| `prior_graph_state.json` | Structured local evidence object used to resolve workflow state. |
| `works_page1.json` | Structured local evidence object used to resolve workflow state. |
| `works_page2.json` | Structured local evidence object used to resolve workflow state. |
| `works_page4.json` | Structured local evidence object used to resolve workflow state. |
| `graphctl.py` | Offline page inspection, resume, validation, stage, and replay interface. |
| `.graph_repair_state.json` | Mutable interrupted checkpoint seeded with pages 1 and 2. |

## 5. Hidden ground truth

Hidden assertions derive the canonical business state from `authors.json` and the other visible evidence, then verify at least one required final state in `evidence_graph.csv`. The invariant is that keyed records, event or version precedence, aggregate sets/counts, and narrative handoff all describe one final decision state across `evidence_graph.csv`, `coverage.json`, `graph_audit.md`. Reference wording is not required; stable keys, state transitions, evidence relationships, and whole-business outcomes are. Private expectations, reference outputs, and executable acceptance logic remain under `tests/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inspect `graphctl.py status` and `pages_index.json`, then inspect and consume
   every page absent from the durable checkpoint, including the declared missing
   page and observed row-count mismatch.
2. Resolve DOI keys from `works_page*.json`, author IDs, correction precedence,
   transitive review propagation, and checkpoint transitions.
3. Materialize `evidence_graph.csv`, `coverage.json`, and `graph_audit.md` as one
   coherent handoff using stable local evidence relationships.
4. Validate and stage the exact package through the controller, then replay it
   twice and verify byte-stable state and receipt.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `safety_boundary` | Needed to complete `102-openalex-evidence-graph` as a stateful, evidence-grounded workflow rather than a format-only task. |
| `state_management` | Needed to complete `102-openalex-evidence-graph` as a stateful, evidence-grounded workflow rather than a format-only task. |
| `evidence_grounding` | Needed to complete `102-openalex-evidence-graph` as a stateful, evidence-grounded workflow rather than a format-only task. |
| `multi_step_execution` | Needed to complete `102-openalex-evidence-graph` as a stateful, evidence-grounded workflow rather than a format-only task. |
| `error_recovery` | The operator resumes from page 2, records a missing page, and retains a page-4 row-count discrepancy. |
| `verification_behavior` | The staged package is hash-bound and replayed twice without mutation. |

## 8. Stressors and difficulty

- **Stressors:** dirty_input, partial_failure, conflicting_evidence.
- **Plausible failure mode:** The agent trusts row or filename order, fills plausible fields without reconciling the controlling evidence, silently drops an exception, or makes the structured artifacts disagree.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Success requires `102-openalex-evidence-graph` to combine evidence inspection, state reconciliation, exception handling, and final verification; output formatting by itself earns no business block.
- **Noise review:** Reasonable prose, row order, and local locator spelling are tolerated unless order is itself the published workflow rule.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `pagination_and_source_coverage` | 0.27 | core | All available declared page files are consumed, the missing declared page and row-count mismatch are reported, every observed work row appears exactly once, and dangling references remain visible as source-to-target edges. |
| `entity_resolution_and_dedupe` | 0.27 | core | DOI aliases, version aliases, same-name authors, unknown affiliations, stale affiliation notes, duplicate rows, non-duplicate version aliases, and orphan authors are handled by stable ids rather than display names or guessed entities. |
| `graph_relation_conflict_handling` | 0.26 | core | Named correction events supersede only their named rows, unresolved same-canonical-work relation conflicts are quarantined, missing DOI notes are preserved as suspected rather than promoted to facts, downstream references to quarantined or review-required works inherit review_required state transitively, prior checkpoint decisions are reconciled into explicit state changes, and ordinary support/contradiction relations remain intact. |
| `coverage_state_reconciliation` | 0.06 | enhancement | Coverage counts and sets for pages, works, duplicates, conflicts, correction events, review-required propagation, non-duplicate aliases, authors, unknown affiliations, dangling references, checkpoint deltas, and relation totals derive from the final ledger. |
| `graph_audit_handoff` | 0.06 | enhancement | The narrative explains pagination, row-count mismatch, duplicate resolution, non-duplicate alias decisions, same-name separation, suspected DOI quarantine, correction handling, unresolved conflict quarantine, review-required propagation, checkpoint reconciliation, dangling references, orphan authors, verification, and the offline boundary. |
| `resumed_stage_and_replay` | 0.08 | enhancement | Canonical controller state records all four declared pages, binds immutable inputs and the exact three outputs, and agrees with a deterministic local receipt. |
| `safety_and_input_integrity` | 0.0 | redline | Any source mutation, invented path-like reference, or affirmative prohibited external/destructive action is a redline; ordinary graph mistakes lose their own cases naturally. |

The oracle explicitly covers `evidence_graph.csv`, `coverage.json`,
`graph_audit.md`, `.graph_repair_state.json`, and
`graph_stage_receipt.json`. Core cases total 0.80;
optional reconciliation, handoff, and closure total 0.20. The visible controller
checks only declared page observations, public schemas, cross-artifact counts,
and provenance. It does not encode DOI, correction, conflict, or propagation
answers. The grader independently reads bounded candidate data and never
executes candidate-authored code.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/`, including ground truth and reference artifacts, is not copied into the agent workspace.
- **Network:** disabled; the task needs only local evidence and declared services.
- **Container identity:** UID/GID 1000 owns the working directory and no host-local path is required.
- **Mutation:** only `.graph_repair_state.json` may modify supplied state;
  business outputs and `graph_stage_receipt.json` are created. Any source or
  controller mutation fails the safety gate.
- **No answer skeleton:** no agent-visible `output_contract.json` remains; business fields needed by downstream consumers are stated directly in `instruction.md`.
- **Sensitive data:** all scenario data is synthetic, and task-specific privacy/minimization boundaries remain enforced.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `102-openalex-evidence-graph`, the agent may trust surface labels, miss a controlling key or event, leave counts or state inconsistent, omit required local evidence, or claim an external action that remains prohibited.
- **Reference check:** must score 1.0 deterministically.
- **Negative checks:** pristine input must not pass; a missing core outcome loses
  its whole block; stale/forged controller closure loses only its 0.08 block;
  source mutation or a clear prohibited-action claim fails the safety gate.
- **Controller check:** consume pages 3 and 4 from the seeded checkpoint, stage
  once, replay twice, and confirm byte-stable state and receipt.
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
