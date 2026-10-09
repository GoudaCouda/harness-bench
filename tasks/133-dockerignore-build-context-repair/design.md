# Task Design: 133-dockerignore-build-context-repair

## 1. Workflow identity

This task models a container maintainer repairing a Docker build-context leak caused by ordered negation rules. The build still appears viable, but a broad JSON reinclusion sends a developer credential file and an unrelated documentation exception expands the context.

## 2. Idea provenance

The workflow adapts Docker build-context and `.dockerignore` matching semantics documented at https://docs.docker.com/build/building/context/#dockerignore-files. The retained source ID is `DOCKERIGNORE-BUILD-CONTEXT`.

- **Private user logs:** None were used; the repository and leakage report are authored benchmark fixtures.
- **Synthetic-data statement:** Paths, configuration values, package names, digests, and credential-shaped strings are synthetic.

- **Adaptation:** Docker ordered `.dockerignore` semantics are transformed into an offline repository containment incident where broad negations reinclude a local credential-shaped JSON file and excess documentation while a minimal runtime context must remain buildable.

## 3. Real-workflow justification

Docker clients filter files before sending a build context. Ordered patterns and negation can unintentionally reinclude local configuration even when a prior directory rule looks protective. Real remediation requires inventorying the full tree, preserving runtime inputs, narrowing precedence, producing a deterministic context manifest, and proving secrets and irrelevant bulk are excluded without deleting evidence.

## 4. Agent-visible inputs

The repository contains application code, runtime defaults, local overrides, synthetic secrets, dependencies, build output, tests, docs, Git metadata, and a retained license. Policy lists required and protected paths. The public audit utility applies ordered patterns and writes included paths, excluded protected paths, byte count, and per-file hashes.

## 5. Hidden ground truth

The grader binds visible `repo/.dockerignore`, `repo/policy/context_policy.json`, the complete repository tree, and `repo/tools/audit_context.py` to final state in `repo/.dockerignore`, `repo/out/context_manifest.json`, and `repo/BUILD_CONTEXT_HANDOFF.md`. The invariant is an exact included-path set with required runtime inputs retained, every protected path excluded, and hashes/byte count derived from current files.

## 6. Expected workflow

1. Inventory the full `repo/` tree, including dotfiles, generated output, dependencies, tests, docs, local configuration, and retained license.
2. Read `repo/policy/context_policy.json` and trace ordered state through every rule in `repo/.dockerignore`.
3. Run `repo/tools/audit_context.py` to reproduce which negation event reintroduces local JSON and documentation.
4. Repair only `repo/.dockerignore` with narrowly scoped precedence rules that retain required runtime files.
5. Rerun the audit to generate `repo/out/context_manifest.json`, then verify included paths, protected exclusions, byte count, and file hashes.
6. Write `repo/BUILD_CONTEXT_HANDOFF.md` with cause, exact scope, commands, and evidence; do not build or publish an image.

## 7. Harness demands

The task requires filesystem discovery including dotfiles, ordered-policy reasoning, a scoped configuration edit, executable local verification, artifact inspection, and evidence-rich handoff. It is not a function implementation exercise.

## 8. Stressors and difficulty

- **Stressors:** ordered pattern precedence; negation reinclusion; hidden files; runtime-default preservation; deterministic context hashing.
- **Plausible failure mode:** appending a broad exclusion can hide required defaults or the license, while retaining `!config/*.json` leaks local credentials; deleting leaked files or forging the manifest avoids rather than fixes context policy.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** a valid repair requires complete tree discovery, ordered-rule reasoning, simultaneous positive/negative set satisfaction, and reproducible manifest verification, not a keyword edit.

## 9. Oracle design

Exact context selection weighs 0.40, protected-path containment 0.20, reproducible manifest 0.20, and handoff 0.20. The oracle explicitly grades `repo/.dockerignore`, `repo/out/context_manifest.json`, and `repo/BUILD_CONTEXT_HANDOFF.md`. Core weight is 0.80; a zero-weight gate protects repository evidence and filesystem boundaries. Semantically equivalent ignore rules are accepted.

## 10. Leakage, isolation, and safety review

All files and credential strings are synthetic and local. The public audit reports included paths but does not prescribe rules. Hidden selection and hashing are independent. Ordinary omissions and over-inclusions lose weighted cases; protected-source tampering reaches the gate.

## 11. Pilot plan

Acceptance requires untouched and malformed zero, reference one, and adversarial failures for deleting leaked files, excluding required defaults, retaining broad negations, forged manifests, audit-tool tampering, and handoff-only answers.

- **Expected Gemma/OpenClaw failure modes:** inspect only visible files, misunderstand last-match negation precedence, exclude required runtime defaults, delete a synthetic secret, fail to regenerate `repo/out/context_manifest.json`, or claim that an image was built/published.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, reference, discrimination, leakage, environment, Docker, and trajectory checks own admission.
- **Model calibration:** a fresh model/harness run remains useful difficulty evidence, not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval is not part of benchmark admission.
