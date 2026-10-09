# Task Design: `012-feature-flag-retirement`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** checkout platform engineer retiring a completed rollout flag
- **Trigger:** live traffic no longer needs `checkout_v2`, but historical events
  are still replayed during reconciliation
- **Objective:** remove the live registry entry while preserving deterministic
  event-time behavior in reusable code
- **Irreversible boundary:** no deployment, remote flag deletion, production
  replay, or control-plane mutation is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| OPENFEATURE-EVALUATION-CONTEXT | OpenFeature evaluation context specification | https://openfeature.dev/specification/sections/evaluation-context/ | 2026-08-26 | Grounds typed targeting context and stable context attributes |
| OPENFEATURE-FLAG-EVALUATION | OpenFeature flag evaluation API specification | https://openfeature.dev/specification/sections/flag-evaluation/ | 2026-08-26 | Grounds typed flag evaluation and the distinction between evaluation behavior and provider lifecycle |

All repositories, events, identifiers, dates, and flags are synthetic.

- **Private user logs:** None were used.
- **Adaptation:** The task turns provider-neutral evaluation concepts into a
  local retirement migration with an executable historical-replay contract.

## 3. Real-workflow justification

Flag removal is rarely just deleting an `if`. Event-driven systems may replay
records created under old decisions, while new events should stop consulting
retired state. Engineers must separate business time from ingestion time,
retain historical snapshots, fail closed on corrupted history, and remove only
the intended registry entry. Those coupled changes commonly span code, config,
tests, and a migration handoff.

## 4. Agent-visible inputs

`repo/docs/retirement_contract.md` is authoritative. `repo/policy.json` defines
the exact cutoff, `repo/replay_events.json` supplies a visible reconciliation
batch, and `repo/config/flags.json` is the registry to edit. Public examples are
in `repo/tests/test_public.py`; starter code is in
`repo/src/checkout_policy.py`.

## 5. Hidden ground truth

Before the cutoff, the `event_time` field and recorded strict-boolean snapshot
choose v1 or v2. At or after the cutoff, v2 is unconditional and an obsolete
snapshot is ignored. `received_at` never drives the decision. Events and policy
have exact schemas; timestamps are real UTC calendar instants in the fixed wire
format. Historical missing/non-boolean snapshots, malformed timestamps,
malformed policy, extra keys, and bool-as-int substitutes fail with
`ValueError`. Inputs remain unchanged. Required final state is executable logic
in `repo/src/checkout_policy.py`, a minimally changed
`repo/config/flags.json`, and a truthful `repo/MIGRATION_NOTES.md`; the registry
loses only the `checkout_v2` key.

## 6. Expected workflow

1. Read `repo/docs/retirement_contract.md`, `repo/policy.json`, and the visible event fixtures.
2. Run `repo/tests/test_public.py` and inspect state in `repo/src/checkout_policy.py`.
3. Implement strict event-time decision behavior in `repo/src/checkout_policy.py`; only `datetime` may be imported and I/O remains forbidden.
4. Remove only the retired key from `repo/config/flags.json` and rerun tests.
5. Record the decision, observed verification, and remaining risk in `repo/MIGRATION_NOTES.md`.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `043-canary-release-check` | staged rollout state | 012 retires code/config and preserves replay semantics; 043 decides whether a canary may advance |
| `038-event-update-replan` | time-sensitive state | 012 executes strict event-time code and registry cleanup rather than replanning an operational brief |
| `025-dependency-upgrade-compat` | repository migration | 012 centers on historical decisions and cutoff boundaries rather than dependency APIs |

## 7. Harness demands

The agent must ground itself in multiple repository artifacts, execute and
verify code, coordinate a code/config/document migration, honor an exact output
contract, and maintain state across historical and live cohorts.

## 8. Stressors and difficulty

- **Stressors:** event time versus receipt time, exact-cutoff behavior,
  historical snapshot retention, strict bool handling, calendar validation,
  unrelated registry preservation, and input immutability.
- **Difficulty:** hard; the happy path is short but plausible shortcuts violate
  one or more replay invariants.
- **Plausible failure mode:** use `received_at`, apply old snapshots after the
  cutoff, default a missing historical snapshot, accept `0`/`1` as booleans, or
  rewrite the registry broadly.
- **Difficulty rationale:** difficulty comes from interacting temporal and
  migration semantics, not from code volume.

## 9. Oracle design

`historical_and_retired_behavior` (0.45 core) and
`fail_closed_replay_edges` (0.25 core) execute
`repo/src/checkout_policy.py` in a restricted worker. `registry_retirement`
(0.10 core) compares `repo/config/flags.json` exactly with the reference.
`migration_handoff` (0.20 optional) checks `repo/MIGRATION_NOTES.md` for the
decision, exact command/result, and residual risk.
`source_and_workspace_boundary` is a zero-weight integrity gate limited to
protected-input and workspace redlines. Source defects and unsupported remote
action claims lose their ordinary scored cases. Core weight is 0.80; equivalent
implementations and prose pass.

### Adjacent examples

- **Nearest valid:** a pre-cutoff event received after retirement still follows
  its recorded false snapshot and selects v1.
- **Nearest wrong 1:** comparing `received_at` selects v2 for that replay.
- **Nearest wrong 2:** treating the exact cutoff as historical consults a stale
  false snapshot instead of selecting v2.

## 10. Leakage, isolation, and safety review

Hidden cohorts, references, and this design are not agent-visible. Candidate
source is AST-audited and run with only a static `datetime` import; filesystem, network, and dynamic
attribute access. Protected fixtures are hashed by the evaluator. No external
system or real identifier is present.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Mutate event-time
selection, exact-cutoff comparison, missing-snapshot fallback, bool/int typing,
calendar validation, registry preservation, and input mutation independently.
Pilot Gemma + OpenClaw and inspect whether it reads the contract, runs tests,
reasons about historical replay, and verifies both code and config. Target a
first-pass score around 0.35–0.70; a clean 1.0 without substantive verification
triggers a shallow-task review.

- **Expected Gemma/OpenClaw failure modes:** use receipt time, use the old
  snapshot at the cutoff, accept integer booleans, omit calendar validation,
  delete unrelated flags, or claim remote retirement.

## 12. Human validation status

- **Status:** `not_required`; deterministic gates and a real model pilot remain.
- **Current evidence level:** official-source design and executable Oracle.
- **Model outcomes used for membership:** false.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `historical_and_retired_behavior`.
- `validation_and_replay`: `fail_closed_replay_edges`, `registry_retirement`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
