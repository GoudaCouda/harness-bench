# Task Design: `207-water-main-isolation-recovery`

## 1. Workflow identity

- **Canonical domain:** Business Operations
- **Operational subdomain:** municipal water distribution control
- **Role:** distribution-control planner recovering an interrupted offline
  valve-isolation projection.
- **Trigger:** an at-least-once telemetry batch arrived while a prior worker had
  changed one local valve projection but not closed its before-image journal.
- **Objective:** resolve telemetry authority, choose the safe minimum-impact
  isolation boundary, recover the partial transaction, commit and verify a
  complete local projection, and stage a hash-bound review packet.
- **Consequence:** accepting a stuck valve, crossing a maintenance lock, or
  isolating a hospital feed makes a field plan unsafe; treating a planning
  projection as a physical operation also crosses the authority boundary.
- **Task family:** `municipal-water-isolation-recovery`.

## 2. Idea provenance

| Source ID | Public source | Use |
|---|---|---|
| `EPA-AWIA-EMERGENCY-RESPONSE` | EPA America's Water Infrastructure Act emergency-response resources, https://www.epa.gov/waterresilience | motivates consequence-aware utility response planning and protected critical service |
| `AWWA-WATER-AUDITS` | AWWA water-system operations and auditing resources, https://www.awwa.org/ | motivates controlled asset identity, valve condition, and reviewable distribution decisions |
| `SQLITE-TRANSACTIONS` | SQLite transaction documentation, https://sqlite.org/lang_transaction.html | supports guarded local transaction recovery and replay |

- **Synthetic-data statement:** All utilities, assets, zones, telemetry,
  timestamps, work orders, and people are synthetic.
- **Private user logs:** Not used.

Public concepts are adapted into an offline deterministic exercise; cited
sources do not contain fixture answers.

- **Adaptation:** `207-water-main-isolation-recovery` transforms public water
  resilience, asset-control, and transaction-safety concepts into a synthetic
  municipal-water isolation recovery with dirty telemetry, constrained
  boundary selection, an interrupted SQLite journal, and local-only staging.

## 3. Real-workflow justification

Water-distribution planners use valve condition, protected locks, customer
impact, and critical-service continuity to prepare isolation boundaries before
field authorization. This task preserves that dependency chain in a bounded
digital twin: terminal observations change which graph boundary is admissible,
and a durable recovery transaction must close before a review packet can be
trusted.

### 3.1 Task-only selection audit

```yaml
task_key: self_created::207-water-main-isolation-recovery
evidence_mode: full_package
capability_signature:
  domains: [municipal_water, infrastructure_operations, safety_planning]
  tools: [python_cli, sqlite, jsonl, sha256, filesystem]
  behaviors:
    - inspect protected state before acting
    - reconcile dirty at-least-once telemetry
    - solve constrained minimum-impact boundary selection
    - diagnose and restore an interrupted journal
    - repair a plan from object-specific preview feedback
    - commit and independently verify one local transaction
    - stage hash-bound artifacts and prove semantic replay
  fault_or_initial_state: conflicting telemetry plus an open V-04 before-image journal and partial projection
  expected_final_state: restored journal, seven coherent projections, verified offline packet, byte-stable replay
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
  - Later choices depend on SQLite inspection, event identity and sequence diagnostics, valve availability, lock state, critical-service impact, and executable preview feedback.
  - The controller derives outcomes from general public rules and visible rows; it contains no literal valve-to-final-answer map.
  - The evaluator does not import or execute the controller and separately checks semantic artifacts, durable mutation, protected source facts, hashes, and replay.
risks:
  - Operational vocabulary is exact, so preview reports mismatches by concrete valve or delivery instead of forcing hidden-string guessing.
  - The scenario is safety-critical, so all effects are local and synthetic and external or physical execution claims are gated.
missing_evidence: []
```

### 3.2 Historical replacement and Standard207 reactivation

The water-isolation package originally replaced a static shopping-dispute
exercise. Standard207 now reactivates the reviewed water workflow under the new
identity `207`; no historical score or release identity is carried forward.
Its graph constraints, telemetry authority, durable recovery, and protected
physical-action boundary remain independently executable and graded.

### 3.3 Novelty against Standard200 and the other long-horizon additions

The active Standard200 contains laboratory, healthcare, infrastructure, and
state-recovery work, while additions 202--206 cover metering, cold chain, EDI,
field service, and engineering change. Task 207 is distinct: it selects among
competing graph boundaries where alternatives can be defeated by current
operability, maintenance locks, or critical-service impact. Physical-position
immutability, valve projection, utility review packets, and telemetry collision
authority are independently graded rather than inherited from a generic event
replay template.

## 4. Agent-visible inputs

| Asset | Purpose |
|---|---|
| `waterctl.py` | guarded inspect/query/preview/apply/verify/stage/replay interface |
| `state/network.db` | work order, valve sources, candidate boundaries, memberships, mutable projections, and interrupted journal |
| `policy/isolation_policy.json` | admissibility, selection, precedence, event, and external-action rules |
| `policy/source_manifest.json` | hashes of policy and telemetry inputs |
| `evidence/telemetry_events.jsonl` | accepted observations, exact redeliveries, two collision kinds, stale/protected/unknown traffic |

The controller groups deliveries by event body excluding delivery identity,
then by valve/source sequence. Accepted observations override base operability
only for validation. It checks the submitted boundary against database
membership and current operability, unavailable, locked, and critical-outage
constraints, and the minimum affected-connections/ID rule. It never returns a
complete target plan or complete decision list. A seed mutation to V-02's
delivered observation makes the former B-B candidate fail preview because B-A
becomes the selected 120-connection boundary, proving the validator follows
source state rather than a fixture answer map.

The package is offline, credential-free, standard-library-only, and owned by
UID/GID 1000 in the pinned Python environment.

## 5. Hidden ground truth

The hidden reference builder constructs a complete candidate from the visible
source rows in `state/network.db` and `evidence/telemetry_events.jsonl`, then
exercises the public constraint validator and guarded
workflow in an isolated copy. Frozen truth contains the normalized plan and
protected valve source projection. Required final state includes
`isolation_recovery_plan.json`, a closed J-INT-V04 journal in
`state/network.db`, and a hash-bound `staging/isolation_review_packet.json`.
The stable `recovery_id + source_checkpoint` key and semantic-plan digest are
the replay invariant. Neither hidden builder nor reference output is copied
into the agent workspace. The independent evaluator uses frozen truth plus its
own JSON, SQLite, permission, and hash checks.

## 6. Expected workflow

1. `inspect` computes a checkpoint over source hashes and protected SQLite
   fields and exposes the open journal and bounded query table list.
2. `query` exposes real rows without allowing arbitrary SQL.
3. `preview` validates exact schemas, source identity, every valve and delivery,
   and impact totals; failures are keyed by object and field and do not mutate
   SQLite.
4. `apply` rejects a stale checkpoint or conflicting recovery identity before
   `BEGIN IMMEDIATE`, restores J-INT-V04, removes its partial projection, closes
   the old run, and atomically records seven current projections.
5. `verify` reopens SQLite and checks checkpoint, journal, run, semantic digest,
   projection rows, and unchanged physical positions.
6. `stage` requires verification and the human handoff, then writes a local
   review packet and SHA-256 manifest.
7. `replay` accepts row/set reordering and formatting as a semantic no-op; a
   changed meaning conflicts and a changed checkpoint is stale.

## 7. Harness demands

| Demand | Concrete use |
|---|---|
| evidence grounding | valve sources, dirty telemetry, memberships, impact and policy jointly control the plan |
| tool selection | bounded controller queries, JSONL inspection, SQLite and hashes provide distinct evidence |
| multi-step execution | preview repair, atomic apply, verify, handoff, stage and replay depend on prior state |
| state management | interrupted/current runs, journal, seven projections and packet identities must agree |
| error recovery | V-04's real before-image must close before the new batch commits |
| verification behavior | closure requires reopened database state, hashes and semantic replay |
| safety boundary | only local desired positions change; physical/external action remains prohibited |

## 8. Stressors and difficulty

Difficulty comes from dependent state rather than volume: two collision kinds,
an exact redelivery, stale/unknown/protected traffic, an accepted observation
that invalidates the otherwise attractive boundary, a lower-impact hospital
boundary that must fail closed, and an interrupted transaction. Likely errors
are attributable by valve, delivery, boundary, or durable-state case. The task
is hard but bounded because all tables and policies are local, queries are
enumerated, and preview identifies the failing object and field.

- **Plausible failure mode:** choose B-D by numeric impact while missing the
  hospital outage, accept one side of an event collision, or commit on top of
  the interrupted V-04 projection.
- **Difficulty rationale:** correct closure depends on event authority,
  constraint-based boundary selection, protected state, atomic recovery,
  independent verification, and replay rather than on file formatting alone.

## 9. Oracle design

The hidden reference builder derives the plan from the visible sources and
runs the guarded workflow in a temporary copy. The evaluator uses frozen truth
and independent SQLite/JSON/hash logic; it never imports, executes, or shells
out to `waterctl.py`.

Deterministic core weight is exactly 0.80:

| Case | Weight | Responsibility |
|---|---:|---|
| boundary selection and valve dispositions | 0.28 | selected boundary, all valves, impact, refs, checkpoint |
| telemetry identity and sequence authority | 0.24 | all eleven delivery dispositions |
| journal atomicity and protected state | 0.28 | before-image, run, projections, local fields |
| packet/hash/verification/replay | 0.12 | deterministic closure enhancement |
| handoff semantics | 0.08 | bounded semantic fallback only |
| safety/input integrity | gate | sources, protected facts, hazardous paths, and external claims; ordinary writable output permissions are diagnostic |

Reference, empty, pristine, malformed, adjacent field errors, database-only
errors, semantic equivalent replay, semantic conflict, stale checkpoint, source
tamper, external-action claims, evaluator independence, and ordinary permission changes are
focused contracts. A failing core block loses only its attributable weight;
the gate forces zero. Prose fallback is capped at 0.08 and cannot rescue any
state or business case.

Artifact coverage is explicit: `isolation_recovery_plan.json` and
`.isolation_preview.json` establish validated intent; `state/network.db`,
`state/recovery_receipt.json`, and `state/verification.json` prove atomic
closure; `isolation_handoff.md` supplies bounded reviewer semantics;
`staging/isolation_review_packet.json` and `staging/packet_manifest.json` bind
the offline packet; and `state/replay_report.json` proves semantic no-op replay.

## 10. Leakage, isolation, and safety review

Only `workspace/` is agent-visible. Tests, frozen truth, and reference outputs
remain grader-only. The public controller contains schemas and general
constraint checks but no callable target/expected/derive-plan function, no
complete decision constructor, and no literal `V-xx -> disposition` or
`delivery -> answer` map. A focused AST contract enforces that boundary.
Sources and controller must remain byte-identical; protected physical
positions, base observations, locks, critical-feed flags, work order, boundary
rows, and memberships are checked independently. Symlinks, special nodes,
protected-source changes, and affirmative physical/external claims fail the
gate; ordinary regular analysis files remain controller-level diagnostics.

## 11. Pilot plan

- **Static package status:** package, task-only oracle, discrimination, design,
  leakage, catalog, lock, and Docker-reference checks pass.
- **Gemma 4 31B + OpenClaw:** pending; no model was started by this isolated
  authoring pass.
- **Expected Gemma/OpenClaw failure modes:** trust the lower numeric impact without
  checking critical service, accept one side of a collision, apply the newest
  delivered row by file order, omit journal restoration, hand-edit SQLite, or
  confuse local desired position with a physical operation.

## 12. Human validation status

- **Status:** `not_required` under the current deterministic acceptance policy.
- **Model calibration:** the pending Gemma/OpenClaw pilot is useful difficulty
  evidence, not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Standard207 long-horizon refactor

The timeout is raised to 7200 seconds so the benchmark measures sustained graph
reasoning, evidence reconciliation, crash recovery, verification, and replay.
That budget does not excuse incomplete work: timeout remains in the denominator.
The task-specific weights emphasize safe boundary selection and durable state;
they are not normalized to the protocol-repair template.
