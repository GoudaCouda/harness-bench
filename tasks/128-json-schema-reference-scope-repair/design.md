# Task Design: 128-json-schema-reference-scope-repair

## 1. Workflow identity

This task models an engineer repairing a JSON Schema bundle after a URI-prefix migration. The final tree is superficially plausible, but a stale absolute identifier changes the effective base of a nested resource and makes its relative address reference resolve outside the registered bundle.

## 2. Idea provenance

The workflow adapts JSON Schema Core 2020-12 resource identification, base URI, anchors, and reference resolution. Source ID JSON-SCHEMA-CORE-2020-12 refers to https://json-schema.org/draft/2020-12/json-schema-core.html. - **Private user logs:** None were used; the migration incident is an authored benchmark fixture.
- **Synthetic-data statement:** Fixtures, domains, records, examples, and URIs are synthetic.

- **Adaptation:** JSON Schema 2020-12 resource identifiers and effective-base rules are converted into an offline migrated bundle where one mutable order schema must reconnect a protected registry, catalog reference, address anchor, and positive/negative examples.

## 3. Real-workflow justification

Schema repositories frequently separate retrieval locations from declared identifiers. Moving a bundle without reconciling absolute identifiers can leave files in the expected directories while validation resolves references elsewhere. Repair requires inspecting repository metadata, following URI resolution across files, preserving validation strictness, and proving both valid and invalid examples.

## 4. Agent-visible inputs

registry.json maps three schema paths to frozen retrieval URIs. schemas/catalog.json references the order resource. schemas/orders/order.json is the only mutable schema and contains the migration defect. schemas/common/address.json owns an address anchor. Two examples exercise a valid order and a missing-address failure. tools/check_bundle.py reports current graph diagnostics and writes a reproducible audit but does not edit schemas.

## 5. Hidden ground truth

The independent truth binds visible `registry.json`, `schemas/catalog.json`, `schemas/orders/order.json`, and `schemas/common/address.json` to required final state in `repo/schemas/orders/order.json`, `repo/out/bundle_audit.json`, and `repo/SCHEMA_HANDOFF.md`. The key invariant is that retrieval URI, declared identifier, relative `$ref`, and address anchor resolve inside the registered resource graph while required fields remain strict.

## 6. Expected workflow

1. Read `repo/README.md` and `repo/registry.json`, then inventory identifier and reference state across every schema resource.
2. Run `repo/tools/check_bundle.py` and trace the unresolved address event from retrieval URI through the order schema effective base.
3. Repair only `repo/schemas/orders/order.json`, preserving required-field and instance-classification invariants.
4. Run `repo/tools/check_bundle.py --write` to create `repo/out/bundle_audit.json` from the corrected graph.
5. Verify both valid and invalid examples and ensure the protected registry, checker, catalog, common schema, and examples are unchanged.
6. Write `repo/SCHEMA_HANDOFF.md` with the cause, reference chain, example results, commands, and offline boundary.

## 7. Harness demands

The task requires multi-file evidence grounding, URI reasoning, a scoped configuration edit, execution of a local diagnostic tool, positive and negative verification, and durable artifact production. It is not solved by implementing a standalone pure function.

## 8. Stressors and difficulty

- **Stressors:** valid-but-stale absolute identifier; retrieval URI versus effective-base scope; nested anchor resolution; plausible final tree; positive and negative instances.
- **Plausible failure mode:** hard-coding a replacement URI without following the registered base, weakening address requirements, editing the registry/checker, or validating only the positive example can leave a plausible but semantically broken bundle.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** the repair is small, but diagnosis requires multi-resource URI resolution, scope reasoning, strictness preservation, executable classification, and reproducible audit closure.

## 9. Oracle design

Resource graph correctness weighs 0.35, semantic example classification 0.25, reproducible audit 0.20, and engineering handoff 0.20. Core weight equals the 0.80 pass threshold. The oracle explicitly grades corrected state in `repo/schemas/orders/order.json`, deterministic evidence in `repo/out/bundle_audit.json`, and causal verification in `repo/SCHEMA_HANDOFF.md`. A zero-weight gate protects source evidence and filesystem safety; equivalent JSON formatting and key order are accepted.

## 10. Leakage, isolation, and safety review

The public checker reveals current resolution diagnostics and classifications, which is normal developer tooling, but it does not construct a repair. Hidden evaluation is independent. No network is required. Only the order schema, generated audit, and handoff are mutable.

## 11. Pilot plan

Acceptance requires untouched and malformed states to fail, the reference to score one, and adversarial variants for checker tampering, registry tampering, wrong-prefix URI hard-coding, weakened required fields, stale audit, and valid-only classification.

- **Expected Gemma/OpenClaw failure modes:** infer a file-path fix without checking effective base, change a protected registry entry, remove a required field to make examples pass, omit the negative example, or leave `repo/out/bundle_audit.json` stale after editing the schema.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, reference, discrimination, leakage, environment, Docker, and trajectory checks own admission.
- **Model calibration:** a fresh model/harness run remains useful difficulty evidence, not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval is not part of benchmark admission.
