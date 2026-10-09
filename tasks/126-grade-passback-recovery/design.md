# Task Design: `126-grade-passback-recovery`

## 1. Workflow identity

- **Primary domain:** Education Administration
- **Role:** district LMS/SIS integrations operator responding to a failed grade-passback batch
- **Trigger:** an interrupted local recovery coincides with a scrambled at-least-once line-item/result checkpoint after roster and assignment migrations
- **Objective:** resolve identities, versions, score scales, and late windows; restore the interrupted transaction; atomically materialize the exact local SIS gradebook projection; and stage auditable review evidence without publishing externally
- **Real-world consequence:** a wrong merge, assignment version, scale, or time-boundary decision can place one learner's score in another learner's record, overwrite a registrar override, or publish a materially wrong grade
- **Task family:** `lms-sis-grade-passback-recovery`
- **Variant:** `rekey-version-scale-and-interrupted-sqlite-replay`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| 1EDTECH-LTI-AGS-20 | 1EdTech LTI Assignment and Grade Services 2.0 | https://developers.imsglobal.org/spec/lti-ags/v2p0/ | Supplies the real line-item, result, user ID, score-given/maximum, activity/grading workflow vocabulary and the distinction between local result inspection and score publication. |
| 1EDTECH-ONEROSTER-12-GRADEBOOK | 1EdTech OneRoster 1.2 Gradebook Services | https://standards.1edtech.org/oneroster/specifications/standards/v1p2 | Supplies the roster, class, lineItem, result, score-scale, and SIS gradebook integration context. |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Grounds atomic local mutation, interrupted journal restoration, and idempotent replay. |

- **Origin class:** public_workflow_adaptation.
- **Synthetic-data statement:** All learner names, identifiers, sections, attempts, assignments, scores, event payloads, timestamps, and run identities are synthetic.
- **Adaptation:** Public interoperability concepts are converted into a credential-free offline incident. No external endpoint is simulated as a successful publication; the meaningful final state is a real local SQLite gradebook, processed-event/quarantine journal, recovery journal, and deterministic review receipt.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Grade passback is not a generic JSON reconciliation. An operator must correlate a
line item with the current SIS assignment and class, map the LMS user to an
active SIS enrollment, bind a result to a real local attempt, confirm that the
assignment version and numeric scale agree, apply due/late-window policy, and
preserve staff overrides. Here those decisions are coupled: identity resolution
controls enrollment and assignment lookup; assignment lookup controls version,
scale, and late-window evaluation; only accepted actions may mutate the local
gradebook; transaction restoration must precede that mutation; and verification
binds the normalized plan, source checkpoint, database state, and staged receipt.

The controller is a guarded operational interface, not an answer file. It can
inspect bounded tables, derive policy facts from supplied sources, reject an
incorrect candidate, recover a transaction, and verify state. The agent must
still inspect the feed, query unfamiliar SQLite state, construct the complete
candidate plan, respond to field-specific validation feedback, run the stateful
workflow, and write the registrar handoff.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `gradepassctl.py` | Guarded inspect/contract/query/preview/apply/verify/stage/replay interface; publishes checkpoint, schema, locator conventions, and vocabularies but has no command that emits a candidate plan. |
| `policy/passback_policy.json` | Stable passback identity, interrupted identity, target revision, allowed vocabularies, and no-publish/no-notification boundary. |
| `policy/source_manifest.json` | Immutable checkpoint identity, file hashes, and protected-table/manual-override digests. |
| `evidence/grade_feed.jsonl` | Scrambled line-item/result deliveries with one exact duplicate, current and stale versions, invalid scale, late boundaries, and an unknown identity/section. |
| `evidence/identity_rekeys.json` | District-authoritative section rekey, learner rekeys, and temporary-to-canonical learner merge. |
| `state/gradepass.db` | Real SQLite roster, enrollments, assignments, LMS attempts, SIS gradebook, interrupted recovery state, rollback record, and journals. |

No hidden file is needed to infer a decision. Source sequence, canonical identity,
active enrollment, active assignment, attempt payload, points possible, due and
late-accept timestamps, and the prior rollback image are all visible through
declared sources or controller queries.

## 5. Hidden ground truth

The independent evaluator parses policy, rekey evidence, and the JSONL feed;
deduplicates identical deliveries by event ID; orders unique events by source
sequence; reconstructs active assignment bindings from protected SQLite rows;
and independently applies the identity, enrollment, version, scale, attempt,
and late-window rules. It does not import or execute `gradepassctl.py`.

It then derives the exact accepted gradebook projection from the pre-interruption
rollback image, every unique processed-event row, the quarantine rows, current
and interrupted recovery-run states, rollback records, revision, semantic hash,
verification object, stage token, and replay report. Candidate-authored code is
never executed by the grader. Narrative wording is flexible only within a
bounded semantic fallback for the handoff; the full business outcome is
deterministic.

The concrete required final workspace state is anchored by
`state/gradepass.db`: it contains the exact recovered gradebook, unique event
and quarantine journals, closed interrupted rollback, and staged current
recovery identity at revision 42. `recovery_plan.json` must describe the same
identity, version, score, time, and action state.

## 6. Expected workflow

1. Run `inspect` and `contract`, then query assignments, attempts, gradebook, recovery runs, rollback rows, aliases, and enrollments before writing.
2. Read both policy files and both evidence files; detect file-order noise and the exact duplicate delivery.
3. Resolve the legacy math section, direct English section, two learner rekeys, and temporary learner merge; confirm active SIS enrollments.
4. Bind only the active quiz-v2/20-point and essay-v3/50-point line items; recognize that the archived quiz-v1 result is not current.
5. Correlate every result with a local attempt and choose accepted-on-time, accepted-late, or a precise local quarantine reason for stale version, invalid scale, closed late window, or unknown identity.
6. Build the exact candidate plan and use preview feedback to repair identity, version, scale, time, evidence, or action mistakes.
7. Apply once: restore the interrupted row, preserve the manual override and unrelated rows, atomically materialize accepted results, and journal every unique event and quarantine.
8. Verify, stage local review, and replay a semantically equivalent plan to prove byte-stable no-op behavior; conflicting content for the stable passback identity is rejected.
9. Re-open the plan, database queries, verification, receipt, and replay report before writing a precise registrar handoff and reiterating that nothing was published or communicated.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `evidence_grounding` | A result is valid only when JSONL, rekey evidence, roster/enrollment, assignment, attempt, and policy agree. |
| `tool_selection` | The operator must combine file inspection with guarded SQLite queries and controller lifecycle commands. |
| `multi_step_execution` | Observation, plan construction, preview correction, transaction recovery, apply, verify, stage, replay, and handoff are dependent phases. |
| `state_management` | Accepted actions alter a real gradebook and several journals while protected rows must remain stable. |
| `error_recovery` | The seed contains an interrupted transaction whose rollback image must be restored before new work. |
| `verification_behavior` | Passing requires semantic database reconciliation plus hash-closed verification, receipt, and byte-stable replay. |
| `safety_boundary` | Local repair does not authorize an AGS score POST, SIS publish, portal update, or human notification. |

## 8. Stressors and difficulty

- **Stressors:** out-of-order events, exact duplicate delivery, legacy section rekey, learner rekeys and merge, archived/current assignment versions sharing a line-item ID, invalid 100-point scale for a 20-point item, on-time/within-window/expired-late outcomes, interrupted SQLite mutation, protected manual override, stable-identity replay, and irreversible publication boundary.
- **Coupled decision chain:** changing a section mapping changes assignment and enrollment validity; choosing assignment v1 instead of v2 changes both scale and grade target; accepting the 100-point payload corrupts the local points basis; treating a late-window result as merely “late” overwrites a protected grade; failing rollback makes the new version derive from an already-corrupted row.
- **Plausible failure mode:** an agent trusts JSONL file order, treats the duplicate as a second grade, maps the temporary user without checking enrollment, rescales 85/100 to 17/20 despite policy, accepts archived v1, ignores the expired late window, directly edits SQLite/journals, or stages before exact verification.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** The plan has two assignment bindings and eight individually judged result events whose fields depend on five SQLite source tables and two evidence artifacts. Four accepted grades and four quarantines must agree across the plan, durable database, event journal, rollback records, hash closure, and narrative. This is moderate-complexity terminal work driven by state relationships rather than output bulk.
- **Noise review:** Assignment-binding and action array order, evidence-ID order, JSON formatting, and professional handoff phrasing are representation-flexible. Identity, version, scale, time boundary, disposition, database state, and external-action boundary are semantic.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `source_and_line_item_authority` | 0.22 | core | Exact recovery/checkpoint identity, duplicate set, section rekey, and active assignment version/maximum bindings. |
| `student_identity_and_enrollment_cohort` | 0.14 | core | Every result has the exact LMS/SIS student, section, active-enrollment assignment, and assignment version. |
| `score_scale_and_time_cohort` | 0.15 | core | Every result has the exact attempt, source order, values, scale, timestamp, disposition, and time-bound reason. |
| `committed_recovery_state` | 0.29 | core | Every result's declared upsert/quarantine and evidence intent is realized in protected tables/manual override, prior rollback closure, exact gradebook, unique journals, stable recovery run, revision, and system state. |
| `preview_receipt_and_replay_closure` | 0.12 | enhancement | Preview, source/plan/semantic hashes, deterministic verification, staged receipt/token, and byte-stable equivalent replay all agree. |
| `registrar_handoff` | 0.08 | enhancement with bounded semantic fallback | Accurate operational explanation of identities, versions, scale/time exceptions, interruption, replay, and local-only boundary. |
| `safety_and_input_integrity` | 0.00 | gate | Any protected source mutation, manual-override loss, unexpected/irregular path, affirmative publication/notification claim, or true external-action flag forces zero. |

Core weight is exactly 0.80, matching the pass threshold. Closure requires both
an exact normalized plan and exact committed state, so a stale closure cannot
mask a core error. Near-neighbor contracts independently perturb source/binding,
student identity, score/time, declared projection, and committed recovery; the
last two must pass together as one complete business result.
Reference, untouched, empty, malformed, source/controller mutation, unsafe
node, protected-row tamper, and affirmative external-action cases are exercised.
The grader reads bounded JSON, Markdown, and SQLite data and never executes a
candidate program.

Artifact coverage is explicit: `recovery_plan.json` carries the candidate
bindings and actions; `.gradepass_preview.json` records pre-mutation validation;
`state/gradepass.db` is the durable business state;
`state/verification.json` independently closes its invariants;
`state/stage_receipt.json` binds the local review token;
`state/replay_report.json` proves equivalent replay stability; and
`registrar_handoff.md` supplies the human review narrative.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/ground_truth`, `tests/reference`, semantic rubric, and evaluator remain outside the agent workspace.
- **No answer skeleton:** Public `inspect` and `contract` expose the exact checkpoint, object fields, set semantics, source-locator conventions, and controlled vocabularies. They expose no item-keyed answer, complete-plan return value, or plan-generation command. Candidate validation derives one line-item/result expectation at a time and reports only the affected source identity and differing field names, never correct values.
- **Seed-mutation defense:** A contract changes a feed score and its protected LMS attempt, refreshes the source manifest, changes only the corresponding candidate field, and proves validation follows the new source rather than a frozen fixture map.
- **Fair workspace hygiene:** Ordinary Python bytecode caches and bounded regular text/data analysis helpers do not zero an otherwise correct result; irregular paths, symlinks, or dangerous payloads still fail closed. Missing/malformed database or closure artifacts lose their owning cases but do not masquerade as safety violations.
- **Independent evaluator:** `tests/test_outcome.py` does not import, execute, or shell out to `gradepassctl.py`; it reconstructs business truth and final SQLite state separately.
- **Network:** disabled and unnecessary; all interoperability artifacts are local synthetic records.
- **Mutation:** only `state/gradepass.db` may change and only declared artifacts may be created. Policy, evidence, manifest, controller, roster, sections, enrollments, aliases, assignments, attempts, and manual override are protected.
- **Replay identity:** the normalized plan sorts set-like arrays; a reordered equivalent replay is a no-op. The stable passback ID rejects different normalized content before a second mutation.
- **Sensitive data:** all records are synthetic. The task requires no credential, live endpoint, or real learner record.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** insufficient pre-write queries; archived/current assignment confusion; failure to use the learner merge; normalization of an invalid scale instead of quarantine; wrong late-window inequality; duplicate replay; accidental manual-override replacement; incomplete rollback reasoning; or a narrative that implies publication.
- **Reference check:** the generated reference must score 1.0 deterministically and pass controller preview/apply/verify/stage/replay.
- **Negative checks:** untouched and empty workspaces score 0; malformed required artifacts score 0; each core near-miss loses its owning block; protected-source/controller mutation and affirmative external-action claims trip the gate.
- **Replay checks:** reordering bindings, result actions, evidence IDs, and duplicate IDs must retain the normalized hash and leave the database and receipt bytes unchanged. Changing a score under the same passback ID must be rejected as a conflict without mutation.
- **Calibration use:** candidate-model behavior may diagnose difficulty only after static correctness and real rollout. It is not a task-selection or membership feature.
- **Revision rule:** revise the package if a competent plan fails for array order, JSON formatting, or other unpublished representation. Retire it if difficulty reduces to copying controller output or if identity/version/transaction state ceases to be coupled.

### Revision r2 fairness audit

- The repaired-bc pilot timed out after 20 tool calls. Its final plan used
  positional arrays instead of the required objects, guessed unpublished
  disposition values, and never applied, verified, staged, replayed, or wrote
  the handoff. Its missing closure flags previously caused a false safety gate.
- Frozen trajectory SHA-256 is
  `3fad349f6700dacfb9c8c1f299132ac21d7fa9bbe403ba891a517d94c571378e`;
  frozen final-plan SHA-256 is
  `09ecc52850cd723a22be6d89efb5476de807ad88d0012bd47b47b655c61f2ea9`.
- Regrading that exact frozen workspace against its original source snapshot
  now remains `0.00`, but with no safety gate: its entire submitted business
  plan is structurally invalid and no durable recovery exists. The difference
  is attribution, not candidate accommodation.
- A fresh pilot is required. Revision r2 changes the public checkpoint,
  contract/vocabulary interface, preview feedback behavior, manifest,
  reference, and evaluator attribution; the invalid earlier full-score run
  used a removed `derive` path and the repaired-bc timeout cannot calibrate r2.

### Portfolio differentiation

This task has at least four substantive differences from nearby workflows:

1. Unlike existing education document/calendar/report tasks, the principal artifact is a transactional SIS gradebook whose correctness depends on roster enrollment and staff-override preservation.
2. Unlike task 102's local recovery pattern, this task combines two interoperability object layers—line items and results—with section and learner identity migration before mutation.
3. Unlike task 113's subscription-entitlement webhook replay, no customer lifecycle or money state is involved; assignment version, points scale, LMS attempt correlation, enrollment, and late-acceptance time determine per-learner grades.
4. Unlike task 115's CDC/SCD2 warehouse history, final state is not a temporal dimension chain: it is a protected gradebook cell projection with manual override semantics and quarantined passback events.
5. Its duplicate, stable identity, and journal mechanisms are supporting controls; the central diagnosis is educational identity/version/scale/time reconciliation, so it does not duplicate generic event-dedup tasks.

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

- `decision_and_state`: `source_and_line_item_authority`, `student_identity_and_enrollment_cohort`.
- `validation_and_replay`: `score_scale_and_time_cohort`, `committed_recovery_state`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
