# Task Design: `145-permit-routing-constraint-repair`

## 1. Workflow identity

- **Domain:** Business Operations / municipal permitting
- **Role:** municipal systems operator
- **Trigger:** a zoning-map revision leaves routing configuration stale for
  current applications and a historical dual-overlay control.
- **Objective:** repair constraint precedence, replay current and historical
  routes, commit one digest-bound revision, and leave a no-decision handoff.

## 2. Idea provenance

- **Source:** `PUBLIC-PERMIT-01`, informed by the OGC standards catalogue:
  https://www.ogc.org/standards/
- **Adaptation:** Geospatial interoperability and permit-routing mechanics are
  transformed into a synthetic offline workflow with revised map attributes,
  additive overlays, ordered constraints, replay, and revision state.
- **Private user logs:** None; all records and revisions are synthetic.
- **Synthetic-data statement:** All workspace people, organizations,
  identifiers, spatial records, events, and revisions are synthetic.

## 3. Real-workflow justification

Permit routing after a map revision requires operators to reconcile versioned
spatial attributes with routing policy, preserve additive constraints, and
prove current applications and historical controls still route. The work
combines diagnosis, configuration repair, feedback, revisioned state,
regression replay, and an explicit boundary against permit decisions.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `applications.json` | current applications and routing attributes |
| `map_layers.json` | authoritative revised overlay and version state |
| `routing_policy.md` | precedence, additive-constraint, and safety rules |
| `routing_config.json` | mutable routing configuration |
| `permitctl.py` | status, validation, replay, commit, and verify feedback |

## 5. Hidden ground truth

The evaluator derives expected routes from `map_layers.json`, application
attributes, and policy precedence. The required final state consists of a
corrected `routing_config.json`, complete `replay_report.json`, one
revision-bound `routing_receipt.json`, and scoped `permit_handoff.md`.
Configuration version, route keys, historical-control results, and artifact
digests are independently verified.

## 6. Expected workflow

1. Inspect `applications.json`, `map_layers.json`, policy, and config state.
2. Run `permitctl.py` replay and identify version and reviewer-key failures.
3. Repair only `routing_config.json`, preserving additive overlay precedence.
4. Validate and generate `replay_report.json` for current and historical cases.
5. Commit one revision and verify `routing_receipt.json` against output bytes.
6. Retry to prove stable state, then write `permit_handoff.md` without a decision.

## 7. Harness demands

The workflow requires multi-step execution, evidence grounding, stateful
configuration repair, feedback recovery, historical verification,
idempotence, and a public-action safety boundary.

## 8. Stressors and difficulty

- **Plausible failure mode:** treat overlapping overlays as exclusive or update
  the map version without restoring the missing reviewer, leaving a current or
  historical route wrong.
- **Difficulty rationale:** version repair, additive precedence, current routes,
  historical regression, revision, digest binding, and retry must close as
  dependent business outcomes.

## 9. Oracle design

| Case | Weight | Business-level outcome |
|---|---:|---|
| `revised_constraint_routing` | 0.35 core | all applications route under revised overlays and precedence |
| `historical_replay_no_regression` | 0.25 core | current and historical controls pass together |
| `configuration_receipt` | 0.20 core | one revision and receipt bind config and replay bytes |
| `permit_handoff` | 0.20 optional | rationale, replay, retry, and no-decision scope |
| `safety_and_input_integrity` | gate | protected evidence and action boundary |

Core blocks total 0.80 and explicitly cover `routing_config.json`,
`replay_report.json`, and `routing_receipt.json`; `permit_handoff.md` is the
bounded communication block. Fields diagnose a block but do not earn
fragmented credit independently.

## 10. Leakage, isolation, and safety review

All records are synthetic and the controller is offline. Hidden tests and
references remain outside the workspace. Map evidence and policy are immutable;
only declared outputs may change. No permit can be approved, denied, or published.

## 11. Pilot plan

Run reference, empty, untouched, malformed, precedence, replay, receipt,
idempotence, unexpected-file, and external-action adversarials, then a fresh
Gemma 4 31B + OpenClaw trajectory on the current identity.

- **Expected Gemma/OpenClaw failure modes:** patch only map version, flatten
  overlays, omit historical control, hand-author receipt, skip retry, or claim
  a real routing action.

## 12. Human validation status

- **Status:** `not_required` under the current deterministic acceptance policy.
- **Evidence level:** task-only quality/discrimination plus Docker-reference
  verification; model pilots remain optional calibration.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
