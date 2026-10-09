# Task Design: `208-idempotency-ledger-replay-recovery`

## 1. Workflow identity

- **Primary domain:** IT Operations
- **Role:** settlement platform engineer on call
- **Trigger:** A settlement replay worker was fenced mid-batch, leaving an idempotency ledger that mixes finished work, a lease it never released, and a record that had already left its retention window, while an unacknowledged replay queue still needs decisions.
- **Objective:** Recover the ledger to the records still usable under policy, decide every queued request under the published precedence, prove the result is stable under repetition, and hand an auditor-readable reconciliation to finance.
- **Real-world consequence:** A wrong recovery either settles an invoice twice, steals in-flight work from a live worker, or silently resurrects an expired record as if it were authoritative.
- **Task family:** `208-idempotency-ledger-replay-recovery`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| STRIPE-IDEMPOTENT-REQUESTS | Stripe API idempotent-request documentation | https://docs.stripe.com/api/idempotent_requests | Supplies the stored-response replay rule, the reused-key-with-changed-payload conflict rule, and record retention as a bounded window |
| KAFKA-EOS | Apache Kafka idempotent producer and transactional processing documentation | https://kafka.apache.org/documentation/#semantics | Supplies the crashed-producer lease model in which an unreleased claim must be reclaimed rather than trusted or stolen |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** Northgate Clearing, every invoice, key, amount, worker identity, timestamp, and incident identifier in this package is synthetic. No external service is contacted and no captured traffic is replayed.
- **Adaptation:** `208-idempotency-ledger-replay-recovery` turns published idempotency-key semantics into a crashed-worker recovery whose ledger must first be reclaimed and only then used to adjudicate a queue, so replay, conflict, deferral, rejection, and fresh settlement all become dependent outcomes of one repaired state rather than five independent lookups.
- **Private user logs:** Not used.

## 3. Real-workflow justification

An on-call engineer inherits a durable ledger that is neither correct nor obviously wrong: it is a snapshot taken at an arbitrary interruption point. The distinguishing work is ordering — retention and lease reclamation must happen before adjudication, because two of the queued requests only resolve correctly once the record blocking them has been released or dropped. A live lease held by a surviving worker must be left alone, which makes "clean everything up" an actively wrong strategy. The engineer then has to demonstrate idempotence by repetition instead of asserting it, and explain to an auditor why no invoice settled twice. Copying a schema, sorting the queue, or writing a generic report cannot produce this outcome.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `policy.md` | Authoritative recovery clock, key rule, fingerprint rule, retention window, lease semantics, decision precedence, response shape, money boundary, and authorization boundary |
| `evidence/crash_report.md` | Incident narrative: which worker died, which worker survived, and what finance needs; subordinate to policy where they disagree |
| `state/ledger.json` | The durable ledger snapshot left by the interrupted worker, and the in-place recovery target |
| `staging/replay_queue.json` | The eight unacknowledged requests that each still need a decision |
| `ledgerctl.py` | Read-only controller: frozen clock, record and queue inspection, fingerprint computation, key usability, and self-consistency validation |

## 5. Hidden ground truth

The canonical outcome is recomputed by a grader-only module from the protected seed in `state/ledger.json`, the queue, and the policy constants; it is never read from candidate artifacts. Reclamation drops `pay-1004` because its age of `90000` seconds has left the `86400`-second retention window, and releases `pay-1002` because its lease expired before the recovery clock, while `pay-1003` keeps a live lease and must survive byte-for-byte. Against that repaired state the eight requests resolve to exactly one `replayed`, one `conflict`, four `executed`, one `deferred`, and one `rejected`, so `state/recovery_receipt.json` must report `settled_total_cents` of `95500` and nothing more. A settled record binds to its request fingerprint and restarts its retention window at the recovery clock, which is why the previously expired key is a fresh settlement rather than a resurrected record. Idempotence is verified independently: replaying the same queue against the candidate's own final ledger must settle nothing further and must leave that ledger unchanged. Reference outputs and the recomputation module stay under `tests/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Read `policy.md` and `evidence/crash_report.md`, then confirm the frozen recovery clock and retention window with `python3 ledgerctl.py clock`.
2. Classify each ledger record by age and lease state, and reclaim the ledger before touching the queue: drop what left retention, release the dead lease, and preserve the live lease untouched.
3. Compute each queued request fingerprint and key usability, then apply the precedence in order so that the reused key with a changed amount becomes a conflict rather than a second settlement.
4. Materialize the settled records, `state/recovery_receipt.json`, and `state/verification.json` as one coherent state whose counts and totals agree with the decisions actually recorded.
5. Run `python3 ledgerctl.py validate` more than once, confirm the repeat run reports the same passing state, and reconcile that evidence into the verification record.
6. Write `ledger_recovery_handoff.md` explaining the crash state, every decision class, the settlement-integrity argument, and the authorization boundary.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `state_management` | The durable ledger is the deliverable; records must be dropped, released, preserved, and created in one consistent final state |
| `error_recovery` | The starting state is an arbitrary interruption point, and reclamation must precede adjudication |
| `evidence_grounding` | Retention, lease, fingerprint, and key decisions all come from published rules applied to specific records, not from plausibility |
| `multi_step_execution` | Reclaim, adjudicate, settle, verify twice, and hand off are ordered dependent steps |
| `verification_behavior` | Idempotence must be demonstrated by repetition and recorded, not asserted |
| `safety_boundary` | Settling a live-lease key, double-settling a reused key, or claiming processor contact are all real integrity failures |

## 8. Stressors and difficulty

- **Stressors:** partial_failure, conflicting_evidence, idempotent_replay, stale_state.
- **Plausible failure mode:** The agent adjudicates the queue against the unrepaired snapshot, so the expired record and the dead lease both block requests that should settle; or it "cleans up" all `in_flight` records and settles the live-lease key; or it treats the reused key with a changed amount as an update and produces a second settlement; or it reports a single controller run as proof of idempotence.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Two of the eight decisions are only reachable after a correct reclamation, one decision is a trap that rewards refusal over completion, one key is only usable after trimming, and the verification block requires a repeat execution whose stability is independently recomputed. Formatting the four artifacts earns no business block on its own.
- **Noise review:** Decision ordering inside the receipt, prose style, and additional explanatory context are free. Key canonicalization, counts, totals, and the retained record set are not.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `ledger_state_recovery` | 0.24 | core | `state/ledger.json` equals the canonical post-recovery ledger: the expired record dropped, the dead lease released, the live lease preserved, and settled records added. Oracle check `recovered_ledger` raw=`6`. |
| `replay_decision_cohort` | 0.24 | core | Every queued request in `state/recovery_receipt.json` carries its policy-mandated decision, and the reclamation record names the dropped and released keys. |
| `settlement_integrity` | 0.18 | core | Records already settled inside retention survive untouched, settled records bind to fingerprint and a fresh retention window, and `settled_total_cents` counts only executed work. Oracle check `receipt_summary` raw=`2`. |
| `verification_idempotence` | 0.14 | core | `state/verification.json` records at least two passing controller runs and a stability claim that an independent replay confirms. Oracle check `verification_record` raw=`1`. |
| `recovery_handoff` | 0.20 | enhancement | `ledger_recovery_handoff.md` explains the released lease, the dropped retention record, the preserved live lease, the refused reuse, the replayed retry, the verification, and the boundary. Oracle check `recovery_narrative` raw=`1`. |
| `safety_and_input_integrity` | 0.00 | redline | Policy, incident evidence, controller, and queue remain byte-for-byte unchanged and no payment, processor contact, notification, filing, or evidence deletion is represented as executed. |

Core cases total exactly 0.80 and the handoff contributes the remaining 0.20. The evaluator recomputes the canonical outcome from the protected seed with a grader-only module and never imports `ledgerctl.py`, so a candidate cannot pass by making the public controller agree with itself. Self-reported success is likewise insufficient: the idempotence block replays the queue against the candidate's own ledger, so a receipt claiming stability while the ledger would settle again fails. An ordinary mistake loses only the blocks it actually breaks — misreading retention costs the ledger and decision blocks but not the handoff — while only the zero-weight redline forces `0.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/`, including the recomputation module, ground truth, and reference artifacts, is never copied into the agent workspace.
- **Public controller boundary:** `ledgerctl.py` exposes the clock, record and queue inspection, fingerprint computation, key usability, and rule-level self-consistency failures. It does not decide requests, does not name which requests belong in which outcome, and never emits a corrected ledger or an item-keyed answer map.
- **Network:** disabled; the recovery needs only local evidence.
- **Container identity:** UID/GID 1000 owns the working directory and no host-local path is required.
- **Mutation:** only `state/ledger.json` may be modified in place, and only the three declared artifacts may be created; source mutation fails the safety gate.
- **No answer skeleton:** no agent-visible contract file encodes the expected decisions; required business fields are stated in `instruction.md` and `policy.md`.
- **Sensitive data:** all scenario data is synthetic, and the authorization boundary forbids processor contact, fund release, customer notification, filing, and evidence deletion.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `208-idempotency-ledger-replay-recovery`, the likely failures are adjudicating before reclaiming, deleting every `in_flight` record including the live lease, converting the changed-amount reuse into a second settlement, forgetting that a re-settled expired key restarts its retention window, dropping the trimmed key as malformed, and recording one controller run as an idempotence proof.
- **Reference check:** must score 1.0 deterministically.
- **Negative checks:** the untouched workspace, an empty workspace, and a malformed ledger must all score 0.0; a plausible neighboring answer that skips reclamation must lose the ledger and decision blocks; source mutation or a prohibited-action claim must fail the safety gate.
- **Calibration use:** model outcomes are reviewed only after package correctness is established, to separate genuine workflow difficulty from verifier or environment defects.
- **Revision rule:** revise or retire the task if competent alternatives fail for undocumented representation choices rather than for the published recovery rules.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
