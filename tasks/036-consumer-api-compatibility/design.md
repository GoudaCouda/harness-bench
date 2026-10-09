# Task Design: `036-consumer-api-compatibility`

## 1. Workflow identity

- **Role:** API platform engineer repairing a schema compatibility gate.
- **Trigger:** safe response additions fail while old-consumer breaks pass.
- **Objective:** make compatibility directional and consumer-version specific.
- **Boundary:** no API deployment or consumer notification is authorized.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| OPENAPI-3.1.2 | OpenAPI Specification 3.1.2 | https://spec.openapis.org/oas/v3.1.2.html | 2026-08-26 |
| JSON-SCHEMA-2020-12-VALIDATION | JSON Schema Validation | https://json-schema.org/draft/2020-12/json-schema-validation | 2026-08-26 |

- **Adaptation:** OpenAPI object schemas, required arrays, null unions, and enums become a bounded consumer-driven analyzer that distinguishes request producers from response readers.
- **Private user logs:** None were used; operations, schemas, and consumer versions are synthetic.

## 3. Real-workflow justification

API evolution is not a symmetric diff. Clients send requests and read responses,
while strictness and exhaustive enums vary by deployed version. A practical gate
must reconcile schemas with actual consumer contracts before release.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/compatibility_contract.md` | directional compatibility policy |
| `repo/src/compatibility.py` | broken symmetric analyzer |
| `repo/compatibility_cases.json` | visible old/new schemas and consumers |
| `repo/tests/test_public.py` | public required/addition checks |

## 5. Hidden ground truth

The hidden evaluator expands `repo/compatibility_cases.json` with required/null,
request value, response field, enum, strict-reader, removed-operation, and unused
operation states. `repo/src/compatibility.py` must emit sorted consumer issues;
`repo/compatibility_report.json` must reproduce visible decisions.

## 6. Expected workflow

1. Read `repo/docs/compatibility_contract.md` and classify request/response state.
2. Run `repo/tests/test_public.py` and inspect the current issue keys.
3. Repair `repo/src/compatibility.py` using consumer-scoped directional rules.
4. Generate `repo/compatibility_report.json` and confirm deterministic ordering.
5. Write version-snapshot risk and verification in `repo/REVIEW_NOTES.md`.

## 7. Harness demands

The task needs schema/consumer evidence integration, code execution, exact issue
output, multi-step verification, and restraint at deployment/communication limits.

## 8. Stressors and difficulty

- **Plausible failure mode:** compare symmetrically, conflate missing and null,
  mark every enum change, ignore old consumers, or inspect unused operations.
- **Difficulty rationale:** the same field change is safe or unsafe depending on
  direction, declared values, strictness, and consumer version.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `directional_required_and_nullability` | 0.35 | core | Request and response changes are evaluated directionally |
| `enum_strict_reader_and_scope` | 0.25 | core | Enum evolution, strict readers, and operation scope are reconciled |
| `visible_compatibility_report` | 0.05 | core | Visible schema reviews are reproducible |
| `verification_handoff` | 0.20 | handoff | Compatibility reasoning and verification are handed off |
| `source_and_workspace_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/compatibility.py`, `repo/compatibility_report.json`, `repo/REVIEW_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden consumer/schema combinations and reference issues are excluded. The AST
audit permits pure structured computation only. Evidence edits, unsafe workspace
nodes, dynamic capability, deployment, and notification claims fail closed.

## 11. Pilot plan

After deterministic reference/empty/untouched checks and malformed-input behavior scored by affected blocks and leakage/isolation gates, run a fresh Gemma
+ OpenClaw trial and inspect issue attribution rather than only total score.

- **Expected Gemma/OpenClaw failure modes:** symmetric required handling,
  nullable/missing confusion, unconditional enum flags, or strict-reader noise.

## 12. Human validation status

- **Status:** `not_required`.
- Deterministic and model gates remain required; this does not claim human approval.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `directional_required_and_nullability`.
- `validation_and_replay`: `enum_strict_reader_and_scope`, `visible_compatibility_report`, `source_and_workspace_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
