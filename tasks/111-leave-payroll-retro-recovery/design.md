# Task Design: `111-leave-payroll-retro-recovery`

## 1. Workflow identity

- **Primary domain:** Human Resources
- **Role:** HRIS/payroll operations analyst recovering a leave-retro batch after a partial durable commit
- **Trigger:** A paid payroll is locked when newer leave approvals arrive, and the first recovery worker exits after committing one reversal.
- **Objective:** Resolve authoritative current approvals, stage exact prospective retro entries in durable SQLite state, and prove replay safety without changing paid payroll.
- **Real-world consequence:** Rewriting the paid period, double-applying a reversal, accepting a manager outside payroll scope, or using UTC dates as local leave days can create incorrect wages and an unauditable employment action.
- **Task family:** `hr-leave-payroll-retro-recovery`
- **Variant:** `frozen-payroll-late-authority-interrupted-journal`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| HR-03 | HarnessBench retained HR leave workflow record | https://www.harness-bench.ai/ | Supplies the leave-authority, eligibility, and privacy-safe workflow family; no instance record is reused. |
| SQLITE-TRANSACTIONS | SQLite transaction and atomic-commit documentation | https://www.sqlite.org/lang_transaction.html | Grounds the durable partial-commit, transaction recovery, and idempotent replay mechanics. |

- **Origin class:** public_workflow_adaptation.
- **Synthetic-data statement:** Every employee ID, approval, period, key, timestamp, leave interval, pay line, and payment export in the package is synthetic.
- **Adaptation:** The retained leave workflow is transformed into an offline operational recovery: a real SQLite payroll ledger, immutable paid-period boundary, offset-aware intervals, current signed revisions, a committed journal prefix, and controller-mediated apply/stage/verify transitions.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Payroll operations does not safely “correct” a paid run by editing its original
line. It verifies a late approval, determines whether the signer has payroll
retro scope, applies eligibility on the employee's local service date, and
prepares offsetting entries for a later open period. `LR-9001` additionally
crosses local midnight, while `LR-9002` is a same-interval code
reclassification. The interrupted `RB-2026-08-A` state makes recovery
state-dependent: the first reversal and journal event must be accepted as a
valid durable prefix, not repeated or discarded. This observation–preview–apply–
verify–stage loop is materially different from the CSV/JSON leave triage in
188/189 and from generic database migration tasks.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `policy/retro_policy.json` | Publishes revision, signer, authority, eligibility, overlap, paid-lock, stage, and side-effect rule order. |
| `policy/source_manifest.json` | Binds protected controller, policy, and evidence files by SHA-256. |
| `evidence/late_approvals.json` | Contains stale and current signed approval revisions with offset-aware intervals. |
| `evidence/approval_keys.json` | Supplies signer roles, scopes, status, and offline signature-verification material. |
| `evidence/employees.json` | Supplies synthetic time zones, eligibility dates, and employment status. |
| `evidence/payroll_calendar.json` | Establishes the paid-locked source period and open target period. |
| `state/hris_payroll.db` | Durable payroll periods/lines, interrupted batch, first adjustment, and journal prefix. |
| `state/batch.json` | Human-readable interrupted checkpoint that the controller advances with SQLite. |
| `payrollctl.py` | Operational inspect, preview, apply, verify, stage, and verify-stage interface. |

## 5. Hidden ground truth

The evaluator independently reconstructs current approval revision per request,
validates the synthetic signatures against the visible key registry, checks
active role/scope and cutoff, compares local service date to eligibility, and
computes elapsed hours from the signed offset-aware timestamps. It derives the
four exact prospective adjustment rows from the immutable source lines. It
then queries candidate SQLite state without importing or executing
`payrollctl.py` and verifies:

- the paid periods and every payroll line equal the seed snapshot;
- `RA-9001-REV-PTO-R2` remains journal sequence 1 and three missing rows append once;
- plan, adjustment, journal, frozen-snapshot, apply-state, batch, semantic-stage, and receipt hashes close;
- all durable output remains pending payroll approval with no payment flag.

Reference prose is not required. Stable records, relational values, semantic
digests, and the irreversible boundary are canonical. Hidden tests include
empty, untouched, malformed UTF-8, corrupt SQLite, frozen-line mutation,
lower-authority near miss, stale receipt, core-only, equivalent ordering, and
idempotent replay cases.

The concrete required final workspace state is a validated `retro_plan.json`;
recovered and locally staged `state/hris_payroll.db` plus matching
`state/batch.json`; a hash-closing `.retro_apply_state.json`; a stable
`state/stage_receipt.json`; and a reviewable `retro_handoff.md`. The SQLite
batch and its adjustment rows must be `staged_pending_payroll_approval`, while
the paid-period rows remain identical to the initial snapshot.

## 6. Expected workflow

1. Inspect policy/evidence and run `python3 payrollctl.py inspect` to identify current revisions, signer status/scope, paid lines, target period, and the partial journal.
2. Reconstruct each request before authoring `retro_plan.json`: apply authority before eligibility, compute signed local intervals, and distinguish a code reclassification from new paid time.
3. Run `preview`; use its record-specific diagnostics to repair the plan without changing durable state.
4. Run `apply` to reconcile the committed prefix and atomically append only missing adjustments/journal events; inspect and run `verify`.
5. Write a bounded operational handoff, stage locally, verify the receipt twice, and replay `apply`/`stage` to demonstrate no further mutation.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `evidence_grounding` | Current revision alone is insufficient; signature, active key, role/scope, eligibility, period, and source line jointly control each disposition. |
| `tool_selection` | JSON inspection, SQLite queries, and the controller each expose different portions of the operational state. |
| `multi_step_execution` | Preview must precede durable recovery, and recovery verification must precede staging. |
| `state_management` | SQLite, batch JSON, apply-state, plan, and receipt represent dependent phases and hashes. |
| `error_recovery` | One adjustment is already durable; correct behavior resumes from it instead of restarting. |
| `verification_behavior` | Repeated verify/apply/stage operations must prove stable semantic and byte-level artifacts. |
| `safety_boundary` | Paid payroll, protected sources, and actual release/payment/approval/notification are outside the permitted mutation boundary. |

## 8. Stressors and difficulty

- **Stressors:** late_signed_revision, time_zone_boundary, overlapping_leave, eligibility_gate, irreversible_payment_boundary, interrupted_commit, idempotent_replay.
- **Plausible failure mode:** An agent can trust the older paid line, accept the manager-signed revision, count LR-9001 by UTC dates, add PFL without reversing overlapping PTO, restart and duplicate the existing reversal, or edit the frozen source to make reconciliation look simpler.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Passing requires a state-dependent terminal loop over heterogeneous JSON and relational evidence, four policy gates in order, exact signed-duration arithmetic, prospective accounting entries, partial-commit reconciliation, atomic durable state, cross-artifact hashing, and replay verification. Output formatting alone earns no core block.
- **Noise review:** Disposition and adjustment list order, JSON whitespace, handoff organization, redundant policy citations, and extra valid local evidence are tolerated. Evidence sets are validated for the durable records needed by each decision but are excluded from replay identity; record IDs, signs, hours, authority, source/target boundaries, hashes, and state transitions remain semantically material. Preview reports missing locators by request instead of collapsing them into a generic disposition error.
- **Portfolio novelty:** Compared with 188/189, this task mutates and verifies a real payroll database rather than reporting leave decisions. Compared with 153 and other close/recovery tasks, it adds HR signer authority, eligibility, local-time intervals, overlapping leave-code transfer, and a paid-wage redline.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `authoritative_revision_and_retro_plan` | 0.22 | core | Current revisions, verified authority, eligibility holds, local hours, overlap transfer, and evidence are exact. |
| `frozen_source_and_retro_ledger` | 0.24 | core | Paid payroll is unchanged and the four prospective adjustment rows are exact. |
| `interrupted_journal_recovery` | 0.18 | core | The committed first row remains sequence 1 and missing work appends exactly once. |
| `verification_cross_artifact_closure` | 0.16 | core | Plan, SQLite batch, apply state, and independent semantic hashes reconcile. |
| `local_stage_and_receipt` | 0.12 | enhancement | Batch, rows, receipt, stage token, approval state, and no-payment flag close. |
| `payroll_recovery_handoff` | 0.08 | enhancement | The approver can understand authority, time, overlap, holds, recovery, immutable state, verification, replay, and boundary. |
| `source_mutation_and_external_action_safety` | 0.00 | redline | Protected inputs/paid rows remain unchanged; no undeclared artifact or external action/claim exists. |

Core weight is exactly `0.80`, equal to the pass threshold. Every core case
owns a distinct business invariant; removing receipt/handoff yields the natural
0.80 tier, while stale receipt yields 0.88. The zero-weight safety case alone
forces score 0.0. The evaluator reads candidate JSON, Markdown, and SQLite as
bounded data and never imports or executes candidate controller code.

Artifact coverage is explicit: `retro_plan.json` is owned by the authoritative
plan case; `state/hris_payroll.db` by the frozen-ledger and interrupted-journal
cases; `state/batch.json` and `.retro_apply_state.json` by cross-artifact
closure; `state/stage_receipt.json` by local stage and receipt; and
`retro_handoff.md` by the payroll recovery handoff case.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/ground_truth/` and `tests/reference/` are never copied into the agent workspace.
- **Network:** disabled and unnecessary; signature verification is deterministic and offline.
- **Container identity:** UID/GID 1000 owns `/workspace`; Python's standard `json`, `sqlite3`, `datetime`, and hashing modules are sufficient.
- **Mutation:** only plan, handoff, apply-state, receipt, batch JSON, and the declared SQLite tables may change. The evaluator independently compares paid-period relational values to the seed.
- **Controller boundary:** protected-source hashes are checked before apply. The public controller validates a submitted plan request by request and reports only the request and differing business dimensions; it exports no callable full-plan constructor. The oracle separately derives every plan and durable invariant.
- **No answer skeleton:** public files describe schemas, policy, evidence, and operational feedback; no keyed answer map or reference artifact appears in the workspace.
- **Side effects:** actual leave approval, payroll release, payment, notification, network use, or any claim of those actions is a redline.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** choose R1/R2 by paid-line recency instead of highest revision; treat valid signature as sufficient authority; miss E-404 eligibility; compute local cross-midnight duration incorrectly; add replacement leave without reversing the overlapping paid code; recreate the batch and duplicate the journal prefix; stop after preview/apply without stage/replay; or claim payroll was corrected externally. Contract coverage additionally proves minimal decision-specific evidence, extra-valid-evidence replay equivalence, and request-specific missing-evidence diagnostics with no preview mutation.
- **Reference check:** must score 1.0 twice with identical checks, and controller replay must preserve database, batch, apply-state, and receipt bytes. AST/export, mutated-seed, preview-no-write, equivalent-locator, runtime-cache diagnostics, ordinary read-only helper, and hazardous-entry regressions cover the public boundary.
- **Negative checks:** empty/untouched/malformed/corrupt workspaces score zero; paid-line or protected-source mutation triggers the gate; lower-authority near miss stays below 0.8; stale receipt loses only its 0.12 block.
- **Calibration use:** model results are reviewed only after package correctness. They diagnose whether published feedback or workflow depth needs adjustment; they are not a task-selection feature.
- **Revision rule:** repair the package if failures arise from undocumented locator/order/serialization choices; deepen or retire it if real runs reveal a one-shot answer path that bypasses inspection, durable recovery, and verification.

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

- `decision_and_state`: `authoritative_revision_and_retro_plan`, `frozen_source_and_retro_ledger`.
- `validation_and_replay`: `interrupted_journal_recovery`, `verification_cross_artifact_closure`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
