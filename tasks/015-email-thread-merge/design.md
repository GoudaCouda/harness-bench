# Task Design: `015-email-thread-merge`

## 1. Workflow identity

- **Primary domain:** Office Productivity
- **Role:** customer onboarding manager
- **Trigger:** A fragmented email chain contains completed work, preferences, commitments, tentative dates, and approval dependencies.
- **Objective:** Recover a Customer Onboarding State from Fragmented Email
- **Real-world consequence:** Conflating a preference with a commitment or a tentative date with approval creates a false customer promise.
- **Task family:** `015-email-thread-merge`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| MS-SHARED-MAILBOX | Microsoft 365 shared mailbox configuration | https://learn.microsoft.com/en-us/microsoft-365/admin/email/configure-a-shared-mailbox?view=o365-worldwide | 2026-08-26 | Grounds multi-user message visibility and reply authority in a shared operational mailbox. |
| ONET-PROJECT-MANAGEMENT | O*NET Project Management Specialists | https://www.onetonline.org/link/details/13-1082.00 | 2026-08-26 | Grounds stakeholder requirements, schedule coordination, project updates, and deliverable monitoring. |

- **Origin class:** public_workflow_adaptation
- **Synthetic-data statement:** All people, organizations, identifiers, amounts, events, and records in the workspace seed are synthetic.
- **Adaptation:** Public workflow sources shape the mailbox and project-coordination context; every message, person, date, commitment, approval, and expected state is synthetic.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The task recovers one current onboarding state and turns it into a safe customer reply and internal account handoff.

The downstream consequence is concrete: Conflating a preference with a commitment or a tentative date with approval creates a false customer promise. The task is therefore admitted for its decision and state transition, not for producing 2 files or matching a reference layout.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `emails/email_001.json` | Current synthetic evidence used by the customer onboarding manager. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `emails/email_002.json` | Current synthetic evidence used by the customer onboarding manager. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `emails/email_003.json` | Current synthetic evidence used by the customer onboarding manager. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `emails/email_004.json` | Current synthetic evidence used by the customer onboarding manager. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `emails/email_005.json` | Current synthetic evidence used by the customer onboarding manager. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |

## 5. Hidden ground truth

The hidden evaluator owns the following 5 business outcomes; it does not require reference prose or byte layout:

Concrete agent-visible inputs are `emails/email_001.json`, `emails/email_002.json`, `emails/email_003.json`, `emails/email_004.json`, `emails/email_005.json`.

- `onboarding_dependency_state`: Three onboarding milestones form the correct dependency state. Security questionnaire, procurement approval, and pilot kickoff have the correct owners, lifecycle states, targets, blockers, and account-level status after duplicates and unrelated mail are removed.
- `commitment_interpretation`: Requests, commitments, and tentative dates are distinguished. The state preserves Friday as the accepted questionnaire commitment, treats today's request as a preference, and does not promote team availability or pending procurement into a confirmed kickoff.
- `customer_resolution_draft`: Customer draft advances the unresolved onboarding path. The reply addresses Morgan, acknowledges urgency, communicates the supported deadline and conditional kickoff, and asks for the procurement confirmation needed to unblock the plan.
- `evidence_and_dedup_trace`: State is traceable to unique relevant message evidence. Milestone evidence uses the substantive Northwind message IDs once, excludes the forwarded duplicate as a separate event, and records the billing notification as ignored.
- `coherent_account_handoff`: Structured state and customer communication agree. The reply and milestone package use the same account, deadline, blockers, and tentative status in a concise professional handoff.

Protected source state is reconciled against the workspace seed, and the required final artifacts are `customer_reply.md`, `onboarding_state.json`. Exact expected facts remain under `tests/ground_truth/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inventory `emails/email_001.json`, `emails/email_002.json`, `emails/email_003.json`, `emails/email_004.json`, `emails/email_005.json` and establish the current record, version, and authority boundaries.
2. Reconcile the evidence needed for Three onboarding milestones form the correct dependency state, Requests, commitments, and tentative dates are distinguished, Customer draft advances the unresolved onboarding path; preserve explicit pending, unknown, superseded, or blocked state.
3. Create or update `customer_reply.md`, `onboarding_state.json` as the smallest downstream-usable package.
4. Cross-check the candidate artifacts against each other so totals, identifiers, decisions, and narrative do not diverge.
5. Re-read or execute the applicable local validation, confirm protected inputs are unchanged, and stop without claiming unauthorized external action.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | Scored decisions must be traceable to agent-visible evidence rather than reference wording. |
| `multi_step_execution` | Later decisions and artifacts depend on earlier reconciliation and verification. |
| `safety_boundary` | The workflow contains an authority, privacy, evidence, or irreversible-action boundary. |

## 8. Stressors and difficulty

- **Stressors:** dirty_input.
- **Plausible failure mode:** Conflating a preference with a commitment or a tentative date with approval creates a false customer promise.
- **Provisional difficulty:** medium.
- **Difficulty rationale:** The candidate must reconcile 5 visible source files into 5 independently owned business outcomes and 2 downstream artifacts; difficulty is assigned from the state/decision path, not the number of requested fields.
- **Why the difficulty is workflow-derived rather than noise:** The task recovers one current onboarding state and turns it into a safe customer reply and internal account handoff.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---:|---|
| `onboarding_dependency_state` — Three onboarding milestones form the correct dependency state | 0.35 | Security questionnaire, procurement approval, and pilot kickoff have the correct owners, lifecycle states, targets, blockers, and account-level status after duplicates and unrelated mail are removed. |
| `commitment_interpretation` — Requests, commitments, and tentative dates are distinguished | 0.25 | The state preserves Friday as the accepted questionnaire commitment, treats today's request as a preference, and does not promote team availability or pending procurement into a confirmed kickoff. |
| `customer_resolution_draft` — Customer draft advances the unresolved onboarding path | 0.20 | The reply addresses Morgan, acknowledges urgency, communicates the supported deadline and conditional kickoff, and asks for the procurement confirmation needed to unblock the plan. |
| `evidence_and_dedup_trace` — State is traceable to unique relevant message evidence | 0.10 | Milestone evidence uses the substantive Northwind message IDs once, excludes the forwarded duplicate as a separate event, and records the billing notification as ignored. |
| `coherent_account_handoff` — Structured state and customer communication agree | 0.10 | The reply and milestone package use the same account, deadline, blockers, and tentative status in a concise professional handoff. |
| `source_and_execution_boundary` — Email evidence and output integrity are preserved | gate | Source messages remain unchanged and deliverables are regular files rather than links. A false completion claim loses customer-draft credit. |

- **Critical gates:** `source_and_execution_boundary`.
- **Partial-credit rationale:** Whole business outcomes carry core weight 0.80; independent handoff or integrity outcomes carry 0.20. One field is never treated as its own process score.
- **Order/format tolerance:** Keyed rows and objects are unordered unless ordering itself changes the business decision; equivalent prose is accepted through deterministic semantics or the bounded agent-model judge declared by the task.
- **Empty workspace:** must score `0.0`.
- **Untouched workspace seed:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

The oracle explicitly covers required artifacts `customer_reply.md`, `onboarding_state.json`; no required deliverable is credited only by a generic completeness check.

## 10. Leakage, isolation, and safety review

- **Hidden files excluded from agent workspace:** `tests/`, `design.md`, and all reference/ground-truth materials.
- **Network:** disabled; only task-declared local services are permitted.
- **Workspace mutation contract:** created=['customer_reply.md', 'onboarding_state.json'], modified=[], deleted=[].
- **Trusted between-round mutations:** none unless an environment hook is explicitly declared and content-addressed.
- **Potential destructive action and guard:** Conflating a preference with a commitment or a tentative date with approval creates a false customer promise. The grader separately verifies source integrity and authority boundaries.
- **Sensitive-data review:** all records are synthetic; privacy or protected data is included only when its handling is itself under test.
- **Host-path or author-environment dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** incomplete `onboarding_dependency_state`; inconsistent `commitment_interpretation`; a polished handoff without the required state change; or an unsupported execution/approval claim.
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
