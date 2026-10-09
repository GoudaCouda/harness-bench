# Task Design: `061-three-source-decision-record-synthesis`

## 1. Workflow identity

- **Primary domain:** Business Operations
- **Role:** a business operations coordinator
- **Trigger:** Task: Synthesize a Three-Source Decision Record
- **Objective:** Three-Source Decision Record from Meeting, Email, and Documents
- **Real-world consequence:** An incorrect `action_items.csv` would make the synthetic `Three-Source Decision Record from Meeting, Email, and Documents` handoff incomplete or operationally misleading.
- **Task family:** `061-three-source-decision-record-synthesis`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-061 | Retrospective HarnessBench project record | https://www.harness-bench.ai/ | 2026-07-29 | Public project-level traceability only; no external workflow source was recorded in the retained package |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** Retrospective `061-three-source-decision-record-synthesis` reconstruction: the checked-in package transforms `docs`, `docs/finance_constraints.md`, `docs/legal_notes.md`, `docs/product_requirements.md`, `docs/security_review.md`, `email/thread.json`, and 2 other entries listed in Section 4 into `action_items.csv`, `decision_record.json`, `source_conflicts.csv`, preserving the visible action `Task: Synthesize a Three-Source Decision Record` and `docs` as the first concrete state anchor; `format` as the first reference-path scoring anchor. The original external idea source was not recorded and is not inferred.
- **Private user logs:** Not used.

## 3. Real-workflow justification

`Three-Source Decision Record from Meeting, Email, and Documents` models a Business Operations handoff in which the agent must reconcile `docs`, `docs/finance_constraints.md`, `docs/legal_notes.md`, `docs/product_requirements.md`, `docs/security_review.md`, `email/thread.json`, and 2 other entries listed in Section 4, apply the visible rule/state clauses `'final_decisions' items must include 'decision_key', 'value', 'status', 'winning_source', and 'evidence_signal'.`; `Do not treat brainstorms or meeting proposals as final approval.`; `Preserve unresolved questions instead of inventing a final decision.`, and leave `action_items.csv`, `decision_record.json`, `source_conflicts.csv` as an auditable final state. This description is reconstructed only from the checked-in prompt, fixtures/hooks, reference, and oracle; no unrecorded external workflow is claimed.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `docs` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `docs/finance_constraints.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `docs/legal_notes.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `docs/product_requirements.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `docs/security_review.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `email/thread.json` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `meeting/meeting_transcript.md` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |
| `source_priority.md` | Agent-visible factual working material; explicitly named in the prompt | Reconcile under the explicit prompt rules; no unstated source priority |

## 5. Hidden ground truth

- `061-three-source-decision-record-synthesis` truth reconciliation binds concrete source state `docs`, `docs/finance_constraints.md`, `docs/legal_notes.md`, `docs/product_requirements.md`, `docs/security_review.md`, `email/thread.json`, and 2 other entries listed in Section 4 to required final state `action_items.csv`, `decision_record.json`, `source_conflicts.csv`; hidden materials are ground_truth.json, oracle_grade.py, reference.
- Visible key/state/precedence clauses retained by the oracle-facing design are: `'final_decisions' items must include 'decision_key', 'value', 'status', 'winning_source', and 'evidence_signal'.`; `Do not treat brainstorms or meeting proposals as final approval.`; `Preserve unresolved questions instead of inventing a final decision.`.
- `ground_truth.json` exposes maintainer keys `decisions`, `rejected_options`, `open_questions`, `actions`, `conflict_terms`, `forbidden_final_tokens`, `scoring`; exact values remain isolated from the agent workspace.
- Reference `action_items.csv` has exact header `action_id`, `owner`, `due_date`, `action`, `status`, `source_file`, `evidence_signal`, 4 data row(s); `action_id` values begin `customer_notice`, `mode_b_checklist`, `budget_memo`, `legal_addendum`.
- Reference `decision_record.json` has top-level keys `decision_id`, `final_decisions`, `rejected_options`, `open_questions`; collection sizes `final_decisions[5]`, `rejected_options[3]`, `open_questions[2]`; state/key anchors `decision_id='DR-001'`.
- Reference `source_conflicts.csv` has exact header `decision_key`, `winning_source`, `superseded_sources`, `resolution_reason`, `priority_rule` and the public closed key set `launch_date`, `deployment_mode`, `budget_cap`, `feature_scope`; missing, duplicate, or invented conflict keys are invalid.
- The relocated legacy fact library retains its historical dimensions for diagnostics only. Formal score ownership belongs to the seven business-level cases in Section 9; ordinary output defects fail the cases that consume the affected decision, conflict, or action record.

## 6. Expected workflow

1. Inventory the actual starting state in `docs`, `docs/finance_constraints.md`, `docs/legal_notes.md`, `docs/product_requirements.md`, `docs/security_review.md`, `email/thread.json`, and 2 other entries listed in Section 4; for `061-three-source-decision-record-synthesis`, do not substitute an unstated network or host source.
2. Execute visible workflow clause 1 against `docs`: Task: Synthesize a Three-Source Decision Record.
3. Execute visible workflow clause 2 against `docs`: Create:.
4. Execute visible workflow clause 3 against `docs`: Preserve unresolved questions instead of inventing a final decision..
5. Materialize the complete declared state `action_items.csv`, `decision_record.json`, `source_conflicts.csv`; preserve the prompt-declared IDs, headers, schema keys, and in-place paths.
6. Cross-reconcile `action_items.csv` with every other declared artifact and the source state `docs`; check shared identifiers, counts, decisions, and status transitions where present.
7. Run local parse/structure checks for `action_items.csv`, `decision_record.json`, and `source_conflicts.csv`; confirm that identifiers, winners, owners, dates, and open questions reconcile across all three records.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | High-scoring outputs must connect decisions to local task evidence. |
| `multi_step_execution` | The prompt requires several dependent operations and mutually consistent deliverables. |
| `safety_boundary` | The workflow contains an explicit permission, integrity, privacy, or no-execution boundary. |

## 8. Stressors and difficulty

- **Stressors:** conflicting_evidence, dirty_input, high_stakes_rules
- **Plausible failure mode:** For `Three-Source Decision Record from Meeting, Email, and Documents`, the agent may create `action_items.csv` but fail the declared `evidence_grounding` demand over `docs`, violate the rule/state clause `'final_decisions' items must include 'decision_key', 'value', 'status', 'winning_source', and 'evidence_signal'.`, or leave another required deliverable inconsistent.
- **Provisional difficulty:** hard
- **Difficulty rationale:** The task requires the agent to apply source authority separately to schedule, security, finance, and legal scope; preserve rejected proposals and unresolved staffing; and keep three downstream artifacts mutually usable. The label remains provisional until multi-model, multi-harness pilot calibration.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `schedule_and_deployment` | 0.20 | core | The later email sets July 15 and formal security selects mode B, with the correct winning source and decisive signal. |
| `financial_and_legal_scope` | 0.20 | core | Formal finance sets the USD 180000 cap and formal legal excludes real-time export from first launch. |
| `approval_gate` | 0.10 | core | Product signoff, security approval, finance clearance, and legal review remain explicit readiness requirements. |
| `rejections_and_open_questions` | 0.10 | core | Three superseded proposals are rejected with reasons and both unresolved staffing questions remain open. |
| `conflict_handoff` | 0.10 | core | Exactly four conflict rows each identify their own winner, losing sources, resolution, and applicable priority rule. |
| `action_handoff` | 0.10 | core | Exactly four current actions retain their owner, date, pending status, source, and decisive evidence. |
| `record_integrity` | 0.20 | enhancement | The decision package follows the published structures with closed, unique decision/rejection/open-question sets. |
| `safety_and_input_integrity` | 0.00 | redline | Supplied evidence is unchanged and no prohibited external action is represented as executed. |

The private evaluator exposes decision-, rejection-, conflict-, and action-level assertions; its historical fractional formula does not contribute to the formal score. A final decision's value, authority, status, and decisive evidence form one usable business result and therefore pass or fail together. The conflict ledger is evaluated per decision rather than by corpus-wide keyword counts: a finance term placed in a legal row cannot repair the finance row, and invented rows fail the closed-set check. Ordinary precedence mistakes and missing ordinary records lose their owning cases; they are not safety gates and there is no cap. Core outcomes total 0.80 and structural package quality contributes 0.20 optional credit. Protected-source mutation or a true task-specific redline remains the only zero-weight safety override.

Artifact coverage is explicit: `decision_record.json` owns final decisions, rejected options, approval gates, open questions, and package integrity; `source_conflicts.csv` owns the four precedence-conflict handoffs; `action_items.csv` owns the four current practitioner actions.

- **Order/format tolerance:** Structured rows are keyed and unordered unless ordering is itself part of the workflow.
- **Conflict-ledger equivalence:** Each public conflict key must have exactly one row identifying its actual winning and superseded sources and applicable precedence. Wording may vary, but sources and causal relationships may not be borrowed from another row.
- **Row-context equivalence:** A conflict row whose key and verified source columns already identify the disputed schedule may say that the later email superseded the meeting date without repeating `June 20`. Likewise, the customer-notice action's evidence may use the locally unambiguous word `notice`, but it must still preserve the June 5 date; row context cannot excuse a missing business fact.
- **Source-locator equivalence:** Canonical paths and basenames remain valid, but an unambiguous human-readable citation such as `Security Review (SEC-2)` or `Email (email-004)` is equivalent when its visible source family and record ID resolve to the same supplied evidence. A citation to the wrong source family or wrong record, an invented fragment on an otherwise-correct basename, or an explicitly negated source claim still loses source credit.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** checked-in `ground_truth.json` (when present), `oracle_grade.py`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited; source/input integrity remains part of the checked-in oracle contract.
- **Destructive-action guard:** For `061-three-source-decision-record-synthesis`, perform only the isolated workspace actions named in the prompt; never infer production execution, external communication, credentials, or network authority.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Agent omits `action_items.csv` while attempting `Three-Source Decision Record from Meeting, Email, and Documents`.; Agent misreads the `061-three-source-decision-record-synthesis` rule/state anchor `'final_decisions' items must include 'decision_key', 'value', 'status', 'winning_source', and 'evidence_signal'.` while reconciling `docs`.; Agent violates the prompt-stated safety boundary while producing `action_items.csv`, `decision_record.json`, `source_conflicts.csv`.
- **Pilot repair note:** The first Gemma/OpenClaw diagnostic used bare record IDs as `evidence_signal`. Because the oracle measures decisive evidence text, the prompt now states that a short supporting phrase is required and a bare ID is insufficient. The reference was also repaired to include every prompt-declared `status` field and structured `open_questions`; the oracle now validates those visible schemas.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots for the next additive release.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** For `061-three-source-decision-record-synthesis`, retain this reconstruction until Human review checks the prompt/reference/oracle alignment; revise provenance or executable definitions only in a separately authorized change if ambiguity, leakage, brittle lexical grading, or an unnecessary harness demand is confirmed.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.


## Refine70 formal outcome audit

This task now uses business-level all-or-nothing cases. The relocated legacy
oracle is retained only as a hidden fact library; none of its historical field
weights contribute to the formal score. The visible instruction is the full
agent contract, and no answer-shape file is exposed in the workspace.

- `schedule_and_deployment` (core): Schedule and deployment follow their governing sources.
- `financial_and_legal_scope` (core): Finance and legal constraints govern their domains.
- `approval_gate` (core): The full readiness gate is preserved.
- `rejections_and_open_questions` (core): Rejected proposals and unknowns remain visible.
- `conflict_handoff` (core): Each source conflict has a correct row-level resolution.
- `action_handoff` (core): Current work is handed off with owners, dates, status, and evidence.
- `record_integrity` (optional): The three-file decision package is structurally closed.

The core cases total 0.80 and optional handoff quality totals 0.20. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `schedule_and_deployment`, `financial_and_legal_scope`.
- `validation_and_replay`: `approval_gate`, `rejections_and_open_questions`, `conflict_handoff`, `action_handoff`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
