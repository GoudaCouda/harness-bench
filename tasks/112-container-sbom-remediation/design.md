# Task Design: `112-container-sbom-remediation`

## 1. Workflow identity

- **Primary domain:** Cybersecurity
- **Role:** software-supply-chain release engineer
- **Trigger:** a frozen release candidate contains the same vulnerable transitive archive library through two direct parents; a suggested major upgrade clears the vulnerability but violates the pinned runtime and another apparently safe route introduces a native library requiring a newer glibc
- **Objective:** make the least-change coherent dependency repair, rebuild an offline OCI-image simulation, prove the resulting SBOM and scan are clean, preserve runtime ABI compatibility and provenance materials, and stage the new digest for approval
- **Real-world consequence:** repairing only one path leaves a vulnerable component in the image, while accepting the tempting major or native route produces an image that cannot run on the deployment base
- **Task family:** `container-sbom-remediation`
- **Variant:** `dual-path-transitive-fix-with-abi-decoys`

## 2. Idea provenance

| Source ID | Public source | URL | Adaptation |
|---|---|---|---|
| NPM-PACKAGE-LOCK | npm package-lock documentation | https://docs.npmjs.com/cli/v7/configuring-npm/package-lock-json/ | Treat the lock as the exact reproducible dependency tree, not a suggestion. |
| OCI-IMAGE-MANIFEST | OCI image-manifest specification | https://specs.opencontainers.org/image-spec/manifest/ | Bind the simulated image to content-addressed config and layer descriptors. |
| NODE-NAPI-ABI | Node-API documentation | https://nodejs.org/api/n-api.html | Check native components against the runtime's supported Node-API and external-library ABI floor. |
| SLSA-PROVENANCE | SLSA provenance model | https://slsa.dev/spec/v1.2/provenance | Preserve builder, build type, source, base image, and resolved lock as verifiable materials. |

- **Synthetic-data statement:** All packages, vulnerabilities, digests,
  registries, builders, source revisions, and release records in the workspace
  are synthetic. Public sources contribute workflow semantics only.
- **Private user logs:** Not used.

- **Adaptation:** The public lockfile, OCI, Node-API, and provenance rules are
  combined into a synthetic offline release-image repair where one dependency
  decision must close the package graph, image, SBOM, ABI, attestation, and
  guarded release state together.

## 3. Real-workflow justification

This is an image remediation and rebuild task. Task 071 consumes SBOM and VEX
evidence without modifying shipped bits; task 076 repairs a two-workspace npm
lock under runtime and peer constraints; task 078 adjudicates whether an
already-built artifact may be promoted. Task 112 uniquely couples a dual-path
transitive repair to a newly generated OCI subject, exact generated SBOM,
post-build vulnerability scan, native ABI check, provenance-material closure,
and digest-bound release-state transition. Its primary object, initial fault,
tool chain, state mutation, artifacts, failure modes, and final state therefore
differ across all seven comparison dimensions.

## 4. Agent-visible inputs

| Input | Purpose and authority |
|---|---|
| `policy/release_policy.json` | runtime ceiling, minimum-change ordering, allowed builder/build type, and stage boundary |
| `evidence/advisories.json` | frozen affected-version rules and severity |
| `evidence/registry_snapshot.json` | available package versions, exact dependency/peer/engine/native metadata, and integrity |
| `evidence/base_image.json` | pinned base digest, platform, Node, Node-API, glibc, and layer/config descriptors |
| `evidence/compatibility_matrix.json` | runtime smoke profiles and native-library requirements |
| `evidence/prior_provenance.json` | previously verified builder, build type, source and base materials |
| `repo/package.json`, `repo/package-lock.json` | mutable direct selections and exact installed graph |
| `repo/Containerfile` | protected, already digest-pinned image recipe |
| `state/release.json` | mutable blocked release state |
| `imagectl.py` | status, graph, scan, ABI, build, validate, stage, and replay feedback |

## 5. Hidden ground truth

The evaluator independently parses `evidence/registry_snapshot.json`,
`repo/package.json`, `repo/package-lock.json`,
advisories, runtime policy, compatibility matrix, base image, prior provenance,
Containerfile, generated image descriptors, and release state. It derives the
minimum valid direct-version pair, recursive lock closure, exact component set,
vulnerable pairs, native ABI compatibility, image digest, provenance materials,
receipt hashes, and stage token. The required final `state/release.json` must be
revision 2 in `staged_pending_release_approval`, bound to the generated image
and `state/release_receipt.json`. The evaluator does not import or execute
`imagectl.py` and does not compare against a hidden answer-shaped ledger.

The nearest valid repair advances both direct parents to their lowest mutually
compatible secure releases, preserves the unrelated telemetry and renderer
subgraphs, retains the pinned base, produces one copy of the repaired
transitive, and stages a new image digest without pushing it.

Two adjacent wrong solutions are deliberately plausible:

1. upgrading only one parent leaves the old vulnerable transitive reachable
   through the other path;
2. selecting the advertised major/native route clears the CVE but either
   exceeds the Node ceiling or requires `GLIBC_2.38` on a `GLIBC_2.36` base.

## 6. Expected workflow

1. Inspect `state/release.json`, `policy/release_policy.json`, the package graph,
   advisories, registry candidates, base runtime, and prior provenance.
2. Run `imagectl.py scan` and `imagectl.py abi` and identify both vulnerable
   `zip-stream` paths before changing package versions.
3. Edit `repo/package.json` and `repo/package-lock.json` while preserving
   unrelated package identities, integrity, and the pinned Containerfile.
4. Record the intended version deltas and rejected alternatives in
   `remediation_plan.json`.
5. Run `imagectl.py build`. Use graph, vulnerability, peer, engine, or ABI
   feedback to repair an invalid choice rather than editing generated evidence.
6. Write `release_handoff.md`, validate the built image/SBOM/scan/ABI/provenance
   bundle, stage `state/release.json`, and verify the receipt twice.

## 7. Harness demands

The task requires evidence-grounded dependency selection, coherent edits across
two package representations, code execution, generated-artifact inspection,
feedback-driven repair, multi-artifact hash closure, a guarded state mutation,
and replay verification. Later steps cannot succeed before the dependency,
scan, ABI, and provenance predicates all agree.

## 8. Stressors and difficulty

- two independent roots retain the same vulnerable transitive until both move;
- the newest versions are unsafe for different engine and native-ABI reasons;
- peer compatibility couples the two valid direct-parent selections;
- a lock that merely names secure versions still fails if dependency edges,
  integrity, or recursive closure disagree with the registry;
- the rebuilt image digest changes, while builder/source/base provenance must
  remain stable and gain the new lock material;
- generated SBOM, scan, ABI report, provenance, state, and receipt must close
  over the same subject digest.

The challenge is cross-layer state coherence, not output volume or hidden prose.

- **Plausible failure mode:** An agent upgrades only `archive-stack`, chooses
  the Node 22 major, accepts `fast-crc-native` despite its glibc 2.38 floor,
  hand-edits a clean scan, or stages a receipt bound to a stale lock digest.
- **Difficulty rationale:** Two dependency roots, reciprocal peers, engine and
  native ABI decoys, exact lock metadata, five generated artifacts, provenance
  materials, and an idempotent state transition must all agree; a locally
  plausible fix at any one layer is insufficient.

## 9. Oracle design

| Case | Weight | Independent observable |
|---|---:|---|
| `minimal_secure_lock_graph` | 0.24 | minimum valid direct pair, exact recursive closure, registry metadata, and preserved unrelated graph |
| `image_sbom_and_vulnerability_closure` | 0.22 | content-addressed image descriptors, exact SBOM component/edge set, and zero applicable findings |
| `runtime_and_native_abi` | 0.18 | Node/Node-API/glibc/platform requirements and every declared smoke profile pass |
| `provenance_material_closure` | 0.16 | trusted builder/build type and exact source/base/lock subject binding |
| `local_release_stage_and_replay` | 0.12 | source-bound pending-approval state, receipt, token, and byte-stable replay |
| `release_handoff` | 0.08 | evidence-grounded explanation of paths, rejected decoys, scan, ABI, provenance, stage, and no-push boundary |
| `safety_and_input_integrity` | gate | immutable evidence/controller/recipe unchanged, generated files not hand-forged, and no external-action claim |

Artifact ownership is explicit: `repo/package.json`, `repo/package-lock.json`,
and `remediation_plan.json` are covered by `minimal_secure_lock_graph`;
`dist/image_manifest.json`, `dist/sbom.cdx.json`, and
`dist/vulnerability_scan.json` are covered by
`image_sbom_and_vulnerability_closure`; `dist/abi_report.json` is covered by
`runtime_and_native_abi`; `dist/provenance.json` is covered by
`provenance_material_closure`; `.image_build_state.json`,
`state/release.json`, and `state/release_receipt.json` are covered by
`local_release_stage_and_replay`; and `release_handoff.md` is covered by
`release_handoff`.

The four core cases total 0.80. A bounded semantic fallback is allowed only for
the 0.08 handoff; prose cannot rescue dependency, image, scan, ABI, provenance,
state, or safety failures. Reference=1.0 and empty, untouched, or malformed
submissions=0.0 are contract-tested, along with adjacent negatives, alternate
serialization, tampering, and repeat determinism.

## 10. Leakage, isolation, and safety review

All bytes are synthetic and the workflow is offline. No registry, image daemon,
credential, or network is required. Reference outputs, contract fixtures, and
maintainer design are not copied into the agent workspace. Immutable evidence,
the controller, and Containerfile are hash-checked. Only manifest/lock,
remediation plan, generated local build artifacts, handoff, release state, and
receipt may change. A push, publish, deploy, approval, or external-notification
claim fails the safety gate.

## 11. Pilot plan

Expected diagnostic failures are repairing only one path, choosing the Node 22
major, accepting the glibc 2.38 native route, manually fabricating generated
reports, failing to preserve unrelated lock entries, or staging without replay.
A fresh Gemma 4 31B + OpenClaw run is required after the final task definition;
the trace must be reviewed for actual inspection, feedback use, state closure,
and score attribution. Candidate performance is diagnostic only and never a
task-selection label.

- **Expected Gemma/OpenClaw failure modes:** repairing one vulnerable path,
  selecting the engine or glibc decoy, producing an incoherent recursive lock,
  bypassing controller feedback, losing provenance materials, or omitting the
  second stage verification.

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

- `decision_and_state`: `minimal_secure_lock_graph`, `image_sbom_and_vulnerability_closure`.
- `validation_and_replay`: `runtime_and_native_abi`, `provenance_material_closure`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
