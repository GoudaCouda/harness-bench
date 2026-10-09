# Task Design: `162-degree-prerequisite-audit`

## 1. Workflow identity

- **Domain:** Education administration
- **Role:** registrar analyst auditing degree progress
- **Trigger:** transcript, equivalency, substitution, and prerequisite evidence
  include current and expired rules plus no-double-count constraints.
- **Objective:** assign valid evidence to requirements, derive prerequisite
  eligibility, generate an audit and receipt, verify, replay, and hand off.

## 2. Idea provenance

- **Source:** `EDU-DEGREE-01`, informed by U.S. Department of Education
  accreditation and transfer-credit materials:
  https://www.ed.gov/laws-and-policy/higher-education-laws-and-policy/college-accreditation
- **Adaptation:** Transfer-credit policy mechanics become an offline audit over
  synthetic SQLite records, dated equivalencies, an approved substitution,
  unique assignment, prerequisite graph state, and generated evidence.
- **Private user logs:** None; every student and academic record is synthetic.
- **Synthetic-data statement:** All workspace people, organizations,
  identifiers, academic records, equivalencies, and events are synthetic.

## 3. Real-workflow justification

A registrar audit must select the applicable catalog/rule versions, avoid
double counting, distinguish completion from future eligibility, and preserve
the boundary against conferral. The workflow requires relational inspection,
graph traversal, dated policy reasoning, validation feedback, deterministic
finalization, verification, and replay.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `degree.db` | transcript, transfer, equivalency, substitution, and rule records |
| `degree_seed.sql` | inspectable schema and initial relational state |
| `catalog.json` | requirements and prerequisite graph |
| `degree_policy.md` | validity, assignment, eligibility, and safety rules |
| `degreectl.py` | transcript, requirements, graph, validate, finalize, and verify |

## 5. Hidden ground truth

The evaluator derives valid assignments from `degree.db`, catalog, and policy.
The required final state consists of exact `degree_plan.json`, generated
`degree_audit.json`, digest-bound `audit_receipt.json`, and scoped
`advising_handoff.md`. Requirement keys, unique course use, dated equivalency,
substitution scope, prerequisite eligibility state, and hashes are invariants.

## 6. Expected workflow

1. Inspect transcript and rule state in `degree.db` using `degreectl.py`.
2. Inspect `catalog.json` requirements and prerequisite graph keys.
3. Write `degree_plan.json` with unique evidence assignments and dated rules.
4. Validate and correct double-counting, equivalency, substitution, or graph errors.
5. Finalize `degree_audit.json` and verify `audit_receipt.json` against the plan.
6. Re-finalize to prove stable state, then write `advising_handoff.md`.

## 7. Harness demands

The task requires evidence grounding, SQLite queries, graph reasoning,
time-aware policy, feedback correction, generated artifact verification,
idempotence, and a no-conferral boundary.

## 8. Stressors and difficulty

- **Plausible failure mode:** use an expired equivalency or reuse one course for
  two requirements, producing plausible progress totals with invalid evidence
  assignment and prerequisite state.
- **Difficulty rationale:** dated transfer rules, scoped substitution, unique
  assignment, completion versus eligibility, generated audit, digest binding,
  and replay must close together.

## 9. Oracle design

| Case | Weight | Business-level outcome |
|---|---:|---|
| `requirement_assignment` | 0.30 core | all requirements use valid unique evidence |
| `equivalency_substitution_prerequisite` | 0.30 core | dated rules, substitution, and graph state agree |
| `generated_audit_receipt` | 0.20 core | audit facts and receipt bind the submitted plan |
| `advising_handoff` | 0.20 optional | progress, remaining work, eligibility, and scope |
| `safety_and_input_integrity` | gate | records and no-conferral boundary hold |

Core blocks total 0.80 and explicitly cover `degree_plan.json`,
`degree_audit.json`, and `audit_receipt.json`; `advising_handoff.md` is the
bounded communication block. Row fields explain failure but do not independently
earn piecemeal credit.

## 10. Leakage, isolation, and safety review

Student records are synthetic and the controller has no registrar integration.
Hidden truth remains outside the workspace. Database, catalog, policy, and tool
are immutable; only declared outputs may be created. No degree can be conferred.

## 11. Pilot plan

Run reference, empty, untouched, malformed, expired-equivalency,
double-counting, substitution, prerequisite, receipt, replay, and safety
The shared runtime intentionally has no database sidecar: the assessed state is
the supplied SQLite file, and both the controller and evaluator open that real
database through Python's SQLite driver. The agent environment probe exercises
transactions and read-only URI access; the independent grader probe exercises
SQLite, canonical receipt hashing, YAML, and grading APIs.
adversarials, then a fresh Gemma 4 31B + OpenClaw trajectory.

- **Expected Gemma/OpenClaw failure modes:** choose expired equivalency, double
  count a course, overextend substitution, confuse eligibility with completion,
  hand-author audit state, or skip replay.

## 12. Human validation status

- **Status:** `not_required` under the current deterministic acceptance policy.
- **Evidence level:** task-only quality/discrimination plus Docker-reference
  verification; model pilots remain optional calibration.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
