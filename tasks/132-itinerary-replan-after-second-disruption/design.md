# Task Design: `132-itinerary-replan-after-second-disruption`

## 1. Workflow identity

- **Domain / role:** personal travel operations coordinator.
- **Trigger:** a second flight disruption invalidates one leg of a reviewed,
  unexecuted trip while replacement inventory and dependent updates arrive.
- **Objective:** recover an interrupted local journal, select the feasible
  minimum-change/lowest-cost option, preserve valid objects, and stage an
  auditable proposal without making an external reservation or refund request.
- **Consequence:** a wrong connection, visa, bag, accessibility, or local-time
  decision can strand the traveler; over-broad changes can discard valid holds.

## 2. Idea provenance

The workflow adapts concepts from IATA NDC offer/order exchange, Timatic-style
travel-document constraints, RFC 5545 calendar handoffs, and SQLite transaction
recovery. All people, IDs, routes, prices, signatures, keys, inventories, and
events are synthetic. No private user logs or live booking systems are used.

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| RFC5545 | IETF RFC 5545 | https://www.rfc-editor.org/rfc/rfc5545 | Tentative offline calendar artifact semantics. |
| SQLITE-TRANSACTIONS | SQLite transaction documentation | https://www.sqlite.org/lang_transaction.html | Atomic local apply and interrupted-journal recovery pattern. |
The source-to-task adaptation turns those public workflow concepts into a
deterministic offline recovery state machine; no source provides its answer.

- **Adaptation:** IATA offer exchange, travel-document checks, RFC 5545 handoff,
  and SQLite recovery are combined into a second-disruption itinerary state
  machine with synthetic signed inventory and an interrupted proposal journal.
- **Synthetic-data statement:** all scenario records, signatures, keys, IDs,
  prices, schedules, and traveler constraints are synthetic.
- **Private user logs:** not used.

## 3. Real-workflow justification

The workspace contains an explicit policy and plan schema, a signed/ETagged
inventory snapshot and trust material, an out-of-order JSONL delivery stream,
and a SQLite reviewed checkpoint with a partially applied earlier journal.
`tripctl.py inspect/query` exposes operational state; `preview` validates a
caller-authored outcome rather than accepting plausible labels. The manifest protects
source evidence. Hidden tests and reference artifacts are never copied into the
agent workspace.

## 4. Agent-visible inputs

1. Inspect controller output, source policy/evidence, and SQLite tables.
2. Validate snapshot authority and expiry; deduplicate the at-least-once stream.
3. Normalize offset-aware timestamps and test every option's connection,
   continuity, curfew, check-in/rest, shuttle, visa, baggage, and accessibility.
4. Apply the lexicographic minimum-change, then cost objective. A cheaper fully
   feasible option deliberately loses because it replaces both reviewed legs.
5. Encode all option assessments and all object deltas with local evidence.
6. Use controller feedback to correct adjacent infeasible choices.
7. Recover the partial journal, atomically commit the local proposal, verify the
   independent state, stage local tokens/ICS, and prove semantic replay.

Later actions depend on observations made earlier; this is not a static form.

## 5. Hidden ground truth

The public controller performs candidate-first object/field validation over
supplied policy, inventory segments, events, and database rows. It exports no
callable complete-plan constructor, and errors disclose no expected values.
The source checkpoint binds immutable-source hashes, restored baseline rows, and
source revision. The semantic plan digest sorts unordered collections. Equivalent
JSON/order replay is byte-stable; a conflicting plan under the committed identity
is rejected before mutation. Apply uses an immediate SQLite transaction and
rolls back the prior interrupted journal before projecting the current plan.
The required final workspace state includes a validated `replan_plan.json`, an
exact staged `state/travel.db`, and hash-bound verification, receipt, replay,
tentative calendar, and handoff artifacts for the stable recovery identity.

## 6. Expected workflow

`tests/test_outcome.py` independently parses sources, verifies signatures,
reconstructs the baseline, derives option feasibility and the lexicographic
choice, checks the candidate SQLite/journal/run state, and closes receipt,
verification, ICS, replay, provenance, and safety. It does not import or execute
`tripctl.py`. Candidate-authored content is parsed only as bounded data.

Deterministic core blocks total 0.80: source/event authority (0.08), per-option
assessments (0.20), feasibility/objective selection (0.12), per-object plan plus
SQLite projection (0.20), and interrupted-journal commit recovery (0.20).
Failure details retain the exact option/object IDs rather than hiding them behind
one whole-workflow mismatch. Deterministic closure is 0.12. A bounded semantic
fallback worth at most 0.08 assesses the reviewer handoff only after structured eligibility.
Source mutation, unsafe filesystem nodes, or external-action claims are a gate.

1. Inspect `policy/replan_policy.json`, signed inventory, JSONL events, and `state/travel.db`, then create `replan_plan.json`.
2. Preview and repair `replan_plan.json`, apply it to recover the old journal state, and commit only the exact local SQLite proposal projection.
3. Verify, stage `state/stage_receipt.json` and `itinerary.ics`, replay the semantic plan state, and close with `replan_handoff.md`.

## 7. Harness demands

Contracts cover reference 1.0/determinism, empty/pristine/malformed candidates,
source mutation, external-action claims, key neighboring feasibility errors,
time-zone and minimum-change/cost errors, duplicate events, interrupted journal
recovery, DB tampering, stale receipts, equivalent replay, conflict rejection,
changed-seed derivation, evaluator independence, case weights, and semantic input.

## 8. Stressors and difficulty

No network, account, credential, live inventory, payment, booking, cancellation,
refund, or messaging is required. The controller stages only local proposal
tokens and a tentative calendar. The oracle establishes package feasibility,
not model success.

- **Plausible failure mode:** compare local clock strings without offsets,
  choose cheaper O-H despite replacing a valid leg, apply DLV-02 twice, or
  overwrite preserved hotel/event state.
- **Difficulty rationale:** signature and stream authority, multi-option temporal
  constraints, lexicographic optimization, transactional journal recovery, and
  cross-artifact replay must all agree.

## 9. Oracle design

The oracle explicitly covers `replan_plan.json`, `.trip_preview.json`,
`state/travel.db`, `state/verification.json`, `state/stage_receipt.json`,
`state/replay_report.json`, `itinerary.ics`, and `replan_handoff.md`. Five
deterministic core cases total 0.80; closure is 0.12 and bounded handoff semantics
is at most 0.08. The reference scores 1.0; empty, pristine, and malformed
workspaces score 0.0.

```yaml
task_key: harnessbench::132-itinerary-replan-after-second-disruption
evidence_mode: full_package
capability_signature:
  domains: [personal_assistance, travel_operations]
  tools: [python_cli, sqlite, json, rfc5545]
  behaviors: [inspect, reconcile, optimize, recover, stage, verify, replay]
  fault_or_initial_state: cancelled reviewed leg, duplicate events, interrupted local journal
  expected_final_state: exact local proposal projection with staged holds/requests
judgement:
  terminal_transfer: strong
  terminal_agency: strong
  diagnosis_recovery: strong
  moderate_complexity: strong
  verifiability: strong
  spec_feasibility: likely
  novelty: strong
decision: priority
confidence: high
reasons:
  - Later choices depend on signature, stream, database, and preview observations.
  - Constraint reasoning and transactional recovery transfer beyond travel tasks.
risks:
  - Dense temporal evidence requires careful UTC-offset comparisons.
missing_evidence:
  - Real Gemma/OpenClaw calibration remains pending.
```

## 10. Leakage, isolation, and safety review

Maintainer rebuilt; independent human domain/oracle sign-off remains pending.

The network is unnecessary and disabled by task contract. Tests and references
remain outside the copied workspace. Candidate-authored files are bounded data;
the evaluator rejects symlinks, special nodes, source mutation, and affirmative
claims of live booking, cancellation, refund, payment, purchase, or messaging.

## 11. Pilot plan

After static acceptance, run a fresh Gemma 4 31B plus OpenClaw trajectory. Audit
inspection depth, first-write timing, preview failures, repair behavior, full
controller sequence, input integrity, tool-call diversity, and semantic replay.
Treat any runner or semantic-input-builder crash as infrastructure diagnostic,
not candidate evidence. Revise if failures come from undocumented representation
choices; retain difficulty that comes from published state and constraints.

- **Expected Gemma/OpenClaw failure modes:** shallow inventory reading,
  UTC-offset mistakes, choosing cost before minimum change, missing a duplicate
  delivery, failing to restore the journal, stale stage hashes, or a runner
  semantic-input-builder failure after candidate completion.

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

- `decision_and_state`: `source_and_event_authority`, `option_assessments`, `minimum_change_then_cost_objective`.
- `validation_and_replay`: `object_decisions_and_projection`, `interrupted_journal_and_commit`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
