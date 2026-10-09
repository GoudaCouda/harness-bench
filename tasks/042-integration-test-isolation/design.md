# Task Design: `042-integration-test-isolation`

## 1. Workflow identity

- **Role:** CI engineer repairing a local integration-test runner.
- **Trigger:** fixture leakage and order-dependent randomness create flakes.
- **Objective:** isolate state while preserving genuine failures and quarantine expiry.
- **Boundary:** no external CI or quarantine service mutation is authorized.

## 2. Idea provenance

| Source ID | Source | URL | Accessed |
|---|---|---|---|
| PYTEST-FIXTURE-SCOPE | pytest fixture reference | https://docs.pytest.org/en/stable/reference/fixtures.html | 2026-08-26 |
| PYTEST-FLAKY-TESTS | pytest flaky-test guidance | https://docs.pytest.org/en/stable/explanation/flaky.html | 2026-08-26 |

- **Adaptation:** fixture-scope, state control, and deterministic-randomness guidance become a dependency-free descriptor runner with deep isolation and an expiring quarantine state.
- **Private user logs:** None were used; tests, fixtures, seeds, and quarantine records are synthetic.

## 3. Real-workflow justification

Order-sensitive integration failures waste CI capacity and are often hidden by
indefinite quarantine. Reproducing them requires controlling fixture ownership,
random streams, execution order, and truthful failure status in one runner.

## 4. Agent-visible inputs

| Path | Purpose |
|---|---|
| `repo/docs/isolation_contract.md` | runner DSL and outcome rules |
| `repo/src/isolation_runner.py` | broken shared-state implementation |
| `repo/isolation_cases.json` | visible suites and quarantine state |
| `repo/tests/test_public.py` | public isolation/expiry checks |

## 5. Hidden ground truth

Hidden suites reorder tests and vary nested fixture state, assertion state,
random streams, and quarantine records beyond `repo/isolation_cases.json`. Final
`repo/src/isolation_runner.py` must deep-copy every fixture, derive per-test
streams, and preserve true failures; `repo/isolation_report.json` must be exact.

## 6. Expected workflow

1. Read `repo/docs/isolation_contract.md` and map fixture/test/quarantine keys.
2. Run `repo/tests/test_public.py` and reproduce state leakage and expiry.
3. Repair `repo/src/isolation_runner.py` with deep copies and stable ID seeds.
4. Generate `repo/isolation_report.json` without suppressing regression state.
5. Record external-fixture risk and verification in `repo/REPAIR_NOTES.md`.

## 7. Harness demands

The harness must inspect code/data, execute tests, reason about repeated state,
produce exact artifacts, verify outcomes, and avoid external CI actions.

## 8. Stressors and difficulty

- **Plausible failure mode:** shallow-copy lists, share one random stream, skip
  quarantine, use an exclusive expiry boundary, or turn real failures into pass.
- **Difficulty rationale:** order invariance, deterministic entropy, status, and
  nested object ownership must all hold across independent cohorts.

## 9. Oracle design

| Case | Weight | Role | Measured outcome |
|---|---:|---|---|
| `fixture_isolation_and_true_outcomes` | 0.35 | core | Every test receives isolated state and real assertions remain visible |
| `stable_seed_and_quarantine_boundary` | 0.25 | core | Random streams and expiring quarantine are deterministic |
| `visible_isolation_report` | 0.05 | core | Visible suites are reproduced exactly |
| `verification_handoff` | 0.20 | handoff | Isolation repair and residual risk are handed off |
| `source_and_workspace_boundary` | 0.15 | core | Validation and offline task boundaries are respected |

Explicitly graded required artifacts: `repo/src/isolation_runner.py`, `repo/isolation_report.json`, `repo/REPAIR_NOTES.md`.

The task pass threshold is 0.80. The 0.15 validation block is an ordinary scored core requirement: a malformed-input or offline-boundary mistake loses that block but does not erase unrelated business logic. Empty and untouched workspaces still score 0.00 because they complete none of the measured work.

Only framework-level artifact/workspace red lines—protected-state tampering, unsafe filesystem nodes or path escape, or a real prohibited action—can force the numeric score to zero. The case manifest and evaluator remain authoritative for exact artifact targets and equivalent-output handling.

## 10. Leakage, isolation, and safety review

Hidden reorderings and reference outcomes are excluded. The candidate runs in a
bounded pure worker with no I/O or imports. Input mutation, unsafe nodes, and
claims of changing external CI/quarantine state fail closed.

## 11. Pilot plan

Require reference 1.0, empty/untouched 0.0, and malformed-input behavior scored by affected blocks, then run a fresh Gemma +
OpenClaw trial and compare reordered-test outcomes and final status labels.

- **Expected Gemma/OpenClaw failure modes:** shallow clone, Python `hash` seed,
  global RNG consumption, expiry off-by-one, or quarantined pass masking.

## 12. Human validation status

- **Status:** `not_required`.
- Automated gates and calibration remain required; no human approval is claimed.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `fixture_isolation_and_true_outcomes`.
- `validation_and_replay`: `stable_seed_and_quarantine_boundary`, `visible_isolation_report`, `source_and_workspace_boundary`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
