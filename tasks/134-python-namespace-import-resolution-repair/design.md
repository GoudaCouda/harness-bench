# Task Design: 134-python-namespace-import-resolution-repair

## 1. Workflow identity

This task models a Python monorepo repair where two separately owned source roots contribute to one implicit namespace package. An accidental regular-package marker in the API root prevents discovery of the metrics plugin when that root appears first.

## 2. Idea provenance

The workflow adapts Python implicit namespace-package semantics from PEP 420 at https://peps.python.org/pep-0420/. The retained source ID is `PYTHON-PEP-420`.

- **Private user logs:** None were used; the repository and ownership records are authored benchmark fixtures.
- **Synthetic-data statement:** Package names, plugin behavior, owners, paths, and probe results are synthetic.

- **Adaptation:** PEP 420 implicit namespace semantics are transformed into an offline two-root monorepo where an obsolete top-level marker shadows another owner under one `PYTHONPATH` order and only a minimal ownership-safe deletion is permitted.

## 3. Real-workflow justification

Large Python deployments often compose distributions or monorepo roots under a shared namespace. A stray `__init__.py` can turn one portion into a regular package and silently hide another root. Repair requires module-origin inspection under all supported path orders, respect for ownership boundaries, a minimal structural edit, and executable verification.

## 4. Agent-visible inputs

The API root owns the orders plugin and contains the defective namespace marker. The vendor root owns metrics. Ownership files forbid copying or editing plugin implementations. The local probe starts fresh interpreters under both path orders and records import success, module origin, and plugin output.

## 5. Hidden ground truth

The evaluator binds visible ownership records, both source roots, and `repo/tools/probe_imports.py` to required final state in `repo/out/import_probe.json` and `repo/IMPORT_HANDOFF.md`. The key invariant is that `acme.plugins.orders` and `acme.plugins.metrics` resolve from their original owner roots under both path orders, while the namespace state contains both locations and no copied module or shim is introduced.

## 6. Expected workflow

1. Read ownership records and inventory every `__init__.py` and plugin implementation under both `repo/services/api/src` and `repo/vendor/metrics/src`.
2. Run `repo/tools/probe_imports.py` to reproduce the path-order event and inspect module origins plus namespace locations.
3. Diagnose `repo/services/api/src/acme/__init__.py` as the obsolete regular-package marker rather than changing plugin code or path state.
4. Delete only that marker so PEP 420 composes both owner roots without a shim or copied module.
5. Rerun the full two-order matrix and retain normalized evidence in `repo/out/import_probe.json`.
6. Write `repo/IMPORT_HANDOFF.md` with cause, ownership boundary, exact change, probe matrix, and verification.

## 7. Harness demands

The task requires repository discovery, Python import-system reasoning, subprocess execution, provenance inspection, a deletion rather than a code implementation, multi-order verification, and durable evidence.

## 8. Stressors and difficulty

- **Stressors:** opposite path order; regular-package shadowing; split ownership; module provenance; deceptively small repair.
- **Plausible failure mode:** validating only the healthy path order, copying metrics into the API root, adding `sys.path` mutation, editing plugin implementations, or reporting imports without checking origins violates ownership despite apparent success.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** the one-file deletion must be inferred from import specifications, namespace path composition, owner boundaries, and fresh-process verification under both root orders.

## 9. Oracle design

Two-order import success weighs 0.40, module ownership and namespace provenance 0.20, reproducible probe 0.20, and handoff 0.20. The oracle explicitly grades `repo/out/import_probe.json` and `repo/IMPORT_HANDOFF.md`, while the mutation contract limits repository state to deletion of the obsolete marker. Core weight equals 0.80; a zero-weight gate protects implementations, ownership records, and filesystem boundaries.

## 10. Leakage, isolation, and safety review

Everything runs in fresh local Python interpreters without installation or network. The public probe reveals failures and origins but not the required edit. Hidden probes are independent. Equivalent namespace-preserving repairs are bounded by the explicit mutation contract.

## 11. Pilot plan

Acceptance requires untouched and malformed zero, reference one, and adversarial failures for copying metrics into API, adding path mutation shims, editing plugin outputs, validating only one path order, forged reports, and probe tampering.

- **Expected Gemma/OpenClaw failure modes:** add a compatibility shim instead of repairing package state, delete the wrong `__init__.py`, run only one path order, ignore module origin, copy another owner’s plugin, or leave `repo/out/import_probe.json` inconsistent with current imports.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, reference, discrimination, leakage, environment, Docker, and trajectory checks own admission.
- **Model calibration:** a fresh model/harness run remains useful difficulty evidence, not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval is not part of benchmark admission.
