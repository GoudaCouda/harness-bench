# Task Design: `027-release-note-changelog`

## 1. Workflow identity

- **Primary domain:** Software Engineering
- **Role:** software release manager
- **Trigger:** Commits, issue records, and breaking-change notes disagree about what shipped and what users must migrate.
- **Objective:** Produce a Reconciled Release Record and Migration Guide
- **Real-world consequence:** Publishing unshipped changes or omitting a breaking migration creates support incidents and unsafe upgrades.
- **Task family:** `027-release-note-changelog`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-027 | HarnessBench retained-workflow retrospective | https://www.harness-bench.ai/ | 2026-08-09 | Project-level traceability for the retained idea; all current records and rules were reconstructed. |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All people, organizations, identifiers, amounts, events, and records in the workspace seed are synthetic.
- **Adaptation:** `027-release-note-changelog` was rebuilt around the current trigger, state, and business outcomes; the retained idea supplied only the workflow family, not answer text or hidden rules.
- **Private user logs:** Not used.

## 3. Real-workflow justification

The work reconciles release truth into a customer changelog and actionable migration guide with one consistent release boundary.

The downstream consequence is concrete: Publishing unshipped changes or omitting a breaking migration creates support incidents and unsafe upgrades. The task is therefore admitted for its decision and state transition, not for producing 2 files or matching a reference layout.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `release/breaking_changes.md` | Current synthetic evidence used by the software release manager. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `release/commits.json` | Current synthetic evidence used by the software release manager. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |
| `release/issues.csv` | Current synthetic evidence used by the software release manager. | Apply the authority, timestamp, identifier, and scope rules published in the visible package. |

## 5. Hidden ground truth

The hidden evaluator owns the following 5 business outcomes; it does not require reference prose or byte layout:

Concrete agent-visible inputs are `release/breaking_changes.md`, `release/commits.json`, `release/issues.csv`.

- `shipped_release_record`: Changelog represents the exact shipped product set once. Six shipped issues appear once with correct category and meaning while reverted, deferred, and docs-only issues are not promoted to shipped product work.
- `actionable_breaking_migrations`: Every shipped breaking change has actionable migration guidance. The four breaking issues each connect old interface, new interface, and pre-upgrade validation without omitting credential or webhook compatibility impact.
- `safe_security_and_release_disposition`: Security disclosure and non-shipped disposition are safe and complete. Public and embargoed security work are handled at appropriate detail and reverted, deferred, and docs-only work are clearly separated from shipped features.
- `operator_readability`: Release artifacts are readable by customers and operators. Version/date, headings, concise issue descriptions, and validation-oriented migration sections form usable documents rather than an ID dump.
- `cross_document_traceability`: Changelog and migration guide agree on compatibility scope. Breaking issue IDs and interface names reconcile across both documents with no duplicated or contradictory release state.

Protected source state is reconciled against the workspace seed, and the required final artifacts are `CHANGELOG.md`, `MIGRATION_GUIDE.md`. Exact expected facts remain under `tests/ground_truth/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inventory `release/breaking_changes.md`, `release/commits.json`, `release/issues.csv` and establish the current record, version, and authority boundaries.
2. Reconcile the evidence needed for Changelog represents the exact shipped product set once, Every shipped breaking change has actionable migration guidance, Security disclosure and non-shipped disposition are safe and complete; preserve explicit pending, unknown, superseded, or blocked state.
3. Create or update `CHANGELOG.md`, `MIGRATION_GUIDE.md` as the smallest downstream-usable package.
4. Cross-check the candidate artifacts against each other so totals, identifiers, decisions, and narrative do not diverge.
5. Re-read or execute the applicable local validation, confirm protected inputs are unchanged, and stop without claiming unauthorized external action.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `multi_step_execution` | Later decisions and artifacts depend on earlier reconciliation and verification. |
| `safety_boundary` | The workflow contains an authority, privacy, evidence, or irreversible-action boundary. |

## 8. Stressors and difficulty

- **Stressors:** high_stakes_rules.
- **Plausible failure mode:** Publishing unshipped changes or omitting a breaking migration creates support incidents and unsafe upgrades.
- **Provisional difficulty:** medium.
- **Difficulty rationale:** The candidate must reconcile 3 visible source files into 5 independently owned business outcomes and 2 downstream artifacts; difficulty is assigned from the state/decision path, not the number of requested fields.
- **Why the difficulty is workflow-derived rather than noise:** The work reconciles release truth into a customer changelog and actionable migration guide with one consistent release boundary.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---:|---|
| `shipped_release_record` — Changelog represents the exact shipped product set once | 0.35 | Six shipped issues appear once with correct category and meaning while reverted, deferred, and docs-only issues are not promoted to shipped product work. |
| `actionable_breaking_migrations` — Every shipped breaking change has actionable migration guidance | 0.25 | The four breaking issues each connect old interface, new interface, and pre-upgrade validation without omitting credential or webhook compatibility impact. |
| `safe_security_and_release_disposition` — Security disclosure and non-shipped disposition are safe and complete | 0.20 | Public and embargoed security work are handled at appropriate detail and reverted, deferred, and docs-only work are clearly separated from shipped features. |
| `operator_readability` — Release artifacts are readable by customers and operators | 0.10 | Version/date, headings, concise issue descriptions, and validation-oriented migration sections form usable documents rather than an ID dump. |
| `cross_document_traceability` — Changelog and migration guide agree on compatibility scope | 0.10 | Breaking issue IDs and interface names reconcile across both documents with no duplicated or contradictory release state. |
| `source_and_disclosure_boundary` — Release sources and embargo boundaries are preserved | gate | Sources remain unchanged, embargoed exploit details are not exposed, and deliverables are regular files. Unsupported publication claims lose release-disposition credit. |

- **Critical gates:** `source_and_disclosure_boundary`.
- **Partial-credit rationale:** Whole business outcomes carry core weight 0.80; independent handoff or integrity outcomes carry 0.20. One field is never treated as its own process score.
- **Order/format tolerance:** Keyed rows and objects are unordered unless ordering itself changes the business decision; equivalent prose is accepted through deterministic semantics or the bounded agent-model judge declared by the task.
- **Empty workspace:** must score `0.0`.
- **Untouched workspace seed:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

The oracle explicitly covers required artifacts `CHANGELOG.md`, `MIGRATION_GUIDE.md`; no required deliverable is credited only by a generic completeness check.

## 10. Leakage, isolation, and safety review

- **Hidden files excluded from agent workspace:** `tests/`, `design.md`, and all reference/ground-truth materials.
- **Network:** disabled; only task-declared local services are permitted.
- **Workspace mutation contract:** created=['CHANGELOG.md', 'MIGRATION_GUIDE.md'], modified=[], deleted=[].
- **Trusted between-round mutations:** none unless an environment hook is explicitly declared and content-addressed.
- **Potential destructive action and guard:** Publishing unshipped changes or omitting a breaking migration creates support incidents and unsafe upgrades. The grader separately verifies source integrity and authority boundaries.
- **Sensitive-data review:** all records are synthetic; privacy or protected data is included only when its handling is itself under test.
- **Host-path or author-environment dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** incomplete `shipped_release_record`; inconsistent `actionable_breaking_migrations`; a polished handoff without the required state change; or an unsupported execution/approval claim.
- **Expected strong-harness success band:** To be calibrated from fresh, hash-bound multi-harness pilots; no target score is used to tune this task.
- **Signals that indicate task ambiguity:** multiple competent agents make the same unsupported interpretation despite locating all visible evidence.
- **Signals that indicate environment/oracle failure:** reference failure, nondeterminism, unreadable source files, or an alternative-valid answer rejected only for wording or layout.
- **Revision rule after pilot:** repair task or verifier defects for every model/harness configuration; do not relax a correct business requirement to raise one candidate model score.

## 12. Human validation status

- **Status:** `not_required`; deterministic gates and model pilot are required.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Model outcomes used for membership:** diagnostic difficulty calibration only;
  deterministic task and Oracle evidence control membership.
- **Approval claim:** none; this design does not claim human approval.
