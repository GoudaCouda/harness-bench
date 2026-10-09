# Task Design: `097-kubernetes-ca-trust-rotation-recovery`

## 1. Workflow identity

- **Primary domain:** IT Operations
- **Role:** cluster-security engineer
- **Trigger:** an HA control-plane root CA rotation stopped after partial server-leaf rotation, a controller-manager bundle-role failure, a stale client, and a rejected premature retirement
- **Objective:** restore the legal trust-migration sequence and prove the cluster at new-CA-only trust
- **Real-world consequence:** removing old trust too early disconnects old-signed endpoints or stale clients, while rolling back new signers extends exposure and complicates recovery
- **Task family:** `kubernetes-ca-trust-rotation-recovery`
- **Variant:** `interrupted-dual-trust-to-new-only`

## 2. Idea provenance

| Source ID | Source | URL | Adapted mechanics |
|---|---|---|---|
| K8S-CA-ROTATION | Manual Rotation of CA Certificates | https://kubernetes.io/docs/tasks/tls/manual-rotation-of-ca-certificates/ | dual trust distribution, rolling client/server updates, verification before old-CA removal, and root/signing file-role distinction |
| K8S-PKI | PKI certificates and requirements | https://kubernetes.io/docs/setup/best-practices/certificates/ | distinct server and client identities across API servers, kubelets, controllers, proxies, and aggregation components |

- **Origin class:** public_workflow_adaptation.
- **Synthetic-data statement:** All cluster IDs, certificates, fingerprints, components, events, and probes are synthetic.
- **Private user logs:** Not used.
- **Adaptation:** Kubernetes CA-rotation guidance becomes a synthetic
  interrupted dual-trust recovery where file roles, stale clients, serving
  leaves, all-pairs probes, retirement, and append-only history must converge.

## 3. Real-workflow justification

Kubernetes CA rotation is a staged trust migration, not a leaf-renewal command. Operators must maintain overlapping trust, keep bundle-capable and single-CA flags distinct, restart lagging clients, roll serving leaves, verify the full connection graph, and only then remove the old anchor. The task differs from nearby certificate, TLS-route, and access-recovery tasks in goal, initial fault, tool chain, assets, transition graph, verifier, and final state.

## 4. Agent-visible inputs

| Input | Authority |
|---|---|
| `evidence/ca_inventory.json` | old/new fingerprints and which paths are bundles, individual CAs, and keys |
| `evidence/component_inventory.json` | required controller, client, server, and handshake identities |
| `evidence/handshake_matrix.json` | deterministic trust-set/server-signer compatibility |
| `policy/rotation_policy.json` | allowed phases, exact file-role constraints, and retirement prerequisites |
| `state/rotation_state.json` | mutable current component state |
| `state/rotation_events.jsonl` | append-only recovery history including rejected prior action |
| `ca_lib.py`, `cactl.py` | protected inspection, mutation, and verification interface |

## 5. Hidden ground truth

The evaluator independently loads immutable identities and trust compatibility. It derives that the controller-manager must retain the dual bundle only for root distribution while its client/signing certificate flags use the individual new CA, `metrics-adapter` must move from old-only to dual trust, `kube-apiserver/cp-3` must move from old to new signer, and a complete dual handshake graph must pass before retirement. Retirement converts every required client/root distribution to new-only. Final verification must bind the exact new-only matrix, final state, policy, inputs, and append-only event prefix.

The final state links `evidence/ca_inventory.json` to
`work/rotation_plan.json`, `state/rotation_state.json`,
`state/rotation_events.jsonl`, `work/dual_probe.json`,
`work/verification.json`, and `work/rotation_handoff.md`; phase, signer, trust,
event, and receipt keys must agree.

## 6. Expected workflow

1. Inspect `state/rotation_state.json`, history, CA-file roles, clients, and pairs.
2. Write dependency-ordered keys to `work/rotation_plan.json` before mutation.
3. Repair controller-manager state while preserving dual root distribution.
4. Refresh the stale client and rotate the old-signed server via `cactl.py`.
5. Generate `work/dual_probe.json` and diagnose every missing or failed pair.
6. Retire the old anchor only after the recorded dual-proof state.
7. Run new-only verification twice and confirm state, history, and receipt stability.
8. Write `work/rotation_handoff.md` without claiming a real cluster change.

## 7. Harness demands

The task requires evidence-grounded diagnosis, tool discovery, dependency-sensitive mutations, protected state transitions, append-only history, all-pairs verification, recovery from a recorded rejected action, and independent final-state checking.

## 8. Stressors and difficulty

Plausible shortcuts include replacing every CA path with the bundle, changing dual distribution to new-only during controller repair, ignoring the stale client, rotating all servers including already-new leaves, using an aggregate success count, or editing the final state by hand. Difficulty comes from coordinating identities and transition prerequisites across feedback-producing tools rather than from output volume.

- **Plausible failure mode:** replace every CA path with a bundle or retire old
  trust before the complete dual probe, breaking signer roles or connectivity.
- **Difficulty rationale:** file-role repair, ordered mutations, all-pairs proof,
  retirement, append-only events, and idempotent verification must all close.

## 9. Oracle design

Core cases total 0.80: legal pre-mutation plan (0.15), controller/stale-client recovery (0.20), remaining server rotation plus complete dual proof (0.20), and old-anchor retirement plus final new-only closure (0.25). The semantic handoff is optional 0.20 with a bounded LLM fallback limited to that case. A zero-weight gate enforces immutable sources, original history prefix, absence of hazardous workspace entries, no duplicate operations, and no production/external-action claim. Ordinary extra regular files are diagnostic. Structured rows are keyed; plan order is exact only where prerequisites make it operationally significant.

Required artifacts are covered as workflow blocks: `work/rotation_plan.json`;
`state/rotation_state.json` with `state/rotation_events.jsonl`;
`work/dual_probe.json`; `work/verification.json`; and the bounded
`work/rotation_handoff.md`.

## 10. Leakage, isolation, and safety review

The workspace has no network, credentials, private keys usable outside the synthetic controller, or host dependencies. Reference outputs and tests are hidden. Visible tools reveal operational diagnostics but not reference artifacts. Direct state edits, history rewrites, premature retirement, rollback of new signers, production claims, and hazardous workspace entries fail the safety or core cases; ordinary extra regular files do not.

## 11. Pilot plan

Expected Gemma/OpenClaw failures are misreading bundle-capable versus single-CA flags, skipping the stale client, attempting retirement before dual verification, generating an incomplete probe, or stopping without idempotence confirmation. The task stays `hold` until adversarial tests, suite validation, leakage review, and a fresh real trajectory agree with terminal state. Candidate model outcome is diagnostic evidence only.

- **Expected Gemma/OpenClaw failure modes:** confuse bundle and single-CA roles,
  skip the stale client, retire before dual proof, emit an incomplete probe, or
  stop without idempotence confirmation.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Semantic equivalence policy

Cluster/component IDs, trust sets, signer identities, protected event types, transition order, handshake results, and receipt digests are exact. JSON row order is irrelevant. The handoff accepts equivalent professional language, but prose cannot rescue incorrect or manually fabricated state.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `diagnosis_and_legal_plan`, `controller_and_client_recovery`.
- `validation_and_replay`: `server_rotation_and_dual_proof`, `retirement_and_new_only_closure`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
