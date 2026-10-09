# Task Design: `096-pod-config-secret-diagnosis`

## 1. Workflow identity

- **Domain / role:** IT Operations; Kubernetes application support engineer.
- **Trigger:** A current rollout is stalled across secret synchronization, startup configuration, readiness, and Service routing while the incident record also contains healthy evidence from older generations.
- **Objective:** Capture the failing before-state, diagnose the four-layer causal sequence, make only the four policy-allowed field changes, and reproduce readiness/routing in an offline simulator.
- **Consequence:** Fixing only one symptom leaves the application unavailable; broad manifest edits introduce unreviewed risk.

## 2. Idea provenance

- **Source:** [Kubernetes debugging applications](https://kubernetes.io/docs/tasks/debug/debug-application/); source ID IT-01.
- **Origin class:** public_workflow_adaptation.
- **Synthetic-data statement:** Cluster names, images, events, secrets, and logs are synthetic.
- **Adaptation:** The incident uses realistic Deployment/Service manifests, ordered events, a name-only secret inventory, application logs, and a deterministic local cluster controller.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Operators correlate events, resource references, application listeners, selectors, and probes; patch only mismatched fields; reconcile observed state; and record a rollback without exposing secret values or claiming unsupported production action.

## 4. Agent-visible inputs

| Input | Authority |
|---|---|
| `incident_policy.md` | Governs source precedence, minimal change, secret handling, and rollback. |
| `cluster/external_secret.json`, `cluster/deployment.json`, `cluster/service.json` | Mutable provider sync, workload, probe, and routing manifests. |
| `secret_inventory.json`, `config_inventory.json`, `image_contract.json` | Current names/keys, configuration versions, and approved listener/readiness contract; no secret values. |
| `rollout_history.json`, `incident_events.jsonl`, `application.log` | Generation-aware history, ordered symptoms, and current process evidence. |
| `tools/clusterctl.py` | Protected reconciliation and verification simulator. |

## 5. Hidden ground truth

The agent-visible `incident_policy.md` and generation-aware records determine required final workspace state in `cluster/deployment.json`, `cluster/service.json`, `cluster/external_secret.json`, `cluster/before_state.json`, `cluster/observed_state.json`, and `repair_handoff.md`. Before mutation, `observe` must capture blocked remote secret version/property, stale ConfigMap port 8080, `/ready` failure, HTTP-named routing failure, zero ready replicas, and a failed smoke result. The minimal repair changes exactly five leaf fields across four repair groups: ExternalSecret remote version to `3` and property to `database_url`, Deployment HTTP_PORT ConfigMap to `invoice-api-config-v2`, readiness path to `/health/ready`, and Service targetPort to named port `web`. Reconcile/verify must derive three ready replicas, ready endpoints, and HTTP 200 while every other parsed manifest field remains exact.

## 6. Expected workflow

1. Read `incident_policy.md`, both cluster manifests, `secret_inventory.json`, `incident_events.jsonl`, and `application.log`.
2. Separate the FailedMount event state from the later routing symptom and map each to its authoritative record.
3. Apply only the two ExternalSecret remoteRef fields, Deployment ConfigMap name/readiness path, and Service targetPort allowed by policy.
4. Run `tools/clusterctl.py reconcile` and `verify` to create and validate `cluster/observed_state.json`.
5. Document evidence, preserved fields, rollback, and the no-live-cluster boundary in `repair_handoff.md`.

## 7. Harness demands

The task requires evidence grounding across multiple operational artifacts, JSON configuration edits, local tool execution, multi-step verification, and minimal state mutation.

## 8. Stressors and difficulty

- **Plausible failure mode:** The agent fixes only the missing secret, changes the container port instead of Service targetPort, invents secret values, broad-edits selectors/probes, or claims a live rollout.
- **Difficulty rationale:** Four faults occur in causal order and some healthy observations belong to older generations. Fixing an upstream layer reveals the next one, while secret values remain unavailable and all non-allowlisted manifest fields—including strategy, image, labels, selectors, and probe strength—must remain exact.

## 9. Oracle design

Core cases total 0.80 across the layered repairs in `cluster/deployment.json`, `cluster/service.json`, and `cluster/external_secret.json`, executable before/after evidence in `cluster/before_state.json` and `cluster/observed_state.json`, and minimality. The required `repair_handoff.md` scores chronology and rollback. The shared artifact contract covers all six paths; a hard gate protects evidence/simulator, rejects secret leakage, and rejects live-action claims. Empty, untouched, malformed, and reference trials score 0/0/0/1.

## 10. Leakage, isolation, and safety review

No real cluster, network, or credential exists. Secret inventory contains names and key names only. The mutation contract limits edits to the three manifests plus creation of before/observed state and handoff. The grader independently reruns the simulator.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Fixing only one fault, editing the wrong port field, leaking or inventing secret values, failing to rerun reconciliation, or omitting rollback and offline scope.
- **Expected strong-harness success band:** To be calibrated from repeated post-review pilots; runs remain diagnostic only.
- **Revision rule:** Revise only for reproducible package, specification, simulator, or oracle defects and never use candidate performance as selection evidence.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
