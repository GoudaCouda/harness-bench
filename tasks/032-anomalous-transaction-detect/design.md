# Task Design: `032-anomalous-transaction-detect`

## 1. Workflow identity

- **Primary domain:** finance / accounts-payable fraud controls
- **Role:** AP release-gate analyst
- **Trigger:** a review-only supplier-payment gate stopped during apply after
  preparing two rows and committing none.
- **Objective:** reconcile supplier-bank evidence, recover the interrupted
  local state, and stage one replay-safe controller proposal.
- **Real consequence:** an invalid bank-change chain can divert a supplier
  payment; an unsupported hold can delay a legitimate supplier.
- **Task family:** `finance-supplier-bank-release-recovery`
- **Variant:** `interrupted-review-gate`

This is not an invoice/receipt matching exercise. The hard dependency graph is
payment -> supplier master -> recent bank change -> callback channel and time ->
two post-callback approvals, plus first-payment and high-value release controls.

## 2. Idea provenance

| Source ID | Source | URL | Use |
|---|---|---|---|
| `FBI-BEC-PAYMENT-DIVERSION` | FBI Internet Crime Complaint Center, Business Email Compromise | https://www.ic3.gov/CrimeInfo/BEC | Motivates secondary-channel verification of account-information changes and distrust of urgent email instructions. |
| `NACHA-ACCOUNT-VALIDATION` | Nacha Account Validation Resource Center | https://www.nacha.org/content/account-validation-resource-center | Motivates validating first-use or changed payment-account information before live payment use. |

- **Origin:** public-workflow adaptation; records, identifiers, timestamps,
  tokens, and amounts are synthetic.
- **Private user logs:** not used.
- **Adaptation:** the sources motivate the control family. The local
  precedence rules, interrupted journal, exact artifacts, and cases are original
  benchmark construction and do not claim to reproduce an organization's SOP.
- **Suggested shared aliases (not edited by this task-only change):**
  `IC3-BEC-CONTROLS` -> `FBI-BEC-PAYMENT-DIVERSION`; `NACHA-ACCOUNT-VALIDATION-RESOURCE`
  -> `NACHA-ACCOUNT-VALIDATION`.

## 3. Real-workflow justification

The agent must first inventory a source-bound state machine, then query nine
linked record graphs. Later choices depend on timestamp and role relationships
observed earlier: a nominally approved change can still fail because a callback
used the request channel or because approvals predate the callback. The agent
must construct a candidate, use object/field feedback, recover a zero-commit
interruption atomically, verify it, stage a human-review receipt, and prove that
an order-only rewrite is a byte-stable semantic replay.

The controller never contacts a bank or supplier and never produces a payment
file. Its state transition is nevertheless real and independently observable.

## 4. Agent-visible inputs

| File | Purpose | Mutability |
|---|---|---|
| `payment_queue.csv` | payment requests and untrusted urgency notes | protected |
| `suppliers.csv` | status, current bank token, payment history, beneficiary verification | protected |
| `bank_change_requests.csv` | bank-token change requests and lifecycle state | protected |
| `callback_events.csv` | callback source, result, beneficiary match and time | protected |
| `approval_events.csv` | role-scoped bank-change and payment approvals | protected |
| `batch_context.json` | policy, cutoff, thresholds and review-only mode | protected |
| `release_gate_policy.md` | published precedence, enums and lineage contract | protected |
| `SOURCE_HASHES.json` | visible immutable-source manifest | protected |
| `treasuryctl.py` | candidate-first local controller | protected |
| `release_gate_state.json` | interrupted mutable review state | must be modified by controller |

The initial state exposes only phase, revision, checkpoint and interrupted
counts. It contains no decisions or answer-bearing checkpoint payload.

## 5. Hidden ground truth

The hidden evaluator owns the following business outcomes and reconstructs
them without importing or invoking `treasuryctl.py`:

- bank-token mismatch and recent-change-chain decisions;
- first-payment beneficiary and high-value approval decisions;
- inactive-supplier precedence and clean release readiness;
- exact atomic recovery state and semantic plan digest;
- complete scoped visible evidence lineage;
- preview, verification, state, handoff and receipt closure;
- protected-source and external-authority safety.

The hidden mapping is keyed by payment ID and is never copied into the agent
workspace. Reference artifacts exist only under `tests/reference/`.

The required final workspace state is `release_gate_state.json` at
`staged_for_controller@r5`, containing all nine canonical review records and a
completed zero-commit recovery history, with `release_gate_plan.json`,
`.release_gate_preview.json`, `release_gate_verification.json`,
`controller_handoff.md`, and `release_gate_receipt.json` bound to the same
source checkpoint and semantic plan digest.

## 6. Expected workflow

1. Run help, status and inspect; confirm `interrupted_apply`, two prepared rows,
   zero committed rows and a current source checkpoint.
2. Query every payment's local graph and apply published precedence.
3. Create the exact-schema `release_gate_plan.json`.
4. Preview and use per-payment/per-field constraints to repair the candidate.
5. Apply once to roll back the incomplete preparation and atomically commit the
   complete semantic plan; apply again to prove idempotence.
6. Verify the applied state and write a controller handoff.
7. Stage the proposal and create a source/digest-bound local receipt.
8. Replay a semantically equivalent ordering and prove the state and receipt
   remain byte-for-byte unchanged.

State path:

`interrupted_apply@r3 -> review_applied@r4 -> staged_for_controller@r5`

Preview is candidate-first and does not modify `release_gate_state.json`.
Apply requires the matching passing preview and current source checkpoint.
Conflicting or stale candidates fail before state mutation.

### Public-controller non-leakage

`treasuryctl.py` accepts a candidate before evaluating business constraints.
It has no `target_plan`, `expected_plan`, `reference_plan`, `derive_plan`, or
command that exports decisions. `query` returns raw linked visible records and
an explicit null decision. Failed preview output identifies:

- submitted `payment_id` (or batch scope),
- candidate field,
- published rule family,
- violated constraint,
- received/related counts when useful.

It does not print the correct disposition, reason, locator, or replacement
value. The protected evaluator does not import or execute the controller.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | Each action is tied to its payment/supplier and applicable change, callback and approval graph. |
| `multi_step_execution` | Query results drive the candidate; preview drives revision; apply drives verification and stage. |
| `state_management` | A zero-commit interrupted journal must be recovered without replacing the state. |
| `error_recovery` | Stale, incomplete, or policy-inconsistent candidates receive bounded feedback and must be corrected. |
| `verification_behavior` | The agent must verify closure, stage, and prove byte-stable semantic replay. |
| `safety_boundary` | Review readiness cannot be represented as payment, approval, contact, or supplier modification. |

The scoring ownership is:

| Outcome | Weight | Core | Independent observable |
|---|---:|:---:|---|
| Bank-change and token controls | 0.30 | yes | Four payments distinguish mismatch, valid chain, same-channel callback, and early approvals. |
| Beneficiary and high-value controls | 0.25 | yes | First-use verification and two-role payment approval are correct. |
| Supplier status and clean release | 0.15 | yes | Inactive status overrides urgency while one clean established payment remains ready. |
| Interrupted state recovered | 0.10 | yes | Complete canonical records, recovery history, phase, revision and digest are consistent. |
| Evidence lineage | 0.08 | no | Every plan row cites its exact related visible graph and no unrelated record. |
| Verification and semantic replay | 0.07 | no | Preview, verification, state and receipt bind one semantic digest/checkpoint. |
| Actionable handoff | 0.05 | no | Counts, exceptions, recovery, safe next steps and non-execution are present. |
| Source and authority safety | gate | — | Protected hashes, path types and no-execution boundary remain intact. |

Deterministic core weight is exactly **0.80**. Semantic fallback weight is
**0.00**: handoff credit is a bounded deterministic concept/identifier check,
not an LLM judgement. Thus the semantic fallback cap of 0.08 is respected.

The evaluator owns business outcomes rather than controller exit text. It
canonicalizes unordered decisions and evidence locators, checks protected
hashes directly, and independently rebuilds digest, state, verification, and
receipt closure.

## 8. Stressors and difficulty

- **Stressors:** interrupted apply, stale source checkpoint, untrusted urgency
  notes, bank-change chronology, callback provenance, role separation,
  high-value threshold, and semantic replay.
- **Plausible failure mode:** treating a same-channel callback or approvals that
  predate callback evidence as a valid bank-change chain can stage a diverted
  supplier payment; treating review readiness as execution breaches authority.
- **Difficulty:** hard.
- **Difficulty rationale:** the candidate must reconcile nine linked record
  graphs, preserve precedence across six control branches, recover a real local
  state transition, close multiple digest-bound artifacts, and distinguish
  semantic equivalence from a conflicting replay. Complexity comes from
  state-dependent decisions, not data volume or hidden wording.

The mutation boundary is:

- Allowed creations: plan, preview record, verification, handoff and stage
  receipt.
- Allowed modification: only `release_gate_state.json`.
- All source evidence, visible hash manifest and controller are protected.
- Any protected mutation, source/controller link, required-artifact link,
  executable helper, payment-like execution artifact, or positive external
  action claim fails closed.
- A bounded, regular, non-executable top-level `.py`/`.sql` analysis helper and
  its ordinary `__pycache__` are not treated as an external-action safety
  violation. They can remain a mutation-contract diagnostic without erasing
  otherwise valid business outcomes.
- Bank values are synthetic opaque tokens; there are no credentials or network
  dependencies.

## 9. Oracle design

The oracle explicitly covers every required artifact:
`release_gate_state.json`, `release_gate_plan.json`,
`.release_gate_preview.json`, `release_gate_verification.json`,
`controller_handoff.md`, and `release_gate_receipt.json`.

The deterministic outcome weights and evidence are defined in Section 7. Core
weight is 0.80, the pass threshold is 0.80, and the safety outcome is a gate.
Order is ignored for decisions and locators while semantic content, source
checkpoint and closure hashes remain binding. There is no LLM fallback.

The adversarial and runtime contracts cover:

The package-local contract suite covers:

- reference determinism and oracle `0 / 0 / 0 / 1`;
- candidate-first object/field feedback without correct-value disclosure;
- a neighboring but wrong bank-change decision losing core weight;
- full inspect/preview/apply/idempotent-apply/verify/stage/replay execution;
- action and locator reorder equivalence with byte-stable replay;
- stale checkpoint and post-preview source conflict with no state mutation;
- conflicting apply with no state mutation;
- source seed, visible hash manifest, controller and symlink tampering;
- bounded regular analysis-helper/cache tolerance;
- receipt and verification tamper losing only closure weight;
- absence of public complete-answer exports.

Expected formal oracle points are: pristine `0.0`, empty `0.0`, malformed
`0.0`, and reference `1.0`.

## 10. Leakage, isolation, and safety review

- `tests/`, `design.md`, and all reference/ground-truth material are excluded
  from the agent workspace.
- `treasuryctl.py` is candidate-first and has no public answer constructor or
  command that returns correct decisions.
- Network and external services are unnecessary; the Docker image contains
  only Python and the local workspace.
- Protected input hashes are checked independently by the evaluator. Source,
  controller, manifest, required-artifact symlink, or execution-artifact
  tampering fails closed.
- The only authorized mutation is the review state and the five declared
  generated artifacts; no payment, callback, approval, contact, or supplier
  change may be claimed as executed.
- Synthetic opaque bank tokens avoid sensitive account data.

### Portfolio novelty

| Neighbor | Primary behavior | Why task032 remains distinct |
|---|---|---|
| task121 three-way invoice match | PO/receipt/invoice quantity and price reconciliation | 032 has no PO or receipt matching; it reasons over bank-change identity, callback provenance and approval ordering. |
| task122 purchase-card close | issuer/ERP/receipt/split/refund reconciliation | 032 is a supplier-master fraud gate with change-chain chronology and an interrupted apply journal. |
| task123 entity renewal | vendor entity renewal and fallback verification | 032 consumes the supplier master to gate queued payments; it does not activate or renew vendor master records. |
| task153 close rollover | ledger residual and duplicate-event recovery | 032 recovers a security-control review state and validates identity/authority chains rather than ledger balances. |

The capability signature is therefore finance + fraud/security controls +
temporal graph reconciliation + local state-machine recovery + idempotent
semantic replay.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** skipping per-payment queries;
  trusting urgency notes; accepting a same-channel callback; missing approval
  ordering; treating one high-value approval as dual approval; hand-editing
  state; failing to bind preview/apply to the checkpoint; or omitting semantic
  replay after stage.
- **Strong-harness evidence:** a complete trace should inventory the package,
  query all nine graphs, revise from bounded preview feedback if necessary,
  recover and idempotently reapply, verify, stage, and replay without source
  mutation or execution claims.
- **Ambiguity signal:** multiple competent traces inspect the same linked graph
  yet converge on the same rejected interpretation of a published chronology
  rule.
- **Environment/oracle failure signal:** reference failure, nondeterminism,
  source hash drift, controller mutation on a failed preview/apply, or rejection
  of an order-only equivalent replay.
- **Revision rule:** repair specification/controller/oracle defects for all
  agents; do not weaken a correct bank-control rule to raise one model score.
- **Fresh pilot status:** required after this task-only package change.

Full-package task-only judgement:

```yaml
task_key: harnessbench::032-anomalous-transaction-detect
evidence_mode: full_package
capability_signature:
  domains: [finance, accounts_payable, payment_fraud_controls]
  tools: [python_cli, csv, json, hashing, local_state_machine]
  behaviors: [inspect, query, reconcile, preview, repair, atomic_apply, verify, stage, semantic_replay]
  fault_or_initial_state: interrupted review apply with prepared rows and zero commits
  expected_final_state: source-bound staged controller proposal with recovered journal and stable replay
judgement:
  terminal_transfer: strong
  terminal_agency: strong
  diagnosis_recovery: strong
  moderate_complexity: strong
  verifiability: strong
  spec_feasibility: likely
  novelty: strong
decision: priority
confidence: high
reasons:
  - Later actions depend on observed callback and approval chronology.
  - Candidate-first feedback supports diagnosis without exporting the answer.
  - Independent closure and safety checks make the real local transition verifiable.
risks:
  - Exact evidence scope requires careful instruction/controller agreement.
  - Fresh model rollout is still required for empirical calibration.
missing_evidence:
  - fresh Gemma plus OpenClaw trajectory and post-pilot human review
```

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

- `decision_and_state`: `bank_change_and_token_controls`.
- `validation_and_replay`: `beneficiary_and_high_value_controls`, `supplier_status_and_clean_release`, `interrupted_state_recovered`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
