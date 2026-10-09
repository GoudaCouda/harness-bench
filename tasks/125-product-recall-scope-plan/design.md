# Task Design: `125-product-recall-scope-plan`

## 1. Workflow identity

- **Primary domain:** Business Operations / product-safety supply chain
- **Role:** product-safety operations coordinator
- **Trigger:** a local recall worker stopped after preparing an event, followed by a superseding signed scope and at-least-once shipment feed
- **Objective:** recover one source-bound recall transaction across genealogy, lots, inventory, shipments, channels, journal, verification, and local staging
- **Real-world consequence:** wrong scope can release suspect stock, stop safe stock, double-move inventory, or imply an unauthorized external notice
- **Task family:** `product-recall-transaction-recovery`
- **Variant:** `superseding-scope-with-interrupted-stop-sale-stage`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| FDA-RECALL-OPERATIONS | FDA industry guidance on product recalls | https://www.fda.gov/safety/industry-guidance-recalls | Grounds recall scope, effectiveness, and accountable handoff concepts |
| GS1-TRACEABILITY | GS1 traceability standard | https://www.gs1.org/standards/traceability | Grounds product/lot/batch genealogy and event linkage |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Grounds the offline durable recovery and replay mechanism |

- **Origin class:** public-workflow adaptation with synthetic local records.
- **Synthetic-data statement:** every company, product, lot, batch, shipment, channel, key, time, and event is synthetic.
- **Adaptation:** `125-product-recall-scope-plan` combines public recall operations, lot/batch traceability, and SQLite transactions into a new offline recovery environment with synthetic evidence and failure state.
- **Private user logs:** not used.

## 3. Real-workflow justification

This is not a recall spreadsheet. The operator must choose an authorized scope,
traverse component ancestry, retain uncertainty, adjudicate an at-least-once
feed, and then use a stateful controller to mutate a local operational database.
Preview, a crash journal, transaction identity, replay behavior, independent
verification, and an offline stage receipt form a feedback-dependent recovery
loop. Actual notification, stop-sale, refund, and reroute remain prohibited.

Historical weak recall prototypes contributed scope selection, at-least-once
event handling, customer/channel handoff boundaries, and version/authority
conflict control. Those archived prototypes are provenance only; their old
numbers do not refer to the current Standard207 tasks with those numbers.

## 4. Agent-visible inputs

| Input/tool | Purpose |
|---|---|
| `recall.db` | Real mutable SQLite lots, genealogy, inventory, shipments, channels, event ledger, quarantine, transaction, and journal state |
| `recall_seed.sql` | Protected baseline used by the public verifier to recompute terminal state |
| `recall_checkpoint.json` | Stable `recall_id`, immutable source-state digest, and prepared action |
| `signed_scope_revisions.json` | Trusted keys, signed supersession chain, draft distractor, target batches, material, window, and descendant rule |
| `shipment_events.jsonl` | Out-of-order events, exact duplicate, stale events, and unknown shipment |
| `recall_policy.md` | Published genealogy, feed, operational, replay, and external-action rules |
| `recallctl.py` | Read-only inspect/query plus preview/apply/verify/stage feedback loop |

## 5. Hidden ground truth

The evaluator opens candidate `recall.db` read-only and compares exact logical
table state, `recall_plan.json` action semantics, transaction identity, journal closure,
conservation, receipts, and source integrity. It independently normalizes the
business plan and never imports, executes, or trusts `recallctl.py`. Candidate
verification booleans cannot award credit without matching authoritative state.
Open handoff wording has a bounded one-case semantic fallback after deterministic
shape and safety checks; no safety, scope, ID, count, state, or digest is judged
by an LLM.

The required final state has `LOT-A`, `LOT-B`, and `LOT-E` quarantined as
affected, `LOT-D` quarantined pending trace, one committed `RC-2026-0417`
transaction, and receipts bound to that terminal database and semantic plan.

## 6. Expected workflow

1. Inspect `recall_checkpoint.json`, `signed_scope_revisions.json`, `shipment_events.jsonl`, and the lot/genealogy/shipment tables in `recall.db`.
2. Resolve trusted `SCOPE-02` and write every lot/event decision with evidence into `recall_plan.json`, preserving `LOT-D` as `pending_trace`.
3. Run `recallctl.py preview`; use the returned scope, coverage, evidence, or sequence checks to repair the plan.
4. Apply once to mutate `recall.db`, then reorder action/evidence lists and prove equivalent `RC-2026-0417` replay is byte-stable and idempotent.
5. Produce `recall_verification.json` and `recall_handoff.md`, then create and replay `recall_stage_receipt.json`.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `multi_step_execution` | Later apply, replay, verify, and stage depend on earlier inspection and plan feedback |
| `evidence_grounding` | Signed authority, genealogy, sequences, and checkpoint jointly determine decisions |
| `state_management` | SQLite inventory, shipment, channel, ledger, transaction, and journal state all change coherently |
| `error_recovery` | A prepared journal plus redelivery must become exactly one commit |
| `verification_behavior` | Independent state checks and bound receipts are required after mutation |
| `safety_boundary` | Only offline drafts/holds are allowed; no real recall action occurs |

## 8. Stressors and difficulty

- **Stressors:** signed revision precedence, mixed/descendant/out-of-window genealogy, unresolved parent, out-of-order and duplicate events, unknown entity, prepared journal, authority gate, semantic replay.
- **Nearest correct alternative:** action and evidence lists may be reordered and formatted differently; it remains the same business plan and replays idempotently.
- **Nearest wrong alternative 1:** treating unsigned SCOPE-03-DRAFT as current wrongly affects safe/out-of-window lots.
- **Nearest wrong alternative 2:** guessing CB-UNK is descended from CB-77 wrongly changes LOT-D from pending trace to affected.
- **Nearest wrong alternative 3:** binding idempotency to raw JSON causes reordered equivalent actions to mutate inventory twice.
- **Plausible failure mode:** the agent follows row order, accepts SCOPE-03-DRAFT, clears the unresolved parent, applies an event twice, or treats a local draft as external execution; each produces a different observable database or safety state.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** success requires several dependent observations, thirteen reconciled decisions, a real multi-table mutation, crash-journal closure, semantic replay, and independent verification rather than hidden schema or output bulk.
- **Noise review:** JSON/action/evidence ordering and formatting are ignored; business identifiers, scope, state, conservation, and external-action boundaries remain exact.
- **Evidence interface:** preview names missing evidence by lot/event. Published
  policy-heading spelling variants and controlling-revision locator variants
  normalize to the same local evidence. An absent shipment requires event and
  policy evidence, not a fabricated database-absence locator.

### Nearest-neighbor portfolio contribution

| Neighbor | At least four substantive differences |
|---|---|
| `118-warehouse-reservation-recovery` | product-safety scope authority; component ancestry; event-sequence feed; channel stop/draft states; unresolved genealogy; recall handoff rather than order fulfillment |
| `135-bom-engineering-change-propagation` | incident recall rather than engineering release; signed supersession rather than ECO approval; inventory/shipment/channel mutation; crash journal/replay; explicit no-notice boundary |
| archived weak recall prototypes | replaces shallow CSV metrics, hotline classification, and version-only scripts with mutable multi-table recovery, signed scope, genealogy, operational events, conservation, and replay |

The package changes role, trigger, authoritative state, tools, state transition,
failure feedback, and terminal handoff. Current Standard207 tasks are assessed
from their own packages rather than from superseded numeric labels.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `signed_scope_genealogy_and_plan` | 0.22 | core | exact lot dispositions, source binding, evidence, and lot state |
| `event_feed_and_shipment_state` | 0.18 | core | unique event dispositions, ledger/quarantine, selected sequences, shipment stops |
| `inventory_lot_and_channel_closure` | 0.22 | core | exact inventory/channel state plus nonnegative conservation |
| `transaction_journal_and_replay` | 0.18 | core | one stable-ID transaction closes the prepared journal and binds semantic plan/checkpoint |
| `verification_and_local_stage` | 0.12 | enhancement | receipts bind final logical database, plan, verification, and offline phase |
| `recall_handoff` | 0.08 | enhancement | reviewable factual handoff with bounded semantic fallback |
| `safety_and_input_integrity` | 0.00 | redline | sources unchanged, no unexpected outputs, no external execution claim |

Core weight is exactly `0.80`. Each core has at least one neighboring mutation
regression. Reference, pristine, empty, malformed, protected-source mutation,
equivalent replay, conflicting replay, stale checkpoint, conservation, receipt
forgery, public seed mutation, and semantic-builder failures are contracts.

Artifact coverage is explicit: `recall.db` owns operational and recovery state;
`recall_plan.json` owns source-bound lot/event adjudication;
`recall_verification.json` binds independent local checks;
`recall_stage_receipt.json` binds the offline stage; and `recall_handoff.md`
owns the reviewable product-safety explanation.

## 10. Leakage, isolation, and safety review

- The public controller derives scope, genealogy, event dispositions, final state, and receipts from visible inputs; it contains no literal lot-to-answer or event-to-answer map.
- A seed-mutation contract changes a batch relation and proves public preview/verify recompute a different legitimate outcome.
- `tests/` and reference outputs are hidden from the agent workspace.
- Candidate code is never executed by the evaluator; database reads use SQLite read-only mode.
- Network is unnecessary and all operational effects are local.
- Protected sources/controller remain byte-for-byte unchanged; only `recall.db` is mutable.

## 11. Pilot plan

- Reference must score 1.0; pristine, empty, and malformed workspaces must score 0 without mutation.
- Contracts cover every core neighboring error, source/external gates, public seed mutation, equivalent and conflicting replay, receipt forgery, evaluator independence, and semantic-builder runner behavior.
- **Expected Gemma/OpenClaw failure modes:** accepting the unsigned draft, following feed order, missing descendant/mixed scope, guessing the unresolved parent, using incomplete evidence, confusing local staging with external execution, or omitting semantic replay.
- After package freeze, a real Gemma 4 31B + OpenClaw pilot must preserve the complete observation/action/feedback/revision/verification trace under a new run identity.
- Model outcome diagnoses task/interface quality only; it is not a task-only membership label. Revise or retire if failure comes from undocumented representation rather than published business rules.

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

- `decision_and_state`: `signed_scope_genealogy_and_plan`, `event_feed_and_shipment_state`.
- `validation_and_replay`: `inventory_lot_and_channel_closure`, `transaction_journal_and_replay`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
