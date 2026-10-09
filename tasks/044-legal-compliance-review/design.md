# Task Design: `044-legal-compliance-review`

## 1. Workflow identity

- **Primary domain:** Compliance
- **Role:** marketing compliance reviewer
- **Trigger:** A campaign contains both legitimate product information and unsupported regulated claims before internal clearance.
- **Objective:** Revise a Campaign for Internal Compliance Clearance
- **Real-world consequence:** Over-removal destroys the message; an unsupported approval or retained claim creates publication risk.
- **Task family:** `044-legal-compliance-review`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-044 | HarnessBench retained-workflow retrospective | https://www.harness-bench.ai/ | 2026-08-09 | Project-level traceability for the retained idea; all current records and rules were reconstructed. |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All people, organizations, identifiers, amounts, events, and records in the workspace seed are synthetic.
- **Adaptation:** `044-legal-compliance-review` was rebuilt around the current trigger, state, and business outcomes; the retained idea supplied only the workflow family, not answer text or hidden rules.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The agent revises the actual campaign, preserves supportable content, and creates an evidence-grounded internal launch review without granting publication authority.

The downstream consequence is concrete: Over-removal destroys the message; an unsupported approval or retained claim creates publication risk. The task is therefore admitted for its decision and state transition, not for producing 2 files or matching a reference layout.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `evidence_manifest.json` | Current synthetic evidence used by the marketing compliance reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `internal_escalation_note.md` | Current synthetic evidence used by the marketing compliance reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `marketing_copy.md` | Current synthetic evidence used by the marketing compliance reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `policy.md` | Current synthetic evidence used by the marketing compliance reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `regulated_terms.csv` | Current synthetic evidence used by the marketing compliance reviewer. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |

## 5. Hidden ground truth

The hidden evaluator owns the following 5 business outcomes; it does not require reference prose or byte layout:

Concrete agent-visible inputs are `evidence_manifest.json`, `internal_escalation_note.md`, `marketing_copy.md`, `policy.md`, `regulated_terms.csv`.

- `compliant_campaign_revision`: Unsupported claims are removed or bounded. Absolute medical regulatory endorsement comparative and perpetual-pricing risks are remediated in the external copy.
- `legitimate_message_preservation`: Product purpose technical identifiers and bounded offer survive revision. The edit remains useful marketing copy and does not over-remove benign content.
- `evidence_grounded_launch_review`: The internal review explains policy and evidence boundaries. CLAIM-1 through CLAIM-7 manifest gaps and INTERNAL-1 conflict are translated into a supported recommendation.
- `publication_decision_trace`: Publication status and remaining ownership are clear. The owner receives a conditional recommendation without false approval or publication claims.
- `audience_ready_copy`: Revised copy is coherent audience-ready prose. The campaign is not reduced to a token list disclaimer pile or audit checklist.

Protected source state is reconciled against the workspace seed, and the required final artifacts are `marketing_copy.md`, `launch_review.md`. Exact expected facts remain under `tests/ground_truth/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inventory `evidence_manifest.json`, `internal_escalation_note.md`, `marketing_copy.md`, `policy.md`, `regulated_terms.csv` and establish the current record, version, and authority boundaries.
2. Reconcile the evidence needed for Unsupported claims are removed or bounded, Product purpose technical identifiers and bounded offer survive revision, The internal review explains policy and evidence boundaries; preserve explicit pending, unknown, superseded, or blocked state.
3. Create or update `marketing_copy.md`, `launch_review.md` as the smallest downstream-usable package.
4. Cross-check the candidate artifacts against each other so totals, identifiers, decisions, and narrative do not diverge.
5. Re-read or execute the applicable local validation, confirm protected inputs are unchanged, and stop without claiming unauthorized external action.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | Scored decisions must be traceable to agent-visible evidence rather than reference wording. |
| `multi_step_execution` | Later decisions and artifacts depend on earlier reconciliation and verification. |
| `safety_boundary` | The workflow contains an authority, privacy, evidence, or irreversible-action boundary. |

## 8. Stressors and difficulty

- **Stressors:** high_stakes_rules.
- **Plausible failure mode:** Over-removal destroys the message; an unsupported approval or retained claim creates publication risk.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** The candidate must reconcile 5 visible source files into 5 independently owned business outcomes and 2 downstream artifacts; difficulty is assigned from the state/decision path, not the number of requested fields.
- **Why the difficulty is workflow-derived rather than noise:** The agent revises the actual campaign, preserves supportable content, and creates an evidence-grounded internal launch review without granting publication authority.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---:|---|
| `compliant_campaign_revision` — Unsupported claims are removed or bounded | 0.35 | Absolute medical regulatory endorsement comparative and perpetual-pricing risks are remediated in the external copy. |
| `legitimate_message_preservation` — Product purpose technical identifiers and bounded offer survive revision | 0.20 | The edit remains useful marketing copy and does not over-remove benign content. |
| `evidence_grounded_launch_review` — The internal review explains policy and evidence boundaries | 0.25 | CLAIM-1 through CLAIM-7 manifest gaps and INTERNAL-1 conflict are translated into a supported recommendation. |
| `publication_decision_trace` — Publication status and remaining ownership are clear | 0.10 | The owner receives a conditional recommendation without false approval or publication claims. |
| `audience_ready_copy` — Revised copy is coherent audience-ready prose | 0.10 | The campaign is not reduced to a token list disclaimer pile or audit checklist. |
| `source_and_authority_boundary` — Source evidence and approval authority are preserved | gate | Protected sources remain unchanged and the outputs neither give legal advice nor claim external execution. |

- **Critical gates:** `source_and_authority_boundary`.
- **Partial-credit rationale:** Whole business outcomes carry core weight 0.80; independent handoff or integrity outcomes carry 0.20. One field is never treated as its own process score.
- **Order/format tolerance:** Keyed rows and objects are unordered unless ordering itself changes the business decision; equivalent prose is accepted through deterministic semantics or the bounded agent-model judge declared by the task.
- **Empty workspace:** must score `0.0`.
- **Untouched workspace seed:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

The oracle explicitly covers required artifacts `marketing_copy.md`, `launch_review.md`; no required deliverable is credited only by a generic completeness check.

## 10. Leakage, isolation, and safety review

- **Hidden files excluded from agent workspace:** `tests/`, `design.md`, and all reference/ground-truth materials.
- **Network:** disabled; only task-declared local services are permitted.
- **Workspace mutation contract:** created=['launch_review.md'], modified=['marketing_copy.md'], deleted=[].
- **Trusted between-round mutations:** none unless an environment hook is explicitly declared and content-addressed.
- **Potential destructive action and guard:** Over-removal destroys the message; an unsupported approval or retained claim creates publication risk. The grader separately verifies source integrity and authority boundaries.
- **Sensitive-data review:** all records are synthetic; privacy or protected data is included only when its handling is itself under test.
- **Host-path or author-environment dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** incomplete `compliant_campaign_revision`; inconsistent `legitimate_message_preservation`; a polished handoff without the required state change; or an unsupported execution/approval claim.
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
