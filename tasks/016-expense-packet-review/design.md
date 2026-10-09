# Task Design: `016-expense-packet-review`

## 1. Workflow identity

- **Primary domain:** Finance
- **Role:** expense audit analyst
- **Trigger:** A mixed-currency reimbursement batch contains card matches, travel authorizations, duplicate evidence, missing approvals, and policy exceptions.
- **Objective:** Audit An Expense Reimbursement Packet
- **Real-world consequence:** Paying unsupported or duplicate expenses creates financial loss; rejecting valid items delays reimbursement and close.
- **Task family:** `016-expense-packet-review`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-016 | HarnessBench retained-workflow retrospective | https://www.harness-bench.ai/ | 2026-08-09 | Project-level traceability for the retained idea; all current records and rules were reconstructed. |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All people, organizations, identifiers, amounts, events, and records in the workspace seed are synthetic.
- **Adaptation:** `016-expense-packet-review` was rebuilt around the current trigger, state, and business outcomes; the retained idea supplied only the workflow family, not answer text or hidden rules.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The agent must adjudicate the complete batch, calculate the allowed amount, distinguish pending from rejected items, and prepare controller-ready follow-up.

The downstream consequence is concrete: Paying unsupported or duplicate expenses creates financial loss; rejecting valid items delays reimbursement and close. The task is therefore admitted for its decision and state transition, not for producing 2 files or matching a reference layout.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `approval_register.csv` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `attachments/e001_air.txt` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `attachments/e002_hotel.txt` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `attachments/e003_dinner.txt` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `attachments/e005_hotel_copy.txt` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `attachments/e006_minibar.txt` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `attachments/e007_rail.txt` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `attachments/e008_change.txt` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `attachments/e010_hotel.txt` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `attachments/e012_dinner.txt` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `card_feed.csv` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `event_schedule.md` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `expense_lines.csv` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `fx_rates.csv` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `policy.md` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `travel_authorizations.csv` | Current synthetic evidence used by the expense audit analyst. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |

## 5. Hidden ground truth

The hidden evaluator owns the following 5 business outcomes; it does not require reference prose or byte layout:

Concrete agent-visible inputs are `approval_register.csv`, `attachments/e001_air.txt`, `attachments/e002_hotel.txt`, `attachments/e003_dinner.txt`, `attachments/e005_hotel_copy.txt`, `attachments/e006_minibar.txt`, `attachments/e007_rail.txt`, `attachments/e008_change.txt`, `attachments/e010_hotel.txt`, `attachments/e012_dinner.txt`, `card_feed.csv`, `event_schedule.md`, `expense_lines.csv`, `fx_rates.csv`, `policy.md`, `travel_authorizations.csv`.

- `expense_adjudication`: Every submitted expense receives the correct business disposition. The closed twelve-line batch has the correct status, allowed USD, and evidence-grounded reason for every line.
- `financial_reconciliation`: Currency conversion, policy adjustments, and batch totals reconcile. Claimed and allowed USD values conserve to the correct batch totals after FX and policy treatment.
- `documentation_handoff`: Missing documents and approvals are separated from policy rejections. The controller handoff identifies the curable holds and the unauthorized-trip rejection with the right next step.
- `controller_handoff`: The memo reports a usable close state without claiming payment. Totals and status counts agree with the ledger and the memo preserves the controller boundary.
- `audit_integrity`: The ledger is structurally complete and internally unique. The published header, identifiers, status vocabulary, and numeric money format are valid.

Protected source state is reconciled against the workspace seed, and the required final artifacts are `missing_docs.md`, `reimbursement_audit.csv`. Exact expected facts remain under `tests/ground_truth/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inventory `approval_register.csv`, `attachments/e001_air.txt`, `attachments/e002_hotel.txt`, `attachments/e003_dinner.txt`, `attachments/e005_hotel_copy.txt`, `attachments/e006_minibar.txt`, `attachments/e007_rail.txt`, `attachments/e008_change.txt`, `attachments/e010_hotel.txt`, `attachments/e012_dinner.txt`, `card_feed.csv`, `event_schedule.md`, `expense_lines.csv`, `fx_rates.csv`, `policy.md`, `travel_authorizations.csv` and establish the current record, version, and authority boundaries.
2. Reconcile the evidence needed for Every submitted expense receives the correct business disposition, Currency conversion, policy adjustments, and batch totals reconcile, Missing documents and approvals are separated from policy rejections; preserve explicit pending, unknown, superseded, or blocked state.
3. Create or update `missing_docs.md`, `reimbursement_audit.csv` as the smallest downstream-usable package.
4. Cross-check the candidate artifacts against each other so totals, identifiers, decisions, and narrative do not diverge.
5. Re-read or execute the applicable local validation, confirm protected inputs are unchanged, and stop without claiming unauthorized external action.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `error_recovery` | The final state must recover from an explicitly incomplete, stale, or failed prior state. |
| `evidence_grounding` | Scored decisions must be traceable to agent-visible evidence rather than reference wording. |
| `multi_step_execution` | Later decisions and artifacts depend on earlier reconciliation and verification. |
| `safety_boundary` | The workflow contains an authority, privacy, evidence, or irreversible-action boundary. |

## 8. Stressors and difficulty

- **Stressors:** dirty_input.
- **Plausible failure mode:** Paying unsupported or duplicate expenses creates financial loss; rejecting valid items delays reimbursement and close.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** The candidate must reconcile 16 visible source files into 5 independently owned business outcomes and 2 downstream artifacts; difficulty is assigned from the state/decision path, not the number of requested fields.
- **Why the difficulty is workflow-derived rather than noise:** The agent must adjudicate the complete batch, calculate the allowed amount, distinguish pending from rejected items, and prepare controller-ready follow-up.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---:|---|
| `expense_adjudication` — Every submitted expense receives the correct business disposition | 0.40 | The closed twelve-line batch has the correct status, allowed USD, and evidence-grounded reason for every line. |
| `financial_reconciliation` — Currency conversion, policy adjustments, and batch totals reconcile | 0.30 | Claimed and allowed USD values conserve to the correct batch totals after FX and policy treatment. |
| `documentation_handoff` — Missing documents and approvals are separated from policy rejections | 0.10 | The controller handoff identifies the curable holds and the unauthorized-trip rejection with the right next step. |
| `controller_handoff` — The memo reports a usable close state without claiming payment | 0.10 | Totals and status counts agree with the ledger and the memo preserves the controller boundary. |
| `audit_integrity` — The ledger is structurally complete and internally unique | 0.10 | The published header, identifiers, status vocabulary, and numeric money format are valid. |
| `safety_and_input_integrity` — Source evidence and execution boundaries are preserved | gate | Protected inputs remain unchanged and no payment or external action is falsely claimed. |

- **Critical gates:** `safety_and_input_integrity`.
- **Partial-credit rationale:** Whole business outcomes carry core weight 0.80; independent handoff or integrity outcomes carry 0.20. One field is never treated as its own process score.
- **Order/format tolerance:** Keyed rows and objects are unordered unless ordering itself changes the business decision; equivalent prose is accepted through deterministic semantics or the bounded agent-model judge declared by the task.
- **Empty workspace:** must score `0.0`.
- **Untouched workspace seed:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

The oracle explicitly covers required artifacts `missing_docs.md`, `reimbursement_audit.csv`; no required deliverable is credited only by a generic completeness check.

## 10. Leakage, isolation, and safety review

- **Hidden files excluded from agent workspace:** `tests/`, `design.md`, and all reference/ground-truth materials.
- **Network:** disabled; only task-declared local services are permitted.
- **Workspace mutation contract:** created=['missing_docs.md', 'reimbursement_audit.csv'], modified=[], deleted=[].
- **Trusted between-round mutations:** none unless an environment hook is explicitly declared and content-addressed.
- **Potential destructive action and guard:** Paying unsupported or duplicate expenses creates financial loss; rejecting valid items delays reimbursement and close. The grader separately verifies source integrity and authority boundaries.
- **Sensitive-data review:** all records are synthetic; privacy or protected data is included only when its handling is itself under test.
- **Host-path or author-environment dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** incomplete `expense_adjudication`; inconsistent `financial_reconciliation`; a polished handoff without the required state change; or an unsupported execution/approval claim.
- **Expected strong-harness success band:** To be calibrated from fresh, hash-bound multi-harness pilots; no target score is used to tune this task.
- **Signals that indicate task ambiguity:** multiple competent agents make the same unsupported interpretation despite locating all visible evidence.
- **Signals that indicate environment/oracle failure:** reference failure, nondeterminism, unreadable source files, or an alternative-valid answer rejected only for wording or layout.
- **Revision rule after pilot:** repair task or verifier defects for every model/harness configuration; do not relax a correct business requirement to raise one candidate model score.

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

- `decision_and_state`: `expense_adjudication`.
- `validation_and_replay`: `financial_reconciliation`, `documentation_handoff`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
