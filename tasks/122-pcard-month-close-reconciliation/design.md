# Task Design: `122-pcard-month-close-reconciliation`

## 1. Workflow identity

- **Primary domain:** Finance
- **Role:** purchase-card accountant recovering a failed monthly close
- **Trigger:** the local close journal stopped after preparing one disposition while immutable issuer and ERP ledgers remained posted
- **Objective:** parse receipt artifacts, adjudicate every issuer row, recover one source-bound local close, verify it, and stage it pending external approval
- **Real-world consequence:** a wrong close can reimburse unsupported spend, conceal purchase splitting, double-net a refund, or mutate a posted accounting record
- **Task family:** `finance-pcard-close-recovery`
- **Variant:** `interrupted-close-with-receipt-lineage`

## 2. Idea provenance

| Source ID | Public workflow | URL | Use in this task |
|---|---|---|---|
| GAO-PCARD | GAO purchase-card controls and split-purchase findings | https://www.gao.gov/products/gao-08-333 | receipt sufficiency, split-purchase review, cardholder controls |
| IRS-RECEIPTS | IRS accountable-plan substantiation guidance | https://www.irs.gov/publications/p463 | amount, date, place, and business evidence concepts |
| SQLITE-TRANSACTIONS | SQLite transaction semantics | https://www.sqlite.org/lang_transaction.html | atomic local recovery, stable journal, and replay behavior |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** all people, organizations, cards, receipts, approvals, databases, and transactions are synthetic.
- **Adaptation:** the task combines p-card evidence controls with a locally interrupted transactional close and multi-format artifact lineage. It does not copy examples or answers from the public sources.
- **Private user logs:** not used.

## 3. Real-workflow justification

The candidate does not merely populate a CSV. It must inspect three SQLite business systems, parse PDF/HTML/JSON receipt bodies, verify artifact hashes, detect a graph relationship between independently accepted charges, preserve a prior-period refund link, distinguish accepted subtotal from non-reimbursable tax, and consume an interrupted prepare journal in one mutation of the local close database. Executable preview, verification, staging, equivalent replay, and conflict behavior create a genuine observation-action-feedback loop.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `issuer.db` | Immutable current-period card feed with cardholder, merchant, tax, and refund linkage |
| `erp.db` | Immutable posted prior-period original for the refund |
| `acceptance.db` | Immutable department acceptance decisions |
| `receipts/` | Real local PDF, HTML, and JSON receipt artifacts |
| `receipt_manifest.json` | Media types and published SHA-256 lineage for receipts |
| `pcard_policy.md` | Decision precedence, split threshold, tax, recovery, and side-effect rules |
| `close_context.json` | Stable business close identity, period, timestamps, and stage boundary |
| `pcard_close_state.db` | Mutable close journal, prepared action, disposition ledger, control edges, and run record |
| `pcardctl.py` | Generic inspect/query/preview/apply/verify/stage/replay controller |

## 5. Hidden ground truth

The evaluator independently opens the candidate `pcard_close_state.db` and result documents. It never imports, invokes, or executes `pcardctl.py`. Fixture-specific expected transactions remain hidden, while the public controller derives decisions from SQLite rows, parsed receipt bodies, acceptance evidence, ERP linkage, and published policy. Required final workspace state includes seven keyed `transaction_dispositions`, one `split_edges` relationship, one `refund_links` row, one committed `close_runs` row, a committed `close_journal`, and no `prepared_actions`. Key invariants are cent conservation, immutable posted ledgers, one row per transaction ID, stable `close_id`/source checkpoint binding, and a single semantic plan digest. The evaluator accepts action and evidence ordering differences and binds replay to business identity plus semantic decisions, not JSON bytes.

## 6. Expected workflow

1. Run `pcardctl.py inspect/query` against `issuer.db`, `erp.db`, `acceptance.db`, `receipts/`, and the interrupted `pcard_close_state.db` journal.
2. Author one source-grounded action per issuer transaction in `reconciliation_plan.json`, bound to `close_id` and the reported source checkpoint.
3. Run `pcardctl.py preview reconciliation_plan.json`; repair coverage, policy precedence, receipt hashes, and evidence locators from transaction-specific controller feedback. Documented table aliases (`acceptance`/`acceptance_decisions`, `postings`/`posted_card_transactions`) and the queried split-graph pair are normalized as equivalent local evidence, while preview names any still-missing durable locator.
4. Apply `reconciliation_plan.json` twice, then verify the committed `transaction_dispositions`, split edge, refund link, and consumed prepared action into `pcard_verification.json`.
5. Write `close_handoff.md`, create `pcard_stage_receipt.json`, and run full replay to prove `pcard_close_state.db` and the stage receipt are byte-stable.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `multi_step_execution` | evidence inspection, planning, preview, mutation, verification, staging, and replay are dependent |
| `evidence_grounding` | every disposition needs SQLite and receipt-lineage locators |
| `state_management` | recovery mutates a normalized local SQLite close, not just prose |
| `error_recovery` | a prepared-but-uncommitted disposition must be consumed exactly once |
| `verification_behavior` | verification and stage receipts bind semantic plan, sources, and logical state |
| `safety_boundary` | issuer/ERP postings and evidence are immutable; external posting remains pending |

## 8. Stressors and difficulty

- **Stressors:** missing receipt, three media parsers and hashes, accepted charges that still form a split graph, separately held tax, prior-period refund lineage, missing acceptance, partial journal, and replay conflict rules.
- **Plausible failure mode:** trusting filenames without parsing, clearing accepted split charges, holding the whole taxed charge, netting the refund against current exceptions, treating prepared as posted, or using raw plan bytes as replay identity.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** correct completion requires reasoning across four persistent stores and five artifacts, then satisfying coupled conservation and durable-state invariants.
- **Noise review:** JSON formatting, action order, evidence order, SQLite page layout, and prose wording are not graded as exact reference bytes.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `source_bound_transaction_adjudication` | 0.22 | core | exact transaction coverage, dispositions, evidence, stable identity, and source checkpoint |
| `committed_close_ledger` | 0.25 | core | one normalized disposition row per issuer transaction with conserved cents |
| `split_tax_and_refund_controls` | 0.18 | core | explicit split edge, separate tax exception, and prior-period refund link |
| `stable_identity_and_replay` | 0.15 | core | one commit/run, consumed prepare state, normalized semantic digest, and source binding |
| `verification_and_local_stage` | 0.12 | enhancement | deterministic verification and stage receipts bind the logical close |
| `reviewer_handoff` | 0.08 | enhancement | reviewable transaction/evidence/recovery/offline explanation |
| `source_and_external_safety` | 0.00 | redline | all protected sources unchanged, no unexpected artifact, and no external-action claim |

The four core cases total exactly 0.80. The evaluator treats candidate-authored files strictly as data and catches malformed JSON/SQLite without crashing.

Artifact ownership is explicit: `reconciliation_plan.json` owns source-bound adjudication; `pcard_close_state.db` owns the committed ledger, graph, refund link, journal, and run; `pcard_verification.json` independently summarizes controller checks; `pcard_stage_receipt.json` owns the pending external boundary and digests; `close_handoff.md` owns the human-review explanation.

The deterministic handoff check accepts bounded semantic wording classes for
hash verification, replay stability, and the still-pending ERP boundary; it
does not require the reference answer's exact phrases.

## 10. Leakage, isolation, and safety review

- Public `pcardctl.py` contains generic derivation rules but no fixture final disposition, amount, split-edge, or refund-result map.
- A seed-mutation regression adds acceptance for a formerly unaccepted charge and verifies that preview derives the changed decision.
- Hidden reference artifacts and fixture truth stay under `tests/`.
- Only `pcard_close_state.db` may change; plan, verification, stage receipt, and handoff may be created.
- Different source checkpoints or semantic decisions under the committed close identity are rejected without mutation.

## 11. Pilot plan

Relative to `121-three-way-invoice-match`, this task (1) reconciles card-feed transactions rather than PO/receipt/invoice triples, (2) parses heterogeneous receipt files and content hashes, (3) detects a connected same-cardholder split graph, and (4) recovers an interrupted close with stable replay identity instead of staging invoice review. Relative to `055-financial-close-reconciliation`, it (1) works at card-transaction/evidence granularity rather than general-ledger account totals, (2) preserves prior-period refund lineage rather than resolving statement variances, (3) enforces acceptance and tax substantiation, and (4) mutates a durable recovery journal with conflict semantics.

- Contract tests require reference 1.0, pristine/malformed 0.0, source-tamper gating, split/refund discrimination, core-only 0.80, equivalent replay byte stability, documented locator-alias equivalence, object-specific preview diagnostics with no mutation, conflict rejection, evaluator independence, and seed mutation.
- **Expected Gemma/OpenClaw failure modes:** stopping after document production, overlooking the acceptance database, treating acceptance as a split-policy waiver, failing PDF text extraction, using raw JSON hashes for replay, or omitting the second apply/replay verification.
- A real Gemma 4 31B + OpenClaw pilot is still required before admission. Candidate model outcomes diagnose usability but do not determine selection.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## Scoring-group revision (Standard207)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `source_bound_transaction_adjudication`, `committed_close_ledger`.
- `validation_and_replay`: `split_tax_and_refund_controls`, `stable_identity_and_replay`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
