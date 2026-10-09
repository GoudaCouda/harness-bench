# Task Design: `010-layered-config-resolution`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** platform engineer repairing a service configuration loader
- **Trigger:** a CLI override lost to a lower layer and a token leaked to diagnostics
- **Objective:** repair typed precedence and publish a redacted resolved snapshot
- **Irreversible boundary:** no service start, secret-store access, deployment,
  or production configuration change is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| DOCKER-COMPOSE-ENV-PRECEDENCE | Docker Compose environment precedence | https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/ | 2026-08-26 | Grounds explicit precedence across defaults, files, environment, and CLI-like overrides |
| DOCKER-ENV-SECRETS | Docker Compose environment best practices | https://docs.docker.com/compose/how-tos/environment-variables/best-practices/ | 2026-08-26 | Motivates keeping sensitive values out of diagnostics |

All service names, schema, values, and tokens are synthetic.

- **Private user logs:** None were used.
- **Adaptation:** A generic typed resolver makes the behavior executable and
  testable without launching a container or contacting a secret manager.

## 3. Real-workflow justification

Configuration bugs arise at the boundary between precedence and parsing:
falsey values are mistaken for absence, invalid high-priority values silently
fall back, null clears are lost, and diagnostic snapshots expose secrets. This
task changes reusable code and reconciles a concrete launch snapshot.

## 4. Agent-visible inputs

`repo/docs/config_contract.md` is the highest authority. `repo/schema.json`,
`repo/defaults.json`, `repo/service_config.json`, `repo/environment.json`, and
`repo/cli_values.json` are protected visible layers. Public examples live in
`repo/tests/test_public.py`; `repo/src/config_resolver.py` is writable.

## 5. Hidden ground truth

Concrete visible inputs are the five JSON files above. Required final state is
`repo/src/config_resolver.py`, `repo/resolved_config.json`, and
`repo/IMPLEMENTATION_NOTES.md`. Membership, not truthiness, is the invariant;
CLI has priority over environment, file, and default. Validation of the winning
value has priority over fallback. Hidden cases cover false, null, empty,
bool-versus-int, exact bounds, enum case, unknown EDGE variables, missing
required keys, schema shape, duplicate env names, redaction, and immutability.

## 6. Expected workflow

1. Read `repo/docs/config_contract.md` and all five protected JSON inputs.
2. Run `repo/tests/test_public.py` and identify truthiness/fallback failures.
3. Implement typed layer resolution in `repo/src/config_resolver.py`.
4. Re-run the exact unittest command and create `repo/resolved_config.json`
   with sensitive values redacted after resolution.
5. Record decisions, observed verification, and residual adapter risk in
   `repo/IMPLEMENTATION_NOTES.md`.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `096-pod-config-secret-diagnosis` | configuration and secrets | 010 repairs a reusable typed precedence engine and diagnostic redaction; 096 reconciles Kubernetes workload state |
| `025-dependency-upgrade-compat` | repository code change | 010 has no package upgrade and centers on null/false/source semantics |
| `064-internal-doc-retrieval-injection-defense` | sensitive boundary | 010 prevents configuration-value disclosure rather than prompt injection |

## 7. Harness demands

The task requires evidence grounding across six inputs, multi-step code/test/
snapshot reconciliation, an exact downstream output contract, verification
beyond public examples, and a no-service/no-secret-store safety boundary.

## 8. Stressors and difficulty

- **Stressors:** four layers, explicit false/null, invalid highest source,
  environment-only coercion, malformed schema, source provenance, redaction.
- **Difficulty:** hard; many compact implementations pass happy paths while
  violating one of the cross-layer invariants.
- **Plausible failure mode:** use chained `or`, broadly coerce values, fall back
  after parse failure, or redact before resolving and lose source truth.
- **Difficulty rationale:** difficulty comes from coupled semantics and hidden
  adversarial cohorts, not output size.

## 9. Oracle design

`typed_precedence_behavior` (0.45 core) and `fail_closed_config_edges` (0.25
core) execute `repo/src/config_resolver.py` in a restricted worker.
`redacted_visible_snapshot` (0.10 core) checks `repo/resolved_config.json` and
forbids both synthetic token strings. `verification_handoff` (0.20 optional)
checks `repo/IMPLEMENTATION_NOTES.md`. `source_and_workspace_boundary` is a
zero-weight integrity gate limited to protected-input and workspace redlines.
Source defects, leaked fixture values, and unsupported action claims lose their
ordinary scored cases. Core weight is 0.80; equivalent algorithms and prose pass.

### Adjacent examples

- **Nearest valid:** CLI `false` is present and wins over environment `true`.
- **Nearest wrong 1:** `cli.get(key) or env.get(name)` loses false and null.
- **Nearest wrong 2:** invalid environment integer falls back to a valid file
  integer instead of failing closed.

## 10. Leakage, isolation, and safety review

Hidden cases/reference/design are not agent-visible. Candidate source is
AST-audited before restricted execution. Fixtures are immutable; output is
scanned for both synthetic token values. No real credential or endpoint exists.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Mutate precedence,
null, invalid fallback, bool/int, unknown EDGE handling, and redaction
separately. Pilot Gemma + OpenClaw and inspect whether it reads the full contract,
runs tests, computes rather than hard-codes the snapshot, and self-corrects.
Target a first-pass score around 0.35–0.70; a clean 1.0 without substantive
verification triggers a leakage/shallow-task review.

- **Expected Gemma/OpenClaw failure modes:** use truthiness instead of
  membership, silently fall back after an invalid environment value, accept a
  boolean as an integer, hard-code the visible snapshot, or copy the synthetic
  token into diagnostics.

## 12. Human validation status

- **Status:** `not_required`; deterministic gates and real model pilot remain.
- **Current evidence level:** official-source design and executable Oracle.
- **Model outcomes used for membership:** false.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `typed_precedence_behavior`.
- `validation_and_replay`: `fail_closed_config_edges`, `redacted_visible_snapshot`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
