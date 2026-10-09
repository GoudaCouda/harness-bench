# Task Design: `038-public-assistance-validation-repair`

## 1. Workflow identity

- **Primary domain:** Business Operations
- **Role:** disaster-grant payment-integrity analyst
- **Trigger:** a sampled Public Assistance reimbursement request has conflicting and late supporting evidence
- **Objective:** validate exact cost lines, apply corrections and non-duplication reductions, preserve unresolved holds, and stage a non-disbursed request with replay proof
- **Real-world consequence:** unsupported or duplicated costs create improper payments, while overbroad rejection delays otherwise supported recovery work
- **Task family:** `public-assistance-validation-repair`
- **Variant:** `mixed-cost-evidence-and-duplicate-benefit`

## 2. Idea provenance

| Source ID | Source | URL | Adaptation |
|---|---|---|---|
| FEMA-VAYGO | Validate As You Go Guide | https://www.fema.gov/sites/default/files/documents/fema_pa-validate-as-you-go-guide.pdf | sampled transaction testing, supporting-document reconciliation, financial-system traceability, and retention of the full sample |
| FEMA-PAPPG-V5 | Public Assistance Program and Policy Guide v5 | https://www.fema.gov/sites/default/files/documents/fema_public-assistance-program-and-policy-guide_v5_june2024.pdf | actual-cost evidence and reductions for insurance or other designated assistance for the same purpose |

- **Origin class:** public_workflow_adaptation.
- **Synthetic-data statement:** All applicant, disaster, project, cost-line, document, payment, insurance, award, and amount records are synthetic.
- **Private user logs:** Not used.
- **Adaptation:** FEMA payment-validation mechanics become a synthetic
  multi-cost grant sample whose evidence precedence, duplicate-benefit
  reductions, held exceptions, staged state, and replay receipt must reconcile.

## 3. Real-workflow justification

Payment-integrity analysts reconcile the sampled transaction with the source ledger and the cost-type-specific evidence chain, retain unsupported lines for correction, and prevent duplicated assistance before disbursement. This task is distinct from insurance-claim adjudication, program eligibility, and generic ledger repair: its primary unit is a multi-cost grant-payment sample and its final state is staged but explicitly not posted.

## 4. Agent-visible inputs

| Input | Authority |
|---|---|
| `evidence/sample.json` | sampled identities and claimed amounts |
| `evidence/financial_ledger.json` | paid amounts and unapplied credits |
| `evidence/labor_records.json` | hours, rates, fringe, and approval evidence |
| `evidence/contract_documents.json` | procurement, invoice supersession, change-order, rental, and payment document chains |
| `evidence/benefit_sources.json` | insurance allocations and other-award purpose/amount |
| `policy/validation_policy.json` | evidence requirements, authority precedence, reductions, statuses, and non-disbursement boundary |
| `state/payment_request.json` | mutable pending request |
| `grant_lib.py`, `grantctl.py` | inspection, validation, staging, and replay feedback |

## 5. Hidden ground truth

The evaluator independently derives each line. Complete labor validates from hours, rate, and fringe; unsigned overtime remains held. Contracted debris uses the signed corrected invoice/change order rather than the superseded transcription and subtracts same-scope insurance. Equipment rental subtracts the unapplied vendor credit once. Documented supplies are excluded because another federal award is designated for the same items. Control totals and receipt digests are recomputed from immutable evidence and normalized rows.

The final state starts from `evidence/sample.json` and requires a consistent
`work/line_review.json`, `work/exception_register.json`,
`state/payment_request.json`, `work/validation_receipt.json`, and
`work/grant_handoff.md`; line keys, totals, stage status, and receipt digests are
independent invariants.

## 6. Expected workflow

1. Inspect `evidence/sample.json`, policy, payment state, and each line's evidence.
2. Resolve invoice supersession and compute keyed amounts in `work/line_review.json`.
3. Preserve held/excluded keys and reasons in `work/exception_register.json`.
4. Use `grantctl.py` feedback to correct evidence, status, reduction, or totals.
5. Stage `state/payment_request.json` through the controller without disbursement.
6. Replay twice, confirm `work/validation_receipt.json` is byte-stable, and
   write `work/grant_handoff.md`.

## 7. Harness demands

The task requires multi-source reconciliation, arithmetic, authority precedence, exception preservation, duplicate-benefit analysis, protected state mutation, tool feedback, idempotence, and an irreversible-payment safety boundary.

## 8. Stressors and difficulty

Plausible failures include trusting the superseded invoice, ignoring or double-subtracting insurance/credit, manufacturing a labor approval, treating a designated same-purpose award as unrelated, dropping held/excluded rows, matching only totals, or claiming disbursement. Difficulty arises from dependent evidence and control closure rather than bulk.

- **Plausible failure mode:** match only the aggregate total while using a
  superseded invoice or dropping held rows, so line-level payment state is not
  defensible.
- **Difficulty rationale:** source authority, arithmetic, exception retention,
  staged mutation, receipt binding, and replay must close as dependent stages.

## 9. Oracle design

Core cases total 0.80: sample/document scope 0.20, independent calculations/reductions 0.25, holds/exclusions 0.15, and staged request/receipt/replay closure 0.20. The grant handoff is optional 0.20 with bounded semantic fallback only for equivalent prose. A gate enforces immutable sources/controllers, declared outputs, no fabricated approval, and no submission/disbursement claim. Row order is irrelevant.

Required artifacts are covered by those blocks: `work/line_review.json` and
`work/exception_register.json` capture adjudication; `state/payment_request.json`
and `work/validation_receipt.json` establish staged/replay closure; and
`work/grant_handoff.md` is the bounded communication case.

## 10. Leakage, isolation, and safety review

The environment is synthetic and offline with no credentials, external grant system, or payment rail. Reference artifacts and tests are hidden. The controller can only stage local state. Source edits, manual final-state fabrication, hazardous workspace entries, invented signatures, and external-action claims fail; ordinary extra regular files are only reported as diagnostics.

## 11. Pilot plan

Expected Gemma/OpenClaw failures are amount-only matching, missed document supersession, missing duplication reduction, approving unsigned labor, or stopping before replay. The package remains `hold` until adversarial tests, suite and leakage checks, and a fresh trace agree with observed state and score. Model outcome remains diagnostic evidence only.

- **Expected Gemma/OpenClaw failure modes:** amount-only matching, missed
  supersession, missing reduction, invented approval, manual state editing, or
  stopping before replay and receipt verification.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Semantic equivalence policy

Line IDs, amounts, evidence relationships, corrections, reductions, statuses, exception types, control totals, and receipt digests are exact; keyed row and evidence-ID order are irrelevant. Evidence-grounded line reasons and requested actions may use equivalent wording. Handoff wording is semantic but cannot compensate for operational errors.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `sample_and_document_scope`, `costs_and_reductions`.
- `validation_and_replay`: `holds_and_exclusions`, `staged_request_and_replay`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
