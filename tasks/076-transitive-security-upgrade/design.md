# Task Design: `076-transitive-security-upgrade`

## 1. Workflow identity

- **Domain / role:** Software Engineering; dependency and software-supply-chain maintainer.
- **Trigger:** Six transitive advisories affect packages reached through four direct parents in the root application and an upload worker under a Node 18 runtime ceiling and coupled peer constraints.
- **Objective:** Select the least-change coherent cross-workspace remediation, regenerate the shared recursive lock graph with integrity/metadata coherence, execute compatibility fixtures, and hand off without publishing.
- **Consequence:** Directly pinning a transitive package can create an unsupported graph, while jumping to an incompatible major can break production.

## 2. Idea provenance

- **Source:** [GitHub Dependabot version updates](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates).
- **Origin class:** public_workflow_adaptation; source ID SE-03.
- **Synthetic-data statement:** Package names, versions, advisories, and registry data are synthetic.
- **Adaptation:** Real manifest/lock reconciliation was reduced to a deterministic offline registry and compatibility fixture set.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Maintainers trace a vulnerability through dependency edges, choose a supported direct upgrade, regenerate a coherent lock graph, run the declared runtime matrix, preserve unrelated resolution state, and stop before release authorization.

## 4. Agent-visible inputs

| Input | Authority |
|---|---|
| `advisory.json` | Defines six affected transitive packages across root and worker paths. |
| `package_registry.json` | Authoritative candidate parent releases and dependency edges. |
| `runtime_policy.md` | Node ceiling, minimum-change, and release boundaries. |
| `repo/package.json`, `repo/packages/worker/package.json`, `repo/package-lock.json` | Mutable monorepo manifests and shared lock state. |
| `repo/compat_fixtures.json` | Declared compatibility matrix. |
| `repo/check_upgrade.py` | Protected graph and fixture verifier. |

## 5. Hidden ground truth

Agent-visible `advisory.json`, `package_registry.json`, `repo/compat_fixtures.json`, `repo/package.json`, `repo/packages/worker/package.json`, and `repo/package-lock.json` determine the required final state of both manifests, the shared lock and `upgrade_handoff.md`. The least-change graph is `webstack` 5.4.3, `auth-ui` 3.2.1, `upload-agent` 2.7.2, and `storage-sdk` 4.1.1. It resolves eleven incident-scope packages, clears all six advisories, preserves four compatibility profiles and satisfies two peer families under Node 18. Both workspace roots, every recursive entry, registry integrity, dependency/peer metadata, parser tooling and lock generator metadata must agree. The checker derives candidates from the visible registry and advisories rather than embedding the target graph.

## 6. Expected workflow

1. Trace all six records in `advisory.json` through root `repo/package.json`, worker `repo/packages/worker/package.json`, and `package_registry.json`.
2. Use Node 18, peer ranges and profiles in `repo/compat_fixtures.json` to eliminate unsupported candidates.
3. Update each owning manifest and regenerate both workspace roots plus the recursive closure in `repo/package-lock.json`.
4. Execute `repo/check_upgrade.py`, repair graph or metadata diagnostics, and record the result in `upgrade_handoff.md`.
5. Confirm unrelated package state and write `upgrade_handoff.md` without claiming a release.

## 7. Harness demands

Evidence grounding, dependency-graph state management, local code execution, minimal patching, and verification are all required.

## 8. Stressors and difficulty

- **Plausible failure mode:** The agent repairs only the root application, chooses upload-agent 2.7.1 while leaving a nested advisory, violates a worker peer/profile, omits nested integrity, changes parser or generator metadata, or reports publication.
- **Difficulty rationale:** Four direct parents across two manifests jointly control six advisories and seven transitives. Viable versions interact through Node engines, peer intervals, four compatibility profiles, recursive integrity, workspace roots and a least-change ordering; a newer secure graph can still be unsupported or non-minimal.

## 9. Oracle design

Core weight 0.80 covers secure resolution in `repo/package.json` and `repo/packages/worker/package.json` (0.35), coherent recursive `repo/package-lock.json` resolution (0.25), and executable compatibility (0.20). Minimal scope and `upgrade_handoff.md` quality are 0.10 each. The gate protects evidence and rejects publication/deployment claims.

## 10. Leakage, isolation, and safety review

All registry and advisory data are synthetic and offline. The agent may modify only manifest and lockfile and create the handoff. The grader reruns the protected checker and does not trust a reported pass.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Directly editing a transitive lock entry, selecting webstack 6.0.0 despite Node 18, failing to preserve parser packages, or omitting exact verification evidence from the handoff.
- **Expected strong-harness success band:** To be calibrated from repeated post-review runs; model performance is diagnostic only.
- **Revision rule:** Repair only reproducible graph, environment, specification, or oracle defects and do not tune semantic selection to candidate scores.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
