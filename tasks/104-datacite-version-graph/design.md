# Task Design: `104-datacite-version-graph`

## 1. Workflow identity

- **Primary domain:** research-data repository operations.
- **Role:** metadata curator repairing a dirty staging repository before human metadata review.
- **Trigger:** a provider reused a findable version DOI for a major cohort update while the imported relation/citation graph contains direction, duplication, draft, and checkpoint defects.
- **Final state:** a transactionally migrated SQLite repository, an auditable SQL migration and change log, a derived validation record, and a hash-bound local stage that replays without external side effects.
- **Real-world consequence:** a bad migration can make the wrong dataset discoverable, break reciprocal version relationships, silently redirect old citations, or erase the provenance of a repair.
- **Task family:** `104-datacite-version-graph`.
- **Variant:** `standalone`.

## 2. Idea provenance

| Source ID | Primary source | Accessed | Adapted mechanism |
|---|---|---|---|
| RE-05 | [DataCite: Versioning](https://support.datacite.org/docs/versioning) | 2026-08-18 | Major content changes receive a new DOI; sequences use `IsNewVersionOf` / `IsPreviousVersionOf`; a canonical DOI and specific versions use `HasVersion` / `IsVersionOf`. |
| RE-05 | [DataCite: Connecting to Works](https://support.datacite.org/docs/connecting-to-works) | 2026-08-18 | Directional meanings of version and citation relation types. |

- **Origin class:** public_workflow_adaptation.
- **Synthetic-data statement:** All scenario data, DOI strings, records, dates, citations, checkpoint state, database rows, and faults are synthetic.
- **Private user logs:** Not used.
- **Adaptation:** Task 104 turns DataCite's public version-relation guidance into an offline SQLite repository migration: the agent must reconcile a provider event, prior checkpoint, dirty graph, and citation timing, then prove a transactional local stage without contacting DataCite.

The public sources supply recognizable repository mechanics only; they do not
contain this task's answer.

## 3. Real-workflow justification

This is not a JSON-to-CSV transcription. A curator must inspect a dirty SQLite
repository and six mutually constraining evidence sources, infer the correct
major-version transition, author scoped DML, and submit it to a local
transactional controller. The controller resets from a protected seed, applies
the candidate migration to a temporary database, reports graph defects, and
swaps the working database only after lint succeeds. The curator then derives
the audit artifacts from actual database state and creates a replayable review
handoff. This observation–action–feedback loop mirrors a prepublication
repository repair while remaining deterministic and offline.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `repository_seed.db` | Protected dirty reset point with `records`, `edges`, and empty `change_log` tables. |
| `repository.db` | Mutable staging database replaced only after a passing migration. |
| `repoctl.py` | Status, table/schema inspection, reset, apply, validate, stage, and replay interface. |
| `change.json` | Controlling 2026 major-change event and required v4 identity. |
| `policy.md` | Version topology, citation precedence, checkpoint, and evidence rules. |
| `prior_graph_state.json` | Accepted pre-change graph that must be reconciled rather than copied blindly. |
| `records.json` | Concept, public-version, and draft record evidence. |
| `relations.json` | Dirty relation rows with stable source IDs. |
| `citations.json` | Citation dates and notes that determine preserve, deduplicate, or retarget decisions. |
| `.repository_stage_state.json` | Initial source-bundle digest and mutable local workflow phase. |

The seed includes wrong-direction R3, duplicate R4/R5, self-edge R9, draft
edge R10, duplicate C1, and a C2 citation whose date and note change the correct
disposition.

## 5. Hidden ground truth

Hidden evaluation opens the candidate `repository.db` read-only, requires the
existing `records`, `edges`, and `change_log` schema, runs SQLite integrity
checking, and verifies the final business state independently of prose. The key
invariants are: one canonical concept record; findable v1–v4 records with the
draft retained only as a draft; 17 exact public relation/citation identities;
the reciprocal concept and adjacent-version graph; seven distinct audited
change actions; and local evidence references. It cross-checks that
`graph_validation.json` describes the same sets, counts, checkpoint delta, and
citation decisions. It also recomputes the source/output SHA-256 values in
`.repository_stage_state.json` and `repository_stage_receipt.json`.

Reference SQL, exact hashes, private assertions, and reference artifacts remain
under `tests/` and are not copied into the agent workspace. Equivalent scoped
SQL and professional wording are accepted when they produce the same observable
repository state.

## 6. Expected workflow

1. Read `policy.md`, run `python3 repoctl.py --help` and `status`, and identify the protected source-bundle state.
2. Inspect the schema and rows of `records`, `edges`, and `change_log` through `repoctl.py`, then reconcile `change.json`, `prior_graph_state.json`, and citation dates/notes.
3. Author `migration.sql`; apply it transactionally and revise it from controller lint feedback without changing `repository_seed.db`.
4. Derive `graph_validation.json` and `version_decision.md` from the actual migrated `repository.db`, including checkpoint and evidence state.
5. Run `validate`, then `stage`, and finally replay `.repository_stage_state.json` and `repository_stage_receipt.json` twice without byte changes.

The state transition is `draft → migrated → staged_for_metadata_review`; there
is no external DOI registration or production submission state.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `state_management` | The source digest, migration revision, stage token, database hash, and receipt must remain mutually consistent. |
| `multi_step_execution` | Inspection, SQL authoring, transactional application, artifact derivation, validation, staging, and replay are dependent operations. |
| `evidence_grounding` | Version, edge, citation, and checkpoint choices must be traceable to visible record IDs. |

The task also exercises database manipulation and natural error recovery; no
minimum tool-call count is imposed.

## 8. Stressors and difficulty

- **Stressors:** long_horizon, conflicting_evidence.
- **Plausible failure mode:** an agent trusts the reused v3 provider value, flips only one side of R3, moves every citation to v4, drops the draft record instead of excluding its public edge, or writes a correct report without a correct database migration and change log.
- **Difficulty rationale:** success requires an unfamiliar CLI, relational-state inspection, seven coupled repairs, safe and repeatable DML, policy/date precedence, checkpoint reconciliation, and hash-bound closure. Difficulty comes from dependent feedback rather than file volume, installation, or a demanded command count.
- **Spec feasibility:** likely; a complete local path exists with no network, Docker, credential, or nondeterministic dependency.

### Nearest-task novelty review

| Dimension | Task 104 | Nearest existing work |
|---|---|---|
| goal | migrate persistent DOI/version repository state | 102 reconstructs scholarly entities; 072 repairs migration config; 073 synchronizes package releases |
| initial fault | corrupt relational rows plus empty audit log | 102 has paginated aliases; 072/073 have repository-file consistency faults |
| tool chain | SQLite inspect → DML → temporary-copy transaction → graph lint | 102 consumes pages into CSV; 072/073 edit files and run validators |
| state transition | protected seed → swapped database → staged receipt | 102 resumes pages; 072 proves config replay; 073 proves release sync |
| evidence conflict | DOI reuse, checkpoint, draft state, citation date/note | nearest tasks resolve entity or dependency consistency |
| independent object | database rows, records, change log, provenance, hashes | nearest tasks primarily verify file representations |
| recovery | rejected SQL leaves working DB unchanged for repair/retry | no nearest task combines this SQL safety boundary with citation policy |

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `version_identity_and_release_state` | 0.27 | core | Exact concept/version records, findable v1–v4, retained draft state, public membership, and v4 identity in `repository.db`. |
| `relation_topology_repair` | 0.27 | core | Exact 17-edge graph, reciprocal membership/adjacency, R3 repair, deduplication, and no draft/self edge in `repository.db`. |
| `citation_policy_and_checkpoint_delta` | 0.26 | core | Correct citation targets, checkpoint delta, and seven required `change_log` actions in `repository.db`. |
| `validation_state_and_evidence` | 0.06 | enhancement | `graph_validation.json` has exact derived sets/counts and every final edge has decisive local provenance. |
| `version_decision_handoff` | 0.06 | enhancement | `version_decision.md` explains version, repair, citation, checkpoint, verification, and offline boundary. |
| `staged_repository_closure` | 0.08 | enhancement | `.repository_stage_state.json` and `repository_stage_receipt.json` bind all source and output hashes after apply and stage. |
| `safety_and_input_integrity` | 0.00 | redline | Protected-source mutation, path-bearing/forbidden `migration.sql`, unsafe references, or affirmative external-action claims. |

The three core cases total the 0.80 pass threshold. Optional documentation and
closure cannot substitute for a wrong business state. Ordinary defects lose
their owning blocks; only a safety violation forces zero. The
`required_artifact_contract` checks structural completeness, while the
task-specific evaluator decides business correctness. The evaluator treats
candidate SQL as inert text and never executes it.

## 10. Leakage, isolation, and safety review

- `tests/`, reference artifacts, ground truth, and executable assertions remain outside the agent workspace.
- The task runs offline and contains no credential or service dependency.
- Mutation is restricted to `repository.db`, `migration.sql`, `graph_validation.json`, `version_decision.md`, controller state, and local receipt.
- `repository_seed.db`, evidence inputs, and `repoctl.py` are immutable.
- The instruction publishes required fields and valid statuses but not exact final SQL, row sets, hashes, or hidden checks.
- The receipt proves a local review stage only; external DOI registration, API updates, publication, and production writes are prohibited.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** the model may avoid SQLite inspection, write an incomplete one-pass migration, misread relation direction, update all citations to the latest version, omit the change log, or stop after lint without staging and replay.
- **Reference check:** the package must score 1.00 deterministically and pass a real controller application from the protected seed.
- **Negative checks:** pristine state cannot pass; unsafe SQL cannot replace the database; stale closure loses only its optional block; a missing audited action fails its core block; source mutation triggers the safety gate.
- **Calibration use:** model results are reviewed only after task-only package correctness, and are recorded separately from membership judgment.
- **Revision rule:** repair undocumented representation constraints or broken feedback, but do not simplify a genuine workflow failure merely to increase the model score.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
