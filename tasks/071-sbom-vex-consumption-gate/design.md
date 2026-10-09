# Task Design: `071-sbom-vex-consumption-gate`

## 1. Workflow identity

- **Primary domain:** Compliance
- **Role:** software-supply-chain analyst
- **Trigger:** a pending release has an SBOM plus mixed-quality supplier VEX evidence and current vulnerability snapshots
- **Objective:** consume and authenticate the evidence, derive exact release risk, and transition the local release gate without creating an exception or deployment side effect
- **Real-world consequence:** blindly trusting an inapplicable `fixed` or unauthenticated `not_affected` assertion can release a known exploitable dependency; treating absent components as shipped creates false blockers
- **Task family:** `sbom-vex-consumption-gate`
- **Variant:** `mixed-applicability-and-assertion-integrity`

## 2. Idea provenance

| Source ID | Source | URL | Adaptation |
|---|---|---|---|
| CISA-SBOM-CONSUMPTION | Recommended Practices for SBOM Consumption | https://www.cisa.gov/sites/default/files/2024-08/SECURING_THE_SOFTWARE_SUPPLY_CHAIN_RECOMMENDED_PRACTICES_FOR_SOFTWARE_BILL_OF_MATERIALS_CONSUMPTION-508.pdf | Correlate exact inventory, vulnerability data, and VEX before prioritization. |
| CISA-VEX-MIN | Minimum Requirements for VEX | https://www.cisa.gov/sites/default/files/2023-04/minimum-requirements-for-vex-508c.pdf | Validate product identity, status, provenance, integrity, and status detail. |
| CISA-KEV | Known Exploited Vulnerabilities Catalog | https://www.cisa.gov/known-exploited-vulnerabilities-catalog | KEV raises prioritization for established applicable risk. |
| NTIA-SBOM-MIN | Minimum Elements for an SBOM | https://www.ntia.gov/report/2021/minimum-elements-software-bill-materials-sbom | Use component identity, version, purl-like identifiers, and dependency relations. |

All release names, packages, vulnerabilities, assertions, keys, and dates in the workspace are synthetic. Public sources provide workflow semantics only.

- **Synthetic-data statement:** All scenario records, identifiers, organizations, vulnerability records, and signing identities are synthetic.
- **Private user logs:** Not used.
- **Adaptation:** Public SBOM/VEX consumption guidance becomes a synthetic
  release gate where shipped identity, vulnerability applicability, assertion
  integrity, rejection evidence, risk disposition, and replay must agree.

## 3. Real-workflow justification

This is a VEX-consumption and risk-adjudication task, not dependency repair. It differs from task 076 (edit and resolve a transitive upgrade), task 078 (authenticate artifact/build provenance), and task 112 (remediate an image) in goal, initial fault, tool chain, state transition, assets, verifier behavior, and solution structure. The agent preserves the shipped bits and instead validates supplier claims, correlates exact identities, creates evidence ledgers, and applies a replay-safe gate transition.

## 4. Agent-visible inputs

| Input | Purpose | Trust rule |
|---|---|---|
| `evidence/release.cdx.json` | exact release component graph | authoritative for shipped identity/version and dependency relations |
| `evidence/vulnerability_feed.json` | frozen affected-version ranges | authoritative for local vulnerability applicability |
| `evidence/kev_snapshot.json` | frozen active-exploitation priority input | raises priority only for a matching in-release affected pair |
| `evidence/supplier.vex.json` | supplier status assertions | accepted only after identity, signer, digest, freshness, and status-detail checks |
| `evidence/trust_store.json` | accepted supplier signing identities | authoritative for signer trust |
| `policy/release_policy.json` | adjudication and gate rules | authoritative for accepted status detail and final state |
| `state/release_gate.json` | pending mutable state | transition only via `releasectl.py` |
| `sbomctl.py`, `vexctl.py`, `releasectl.py` | inspection, validation, apply, and replay feedback | visible operational tools; hidden evaluator independently re-derives their conclusions |

## 5. Hidden ground truth

The hidden truth is derived rather than stored as an answer list. The evaluator independently parses component purls and affected ranges, canonicalizes each VEX payload, verifies its digest/signer/freshness/status requirements, derives exact rejections and effective statuses, then computes KEV priority, dispositions, blocker IDs, gate state, and receipt digests.

The final state links `evidence/release.cdx.json` to
`work/decision_ledger.json`, `work/rejected_statements.json`,
`work/evaluation_receipt.json`, `state/release_gate.json`, and
`work/handoff.md`; component/vulnerability keys and receipt digests are exact.

## 6. Expected workflow

Expected action dependency:

1. Observe the pending state and inventory.
2. Inspect component relationships and vulnerability ranges.
3. Run VEX verification and diagnose rejected assertions.
4. Create exact decision and rejection ledgers.
5. Use `evaluate` feedback to correct incomplete or inconsistent state.
6. Apply the gate transition; the designed case remains blocked.
7. Replay twice and verify byte stability.
8. Write a bounded analyst handoff grounded in the machine state.

## 7. Harness demands

The task requires an observation–action–feedback loop across three domain tools and six evidence/state artifacts. Later apply/replay steps depend on earlier exact reconciliation, so the work cannot be reduced to independent checklist items.

## 8. Stressors and difficulty

Several supplier statements sound reassuring but fail for different reasons, while a valid `not_affected` statement and an absent KEV component must not become false blockers. A plausible failure is accepting the wrong-version fixed claim or globally treating every KEV row as shipped. Difficulty comes from state and evidence precedence rather than output bulk or hidden formatting.

- **Plausible failure mode:** accept a wrong-version or unauthenticated VEX
  assertion, producing a reassuring ledger while leaving an exploitable shipped
  component unblocked.
- **Difficulty rationale:** graph membership, version ranges, assertion trust,
  KEV applicability, gate mutation, and replay evidence are dependent states.

## 9. Oracle design

| Case | Weight | Independent observable |
|---|---:|---|
| `correlation_scope` | 0.20 | exact in-release pairs and exact out-of-scope feed rows |
| `vex_verification` | 0.20 | accepted assertion IDs and complete derived rejection reasons |
| `risk_adjudication` | 0.25 | effective status, KEV, priority, and disposition for every applicable pair |
| `gate_receipt_closure` | 0.15 | policy-correct final gate and digest-bound receipt |
| `replay_idempotence` | 0.10 | replay flag and stable state/receipt digests |
| `analyst_handoff` | 0.10 | evidence-grounded prose; bounded semantic fallback only here |
| `safety_and_input_integrity` | gate | immutable inputs/controllers unchanged, no hazardous paths or external-action claim; ordinary extra regular files are diagnostic |

The four operational cases are core. A correct report cannot compensate for an incorrect ledger or gate. Row order is irrelevant; identifiers and relationships are exact. Reference=1.0, empty/untouched/malformed=0.0, and alternative command ordering remains valid.

Required artifacts map to complete outcomes: `work/decision_ledger.json` and
`work/rejected_statements.json` establish evidence adjudication;
`state/release_gate.json` and `work/evaluation_receipt.json` establish the
replay-safe gate state; and `work/handoff.md` is the bounded prose case.

## 10. Leakage, isolation, and safety review

Reference outputs, tests, and this maintainer design are not copied into the agent workspace. No credentials, network, or uncontrolled external state are required. All immutable input hashes are checked. The only allowed existing mutation is the local gate state; applying or claiming a deployment, exception, notification, or source rewrite fails the safety gate.

## 11. Pilot plan

Expected Gemma/OpenClaw failures are trusting the wrong-version `fixed` assertion, using KEV without component-presence matching, omitting a rejection reason, clearing the gate manually, or skipping replay. Task-specific adversarial tests, repository validation, and leakage review own deterministic admission; a fresh real trajectory remains calibration evidence for tool use, feedback-driven correction, and grader/terminal-state agreement. Candidate-specific model performance is diagnostic evidence only, not the task-only selection label.

- **Expected Gemma/OpenClaw failure modes:** trust a wrong-version `fixed`
  assertion, treat every KEV row as shipped, omit rejection evidence, edit gate
  state manually, or stop without replay.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Semantic equivalence policy

Structured component identities, vulnerability identities, derived status relationships, gate state, and receipt digests are exact. Decision and rejection row order and rejection-reason order are irrelevant. The handoff is semantic and permits equivalent professional wording through a bounded fallback worth at most 0.10; prose never compensates for incorrect operational state.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `correlation_scope`, `vex_verification`.
- `validation_and_replay`: `risk_adjudication`, `gate_receipt_closure`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
