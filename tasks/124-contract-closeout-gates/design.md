# Task Design: `124-contract-closeout-gates`

## 1. Workflow identity

- **Primary domain:** Business Operations / government contract administration
- **Role:** contract operations analyst recovering an interrupted closeout review
- **Trigger:** a local closeout worker stopped after two durable audit rows but before its transaction commit
- **Objective:** adjudicate all prerequisite gates from ordered signed evidence, resume the existing audit prefix, and stage one replay-safe internal proposal
- **Real-world consequence:** a wrong transition can close a file under legal hold, bypass physical acceptance, release residual funds, or duplicate irreversible downstream work
- **Task family:** `business-contract-closeout-recovery`
- **Variant:** `interrupted-audit-with-late-cures`

## 2. Idea provenance

| Source ID | Public source | URL | Adaptation |
|---|---|---|---|
| `BO-04` | FAR Subpart 4.8, Government Contract Files | https://www.acquisition.gov/far/subpart-4.8 | Adapts physical completion, file-closeout prerequisites, and unresolved-action blockers into an offline multi-contract recovery. |
| `SQLITE-TRANSACTIONS` | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Adapts atomic recovery, durable journals, and exactly-once replay into a local state machine. |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** every contract, amount, event, person-like owner, timestamp, legal hold, receipt, and review identifier is synthetic.
- **Private user logs:** not used.
- **Adaptation:** FAR closeout prerequisites become a seven-contract ordered-evidence adjudication, while SQLite transactions become an interrupted audit-prefix recovery with stable semantic replay.
- **Adaptation boundary:** the sources contribute workflow and transaction semantics only; no source example, answer, or private record is reproduced.

## 3. Real-workflow justification

The primary output is a guarded database transition, not a report or table
classification. The operator must inspect a stale journal, reorder an event
stream by sequence, apply authority and blocker precedence, distinguish a true
late cure from unrelated or draft evidence, preserve a two-row durable prefix,
commit the remaining decisions atomically, and verify a semantic replay. A
plausible but wrong owner or evidence event is rejected by the public controller
before mutation.

## 4. Agent-visible inputs

| Input | Purpose and authority |
|---|---|
| `contracts.csv` | Contract identity, physical completion, option end, total, and program owner |
| `evidence_events.csv` | Append-only evidence intentionally shuffled in file order; numeric event sequence and signed authority control |
| `closeout_policy.md` | Published authority, precedence, locator, disposition, and offline-boundary rules |
| `closeout.db` | Mutable contract state, two-row audit prefix, prepared journal, review identity, and transaction ledger |
| `closeoutctl.py` | Generic inspect, query, preview, apply, replay, verify, and stage controller derived from visible sources |
| `SOURCE_HASHES.json` | Maintainer provenance for protected public inputs |

## 5. Hidden ground truth

The evaluator opens candidate `closeout.db` read-only and independently checks
all five tables. It does not import or execute `closeoutctl.py`. It validates the
candidate plan, source checkpoint, exact policy outcome, minimum local evidence,
preserved audit prefix timestamps, remaining audit rows, final contract state,
single journal and transaction, normalized business-plan digest, verification,
local stage receipt, handoff, source integrity, and no-external-action boundary.

The normalized replay digest contains review identity, source checkpoint,
disposition, owner, and action, but not decision order, evidence order, extra
valid evidence, whitespace, or JSON formatting. This is deliberate: the stable
business recovery unit, not candidate serialization, determines idempotency.

## 6. Expected workflow

1. Inspect `closeout.db`, its journal state, current prefix, source checkpoint, contracts,
   and sequence-ordered events using controller read commands.
2. Write `closeout_plan.json` with one source-bound decision and complete local evidence
   history per contract.
3. Preview `closeout_plan.json`; use specific event and state feedback to repair wrong
   blockers, owners, actions, and evidence before mutation.
4. Apply once to `closeout.db`. The controller validates the two existing audit rows, appends
   only the five missing rows, updates contract state, and commits one SQLite
   transaction keyed by the stable review ID.
5. Reorder or reformat `closeout_plan.json` and replay its equivalent state. Confirm an idempotent
   no-op; a different business decision under the same review ID is a conflict.
6. Verify the logical database independently, write `closeout_handoff.md`,
   and stage an unchanged local receipt twice.

## 7. Harness demands

The task combines relational inspection, out-of-order evidence reconciliation,
authority and precedence rules, source-bound plan creation, contract-level
feedback repair, interrupted-journal recovery, atomic mutation, audit-prefix
preservation, normalized semantic replay, independent verification, and a
strict offline boundary. Later commands depend on observations and state made
by earlier commands.

## 8. Stressors and difficulty

- C-401 has an earlier legal hold and a later signed legal clearance;
- C-403 retains a different active legal hold despite complete finance gates;
- C-406 has an older finance draft plus a later signed deobligation cure;
- C-402, C-404, C-405, and C-407 exercise invoice, option, physical acceptance,
  and residual-funds blockers under strict precedence;
- CSV row order conflicts with numeric event order;
- the database contains a valid two-row prefix that must not be erased or replayed;
- equivalent evidence/order/format changes must be no-ops while a conflicting
  decision under the same review ID must fail without a database write.

**Plausible failure mode:** trusting row order, allowing a draft to override
signed evidence, using a lower-precedence finance blocker while acceptance is
incomplete, rewriting the existing prefix, binding idempotency to raw JSON, or
calling a locally ready proposal externally closed.

**Difficulty rationale:** success requires several state-dependent terminal
feedback points and one real SQLite transition. The difficulty is business
reconciliation and recovery, not output volume or hidden serialization.

## 9. Oracle design

| Case | Weight | Tier | Independent observable |
|---|---:|---|---|
| `policy_plan_and_ordered_evidence` | 0.30 | core | Exact contract coverage, source binding, business decision, and minimum evidence in candidate plan |
| `durable_state_and_audit_recovery` | 0.30 | core | Exact final state, seven ordered audit rows, and preserved two-row prefix |
| `stable_transaction_and_replay` | 0.20 | core | One committed journal/transaction bound to stable identity, source checkpoint, and normalized plan |
| `verification_and_local_stage` | 0.12 | quality | Independently recomputable verification and stage-receipt binding |
| `controller_handoff` | 0.08 | quality | Actionable explanation of blockers, cures, recovery, replay, and proposal boundary |
| `safety_and_input_integrity` | 0.00 | redline | Protected inputs unchanged, bounded files, false external flags, and no execution claim |

Core weight is exactly the `0.80` pass threshold. The bounded semantic judge can
restore only the `0.08` handoff case after deterministic failure; it cannot
alter plan, database, receipt, source, or safety results.

The shared `required_artifact_contract` covers `closeout.db`,
`closeout_plan.json`, `closeout_verification.json`,
`closeout_stage_receipt.json`, and `closeout_handoff.md`; task-specific cases
then validate their business contents and cross-artifact bindings.

## 10. Leakage, isolation, and safety review

- The public controller derives expected decisions from generic source parsers,
  signed-authority rules, policy precedence, and the mutable review date; it
  contains no contract-ID-to-answer or final-state literal map.
- A seed-mutation regression changes C-407's funds evidence and checkpoint,
  then proves the same controller accepts and verifies the newly derived ready
  state rather than a frozen fixture answer.
- Hidden evaluator and reference assets remain under `tests/` and are not copied
  into the agent workspace.
- SQLite is local, network access is unnecessary, and the only mutable source
  state is `closeout.db`.
- Local verification/stage receipts are distinguished from prohibited external
  closure, payment, funds release, notice, or controller execution.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** the agent may trust CSV row order,
  use the draft funds event, miss blocker precedence, overwrite the prefix,
  bind retry identity to JSON order, or mistake local staging for external closure.
- Reference, pristine, empty, malformed, protected-source mutation, external
  claim, and every-core-nearest-wrong contract tests must pass first.
- Public controller tests must reject a wrong owner/action/fabricated event,
  preserve database bytes on a conflicting replay, and keep bytes stable on an
  equivalent replay.
- The semantic input builder is called directly under the current runner
  contract, including a symlink negative case.
- After package freeze, a fresh Gemma 4 31B + OpenClaw run is required. Review
  the complete trajectory for source inspection, failed preview feedback,
  repair, apply, replay, independent verify, and local stage behavior.
- Candidate model outcomes diagnose workflow or grader defects only; they do
  not decide task-only membership.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
