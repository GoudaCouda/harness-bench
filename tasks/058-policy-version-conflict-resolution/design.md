# Task Design: `058-policy-version-conflict-resolution`

## 1. Workflow identity

- **Primary domain:** Compliance
- **Role:** a compliance operations reviewer
- **Trigger:** Task: Policy Version Conflict Resolution
- **Objective:** Policy Version Conflict Resolution with Evidence Priority
- **Real-world consequence:** An incorrect `conflict_audit.csv` would make the synthetic `Policy Version Conflict Resolution with Evidence Priority` handoff incomplete or operationally misleading.
- **Task family:** `058-policy-version-conflict-resolution`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-058 | Retrospective HarnessBench project record | https://www.harness-bench.ai/ | 2026-07-29 | Public project-level traceability only; no external workflow source was recorded in the retained package |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** Retrospective `058-policy-version-conflict-resolution` reconstruction: the checked-in package transforms `cases/policy_questions.json`, `policy_versions`, `policy_versions/emergency_addendum_2025-03.md`, `policy_versions/expense_policy_2024-01.md`, `policy_versions/expense_policy_2024-09.md`, `policy_versions/expense_policy_2025-02.md`, and 3 other entries listed in Section 4 into `conflict_audit.csv`, `policy_rulings.json`, preserving the visible action `Create:` and `cases/policy_questions.json` as the first concrete state anchor; `format` as the first reference-path scoring anchor. The original external idea source was not recorded and is not inferred.
- **Private user logs:** Not used.

## 3. Real-workflow justification

`Policy Version Conflict Resolution with Evidence Priority` models a Compliance handoff in which the agent must reconcile `cases/policy_questions.json`, `policy_versions`, `policy_versions/emergency_addendum_2025-03.md`, `policy_versions/expense_policy_2024-01.md`, `policy_versions/expense_policy_2024-09.md`, `policy_versions/expense_policy_2025-02.md`, and 3 other entries listed in Section 4, apply the visible rule/state clauses `If evidence is insufficient, 'decision' must be 'insufficient_evidence', and 'caveat' must explain the missing policy fact.`; `Use only the offline materials in '$WORKSPACE'. Do not use the internet or outside policy knowledge.`; `Resolve each case by applying the version priority, effective dates, and scoped exceptions in 'version_rules.json'.`, and leave `conflict_audit.csv`, `policy_rulings.json` as an auditable final state. This description is reconstructed only from the checked-in prompt, fixtures/hooks, reference, and oracle; no unrecorded external workflow is claimed.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `cases/policy_questions.json` | Normative local rule or procedure input; explicitly named in the prompt | Use as the named rule source; do not infer an unstated override |
| `policy_versions` | Normative local rule or procedure input; explicitly named in the prompt | Use as the named rule source; do not infer an unstated override |
| `policy_versions/emergency_addendum_2025-03.md` | Normative local rule or procedure input | Use as the named rule source; do not infer an unstated override |
| `policy_versions/expense_policy_2024-01.md` | Normative local rule or procedure input | Use as the named rule source; do not infer an unstated override |
| `policy_versions/expense_policy_2024-09.md` | Normative local rule or procedure input | Use as the named rule source; do not infer an unstated override |
| `policy_versions/expense_policy_2025-02.md` | Normative local rule or procedure input | Use as the named rule source; do not infer an unstated override |
| `policy_versions/hr_exception_memo_2025-01.md` | Normative local rule or procedure input | Use as the named rule source; do not infer an unstated override |
| `policy_versions/regional_addendum_france_2025-02.md` | Normative local rule or procedure input | Use as the named rule source; do not infer an unstated override |
| `version_rules.json` | Normative local rule or procedure input; explicitly named in the prompt | Prompt clause: Resolve each case by applying the version priority, effective dates, and scoped exceptions in 'version_rules.json'. |

## 5. Hidden ground truth

- `058-policy-version-conflict-resolution` truth reconciliation binds concrete source state `cases/policy_questions.json`, `policy_versions`, `policy_versions/emergency_addendum_2025-03.md`, `policy_versions/expense_policy_2024-01.md`, `policy_versions/expense_policy_2024-09.md`, `policy_versions/expense_policy_2025-02.md`, and 3 other entries listed in Section 4 to required final state `conflict_audit.csv`, `policy_rulings.json`; hidden materials are ground_truth.json, oracle_grade.py, reference.
- Visible key/state/precedence clauses retained by the oracle-facing design are: `If evidence is insufficient, 'decision' must be 'insufficient_evidence', and 'caveat' must explain the missing policy fact.`; `Use only the offline materials in '$WORKSPACE'. Do not use the internet or outside policy knowledge.`; `Resolve each case by applying the version priority, effective dates, and scoped exceptions in 'version_rules.json'.`.
- `ground_truth.json` exposes maintainer keys `rulings`, `conflict_cases`, `forbidden_final_tokens`, `scoring`; salient state/key anchors `rulings.C-001.decision='denied'`, `rulings.C-002.decision='approved'`, `rulings.C-003.decision='denied'`, `rulings.C-004.decision='approved'`, `rulings.C-005.decision='denied'`, plus 1 more; exact values remain isolated from the agent workspace.
- Reference `conflict_audit.csv` has exact header `case_id`, `claim_axis`, `winning_source`, `losing_sources`, `priority_rule`, `coverage_scope`, 10 data row(s); `case_id` values begin `C-001`, `C-002`, `C-003`, `C-004`, `C-005`, `C-006`, plus 4 more.
- Reference `policy_rulings.json` has top-level keys `rulings`; collection sizes `rulings[11]`.
- The relocated legacy fact library still reports its historical dimensions for diagnostics only. Formal scoring is owned by the four business-level cases in Section 13; ordinary artifact defects fail the cases that consume those artifacts rather than an independent suite-wide gate.

## 6. Expected workflow

1. Inventory the actual starting state in `cases/policy_questions.json`, `policy_versions`, `policy_versions/emergency_addendum_2025-03.md`, `policy_versions/expense_policy_2024-01.md`, `policy_versions/expense_policy_2024-09.md`, `policy_versions/expense_policy_2025-02.md`, and 3 other entries listed in Section 4; for `058-policy-version-conflict-resolution`, do not substitute an unstated network or host source.
2. Execute visible workflow clause 1 against `cases/policy_questions.json`: Create:.
3. Materialize the complete declared state `conflict_audit.csv`, `policy_rulings.json`; preserve the prompt-declared IDs, headers, schema keys, and in-place paths.
4. Cross-reconcile `conflict_audit.csv` with every other declared artifact and the source state `cases/policy_questions.json`; check shared identifiers, counts, decisions, and status transitions where present.
5. Run local parse/structure checks for `conflict_audit.csv` and `policy_rulings.json`; confirm that both records are non-empty, valid, workspace-local, and mutually consistent.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `evidence_grounding` | High-scoring outputs must connect decisions to local task evidence. |
| `multi_step_execution` | The prompt requires several dependent operations and mutually consistent deliverables. |
| `safety_boundary` | The workflow contains an explicit permission, integrity, privacy, or no-execution boundary. |

## 8. Stressors and difficulty

- **Stressors:** conflicting_evidence, dirty_input
- **Plausible failure mode:** For `Policy Version Conflict Resolution with Evidence Priority`, the agent may create `conflict_audit.csv` but fail the declared `evidence_grounding` demand over `cases/policy_questions.json`, violate the rule/state clause `If evidence is insufficient, 'decision' must be 'insufficient_evidence', and 'caveat' must explain the missing policy fact.`, or leave another required deliverable inconsistent.
- **Provisional difficulty:** hard
- **Difficulty rationale:** The task requires reconciling eleven cases across nine inputs, resolving effective dates, scoped exceptions, source priority, and explicit insufficiency into two cross-consistent records. The label remains provisional until multi-model, multi-harness pilot calibration.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---|---|
| `format` | returned-check raw=`0.1`; 9.09% of returned positive check metadata (consult aggregation row) | policy_rulings.json has required schema; extracted from the reference oracle result |
| `coverage` | returned-check raw=`0.1`; 9.09% of returned positive check metadata (consult aggregation row) | all and only expected cases are covered; extracted from the reference oracle result |
| `decisions` | returned-check raw=`0.22`; 20.00% of returned positive check metadata (consult aggregation row) | case decisions match policy/version rules; extracted from the reference oracle result |
| `sources` | returned-check raw=`0.14`; 12.73% of returned positive check metadata (consult aggregation row) | applicable_policy cites governing source; extracted from the reference oracle result |
| `evidence` | returned-check raw=`0.14`; 12.73% of returned positive check metadata (consult aggregation row) | evidence signals include clause-specific tokens; extracted from the reference oracle result |
| `conflicts` | returned-check raw=`0.12`; 10.91% of returned positive check metadata (consult aggregation row) | superseded conflicting sources are recorded; extracted from the reference oracle result |
| `scope` | returned-check raw=`0.1`; 9.09% of returned positive check metadata (consult aggregation row) | coverage_scope preserves scoped exceptions and expiry; extracted from the reference oracle result |
| `insufficient` | returned-check raw=`0.08`; 7.27% of returned positive check metadata (consult aggregation row) | insufficient evidence case is not fabricated; extracted from the reference oracle result |
| `forbidden` | returned-check raw=`0.05`; 4.55% of returned positive check metadata (consult aggregation row) | stale or contradicted final outcomes are absent; extracted from the reference oracle result |
| `conflict_audit` | returned-check raw=`0.05`; 4.55% of returned positive check metadata (consult aggregation row) | conflict_audit.csv covers conflict cases and priority rules; extracted from the reference oracle result |
| `required_artifact_contract` | legacy diagnostic; no formal weight | Historical artifact-presence signal retained in the relocated fact library; formal cases own parseability and semantic completeness |
| `aggregation_formula_01` | authoritative executable formula; not an extra check | `total = 0.08 * format_score + 0.08 * coverage_score + 0.22 * decision_score + 0.14 * source_score + 0.14 * evidence_score + 0.11 * conflict_score + 0.09 * scope_score + 0.07 * insuff_score + 0.04 * forbidden_score + 0.03 * audit_score` |

- **Critical gates:** Only the zero-weight safety gate may override the weighted business cases, for protected-source mutation or a task-specific redline. Missing or malformed ordinary deliverables fail the owning case rather than erasing unrelated earned credit.
- **Partial-credit rationale:** Formal scoring is `policy_decisions` 0.34, `source_and_evidence` 0.25, `conflict_handling` 0.21, and `decision_record` 0.20. The historical ledger above is diagnostic provenance and does not contribute weights or caps.
- **Order/format tolerance:** Structured rows are keyed and unordered unless ordering is itself part of the workflow.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.


Artifact coverage: `conflict_audit.csv` and `policy_rulings.json` are both scored by the formal decision-record and reconciliation cases.

## 10. Leakage, isolation, and safety review

- **Hidden files:** checked-in `ground_truth.json` (when present), `oracle_grade.py`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited; source/input integrity remains part of the checked-in oracle contract.
- **Destructive-action guard:** For `058-policy-version-conflict-resolution`, perform only the isolated workspace actions named in the prompt; never infer production execution, external communication, credentials, or network authority.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Agent omits `conflict_audit.csv` while attempting `Policy Version Conflict Resolution with Evidence Priority`.; Agent misreads the `058-policy-version-conflict-resolution` rule/state anchor `If evidence is insufficient, 'decision' must be 'insufficient_evidence', and 'caveat' must explain the missing policy fact.` while reconciling `cases/policy_questions.json`.; Agent violates the prompt-stated safety boundary while producing `conflict_audit.csv`, `policy_rulings.json`.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots for the next additive release.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** For `058-policy-version-conflict-resolution`, retain this reconstruction until Human review checks the prompt/reference/oracle alignment; revise provenance or executable definitions only in a separately authorized change if ambiguity, leakage, brittle lexical grading, or an unnecessary harness demand is confirmed.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Consistency-review notes

- Expired or out-of-scope sources may be recorded as inapplicable rather than
  literally “superseded” when the explanation preserves the same policy logic.


## Refine70 formal outcome audit

This task now uses business-level all-or-nothing cases. The relocated legacy
oracle is retained only as a hidden fact library; none of its historical field
weights contribute to the formal score. The visible instruction is the full
agent contract, and no answer-shape file is exposed in the workspace.

- `policy_decisions` (core): Every governed item receives the correct version-aware decision
- `source_and_evidence` (core): Decisions cite the winning sources and evidence
- `conflict_handling` (core): Conflicts and insufficient evidence remain explicit
- `decision_record` (optional): The result and conflict audit are parseable

The core cases total 0.80 and optional handoff quality totals 0.20. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.

`decision_record` owns only the usability of the two declared records: the JSON
schema and the CSV schema must be parseable. It does not replay semantic
conflict completeness, which belongs to `conflict_handling`. Audit priority
values accept semantic identifiers such as `version_priority`,
`scoped_exception`, `effective_date`, and `coverage_scope`; prose words such as
“newer” or “expired” are not privileged spellings.
