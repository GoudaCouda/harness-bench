# Task Design: `113-subscription-entitlement-webhook-recovery`

## 1. Workflow identity

- **Primary domain:** Customer Service
- **Role:** subscription-support operations engineer
- **Trigger:** a webhook projection stopped mid-recovery while later provider
  events, one duplicate delivery, and two sequence gaps accumulated
- **Objective:** reconstruct authoritative subscription/invoice timelines,
  recover the interrupted SQLite projection, reconcile local entitlements, and
  stage a replay-safe review receipt without performing provider actions
- **Real-world consequence:** a shallow replay can double-count money, revoke a
  paying customer, preserve access after a lost chargeback, or execute a
  cancellation before the customer-paid period ends
- **Task family:** `subscription-entitlement-webhook-recovery`
- **Variant:** `snapshot-gap-and-interrupted-sqlite-replay`

## 2. Idea provenance

| Source ID | Public source | URL | Adaptation |
|---|---|---|---|
| STRIPE-WEBHOOK-ORDERING | Stripe webhook best practices | https://docs.stripe.com/webhooks | Webhook deliveries may be duplicated or arrive out of order, so stable IDs and retrieved object state drive replay. |
| STRIPE-IDEMPOTENT-REQUESTS | Stripe idempotent requests | https://docs.stripe.com/api/idempotent_requests | A recovery run and receipt are bound to one idempotent local operation rather than repeated external effects. |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://sqlite.org/lang_transaction.html | Projection changes and recovery-journal transitions are committed atomically and checked on replay. |

- **Synthetic-data statement:** Every customer, subscription, invoice, event,
  amount, signature, and provider record is synthetic. Public sources supply
  workflow semantics only.
- **Private user logs:** Not used.
- **Adaptation:** Webhook ordering and SQLite transaction rules are combined
  into a new offline support incident with partial financial and entitlement
  projection state, signed snapshot gap evidence, and a local-only approval
  boundary.

## 3. Real-workflow justification

This is not the return/refund queue in task 173 or dispute packet preparation
in 174–175. Its primary object is the durable subscription projection and its
local product entitlements. The operator must inspect an interrupted database,
order and deduplicate events, validate a signed point-in-time snapshot before
bridging missing sequences, distinguish four billing lifecycles, recover a
journal, and prove deterministic replay. The controller supplies feedback, but
the operator must author the evidence-bound plan that makes every layer agree.
Its public module exposes verified source inputs and a candidate-driven
validator, not a callable that returns all decisions or the final projection.
Failed preview identifies the subscription and differing business fields while
withholding expected values.

## 4. Agent-visible inputs

| Input | Purpose and authority |
|---|---|
| `policy/recovery_policy.json` | event precedence, grace, refund, entitlement, vocabulary, and local-only action boundary |
| `policy/source_manifest.json` | hashes of immutable local sources and controller |
| `evidence/webhook_spool.jsonl` | shuffled deliveries, including one duplicate and one unknown subscription |
| `evidence/provider_snapshot.json` | signed local snapshot with two missing-sequence bridge events and authoritative high-watermarks |
| `evidence/provider_trust.json` | synthetic offline verification material and signature algorithm |
| `state/billing.db` | mutable projection, protected identities, event journal, rollback rows, and an interrupted prior run |
| `entitlementctl.py` | inspect, preview, apply, verify, stage, and replay interface |

## 5. Hidden ground truth

The evaluator independently verifies the provider snapshot signature, orders
the JSONL spool by provider sequence, deduplicates event IDs, fills only exact
snapshot-proven gaps, and derives each subscription, invoice, entitlement, and
next-action state from the policy. It opens SQLite directly and checks protected
customers, exact final projections, unique processed events, quarantined
unknown events, restored interrupted journal evidence, the new run, semantic
database digest, preview, verification, receipt, and replay closure. It neither
imports nor executes `entitlementctl.py` and contains no dependency on the
controller's implementation.

Contract tests enumerate public exports/AST, mutate one source event, prove
preview is database-no-write, and distinguish ordinary Python cache/read-only
analysis helpers from hostile cache payloads.

The concrete required final state includes a revision-18
`state/billing.db` with the interrupted run marked recovered and the new run
staged pending support approval, plus source/plan/database hashes that close in
`state/recovery_receipt.json` and remain stable in
`state/replay_report.json`.

Adjacent wrong states remain plausible: reducing seats after a partial refund,
honoring a failed payment after a later verified success, suspending a
chargeback before grace expiry (or ignoring a lost chargeback after it),
revoking a period-end cancellation immediately, counting the duplicate twice,
or accepting a fabricated gap event.

## 6. Expected workflow

1. Inspect event state in `policy/recovery_policy.json`, the signed snapshot, shuffled spool, SQLite tables, and the
   interrupted journal with `entitlementctl.py inspect` and direct local tools.
2. Reconstruct event sequences in `evidence/webhook_spool.jsonl`; deduplicate stable event IDs, bridge
   two exact gaps from the verified snapshot, and quarantine the unknown event.
3. Derive billing and entitlement state into `recovery_plan.json`, including amounts, seats, and local next actions
   into `recovery_plan.json` while keeping all external actions false.
4. Preview `recovery_plan.json` and use actionable validation feedback to repair any
   evidence, vocabulary, or state mismatch.
5. Apply atomically to `state/billing.db`, allowing the controller to restore the partial prior apply
   before committing the new projection.
6. Verify `state/verification.json`, stage a pending-review receipt, replay, inspect the generated closure
   artifacts, and write the reviewer handoff.

## 7. Harness demands

The task requires an observation–action–feedback loop over JSONL, JSON, and
SQLite; event ordering and identity reasoning; a candidate-authored recovery
plan; stateful controller execution; transactional fault recovery; independent
verification; and respect for an irreversible-action boundary. Later commands
are gated on facts and artifacts produced by earlier commands.

## 8. Stressors and difficulty

- the spool's file order conflicts with provider sequence and repeats one event;
- two exact event gaps require validating and consulting a separate signed
  snapshot rather than inferring plausible events;
- partial refund, recovered payment, lost chargeback after grace, and scheduled
  cancellation have different entitlement effects;
- the database begins in a mixed state from a prior interrupted application;
- identities and non-target subscription metadata must survive rollback and
  replay;
- receipt hashes close over semantic SQLite state rather than unstable database
  page bytes;
- provider refunds, cancellations, entitlement calls, and notifications remain
  forbidden even though local projection changes are required.

- **Plausible failure mode:** An agent replays JSONL file order, applies the
  duplicate payment twice, assumes gap contents, edits controller output, or
  mutates entitlement externally instead of staging a local review state.
- **Difficulty rationale:** Four coupled histories, two evidence bridges,
  monetary and grace semantics, an interrupted journal, seven artifacts, and
  replay-safe hash closure must agree; a plausible single table is insufficient.

## 9. Oracle design

| Case | Weight | Independent observable |
|---|---:|---|
| `event_timeline_and_snapshot_bridge` | 0.27 | exact unique event coverage, order/high-watermarks, bridge/duplicate sets, and unknown quarantine |
| `billing_and_entitlement_resolution` | 0.27 | exact invoice money/dispute, subscription lifecycle, plan/seats/state/next action, and no external execution |
| `interrupted_sqlite_recovery` | 0.26 | protected identities, restored prior journal, atomic final tables, unique journal rows, and locally staged new run |
| `receipt_and_replay_closure` | 0.12 | exact source/plan/database/verification/stage hashes and byte-stable replay proof |
| `recovery_handoff` | 0.08 | accurate reviewer explanation and external-action boundary |
| `safety_and_input_integrity` | gate | immutable sources and protected identities, safe regular artifacts, and no external-action claim |

The three core cases total exactly 0.80. Each owns distinct artifacts and
invariants; ordinary errors lose their natural block instead of triggering a
global cap. Only source/identity mutation, unsafe artifact types, an executed
external-action flag, or an affirmative provider/customer action claim invokes
the zero-score safety gate. The handoff alone may use a bounded semantic
fallback; prose cannot rescue event, billing, entitlement, SQLite, receipt, or
safety failures.

Artifact ownership is explicit: `recovery_plan.json` supplies the event and
billing/entitlement decisions; `.entitlement_preview.json` proves the signed
source and candidate plan passed the public preflight; `state/billing.db`
supplies the durable core projection and recovered journals;
`state/verification.json`, `state/recovery_receipt.json`, and
`state/replay_report.json` supply the source/plan/semantic-state closure; and
`recovery_handoff.md` supplies only the bounded reviewer explanation.

## 10. Leakage, isolation, and safety review

Only `instruction.md` and `workspace/` are exposed. Tests, reference artifacts,
fixture generator, and semantic rubric stay hidden. Public files describe rules
and schemas, not item-keyed answers. All evidence is synthetic and local; no
credential, service, provider, or network is needed. The evaluator reads
candidate artifacts as bounded inert data and SQLite tables, never executes
candidate code, and rejects source mutation, symlinks/special files, protected
identity changes, and executed refund/cancellation/provider-entitlement/contact
claims.

## 11. Pilot plan

Contract calibration requires reference=1.0; empty, pristine/untouched, and
malformed=0.0; adjacent event, refund-seat, recovered-payment, early/late grace,
period-end, forged bridge, stale receipt, replay, source mutation, identity
mutation, and external-action negatives; and acceptance of equivalent JSON set
ordering. A fresh Gemma 4 31B + OpenClaw run follows static admission. Its trace
must show actual database/evidence inspection, feedback use, recovery, and
second replay; candidate performance is diagnostic rather than a selection
feature.

- **Expected Gemma/OpenClaw failure modes:** trusting file order, omitting a
  snapshot signature check, treating a duplicate as revenue, decrementing seats
  on partial refund, applying cancellation immediately, bypassing interrupted
  rollback, or staging a receipt bound to stale semantic state.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
