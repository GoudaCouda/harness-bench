# Task Design: `039-task-cancellation-cleanup`

## 1. Workflow identity

- **Domain / role:** Compliance; privacy operations engineer.
- **Trigger:** An identity mismatch is recorded after a DSAR export fanned out; a descendant worker and delivery appeared after the initial job list was captured.
- **Objective:** Reconcile descendant scope, fence new fanout, drain and checkpoint active workers, cancel every scoped job, withdraw cancellable transfers, purge eligible rows/credentials, and retain receipts, legal-hold material, and audit evidence.
- **Consequence:** Partial cancellation can leak data; indiscriminate cleanup can destroy required evidence or unrelated transfer state.

## 2. Idea provenance

- **Source:** [HarnessBench project](https://www.harness-bench.ai/), retrospective workflow ID HB-RETRO-039.
- **Origin class:** handcrafted_synthetic.
- **Synthetic-data statement:** All identities, addresses, IDs, exports, and events are synthetic.
- **Adaptation:** The legacy two-round text exercise was rebuilt around a multi-stage local controller, descendant discovery, a generation fence, lease checkpoint transitions, an append-only audit log, mixed transfer states, deletion semantics, and idempotent verification.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Privacy teams cancel in-flight processing by stable identifiers, stop downstream transfer, purge data copies under retention policy, preserve manifests and audit history, and record a reviewable compliance handoff.

## 4. Agent-visible inputs

| Input | Authority |
|---|---|
| `cancellation_notice.json` | Authoritative identity and required actions for DSAR-8821. |
| `retention_policy.md` | Governs purge versus preservation and external-action boundaries. |
| `control/job_state.json`, `control/queue.json`, `control/worker_leases.json`, `control/fanout_state.json` | Mutable job, transfer, lease and generation-fence state. |
| `control/fanout_index.json` | Immutable parent/descendant evidence that expands the notice scope. |
| `audit/events.jsonl` | Mutable only by append; its original three-event prefix is protected. |
| `staging/` | Purgeable rows/credential, retained receipts and legal-hold evidence. |
| `export_manifest.json`, `export_request.json`, `customer_segments.csv` | Immutable artifact provenance, request scope, and source evidence. |
| `tools/privacyctl.py` | Protected status, cancellation, purge, and verification interface. |

## 5. Hidden ground truth

The agent-visible `control/fanout_index.json` adds export-job-79 to the explicit 77/78 notice scope. In the required final `control/fanout_state.json`, generation 12 is fenced to 13 before leases 77 and 79 in `control/worker_leases.json` reach checkpoint-confirmed release. `control/job_state.json` contains three cancelled jobs; `control/queue.json` contains three withdrawn and two retained-delivery transfers. Four purgeable staging artifacts disappear, retained evidence remains, and `audit/events.jsonl` contains deterministic AUD-700 through AUD-708 once in order. `cleanup_plan.csv`, `cancellation_ledger.csv`, and `privacy_handoff.md` complete the review packet.

## 6. Expected workflow

1. Reconcile the notice, fanout index, jobs, leases, transfers, manifest and audit prefix before changing state.
2. Use `tools/privacyctl.py` to fence child creation, request lease drain and separately confirm checkpoints before cancellation.
3. Classify all seven manifest artifacts, cancel all three jobs, withdraw cancellable transfers and apply cleanup.
4. Re-run `tools/privacyctl.py verify` to prove terminal state, event ordering, and retry idempotency.
5. Reconcile the ledger/handoff to descendant evidence and distinguish unknown from confirmed delivery receipts.

## 7. Harness demands

The task requires tool selection, ordered multi-step execution, deletion and append-only state management, verification behavior, evidence grounding, and a safety boundary around privacy data.

## 8. Stressors and difficulty

- **Plausible failure mode:** The agent trusts only the explicit job list, cancels before fencing/checkpoint release, deletes a receipt or hold, retains a transient credential, conflates confirmed and unknown deliveries, touches xfer-850, or duplicates audit events.
- **Difficulty rationale:** Scope must be derived through a fanout edge; fence, drain, checkpoint, cancel and cleanup are distinct dependent transitions. Three jobs, two leases, five scoped transfers with three dispositions, seven artifacts with three retention classes, an unrelated request and append-only audit state must remain consistent and idempotent.

## 9. Oracle design

Core cases total 0.80 across `control/job_state.json`, `control/queue.json`, `control/worker_leases.json`, `control/fanout_state.json`, retention-aware cleanup, and executable idempotency. Append-only `audit/events.jsonl`, `cleanup_plan.csv`, `cancellation_ledger.csv`, and `privacy_handoff.md` are scored explicitly. A hard gate protects other evidence and rejects claims of external contact or transfer.

## 10. Leakage, isolation, and safety review

All services and identities are synthetic and offline. The agent receives no secret values. Only the declared fanout, job, queue, lease, and audit paths may change, and only manifest-classified purgeable row data or transient credentials may be deleted. Hidden reference setup exists solely to represent deletion in oracle-quality trials.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Purging before cancellation, editing JSON directly instead of preserving tool-generated audit events, skipping the retry check, or omitting retained-evidence and external-action boundaries from `privacy_handoff.md`.
- **Expected strong-harness success band:** To be calibrated from repeated post-review pilots; a single score is not a semantic label.
- **Revision rule:** Use model outcomes only to diagnose reproducible environment, specification, and scoring defects, never as task-selection features.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
