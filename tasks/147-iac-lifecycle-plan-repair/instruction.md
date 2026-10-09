# Repair an infrastructure lifecycle plan

An internal IaC planner mishandles moved state, ignored drift, replacement
triggers, and create-before-destroy ordering. Its current plan could destroy a
protected resource or create dependants before their dependencies. Work only in
`/workspace/repo`.

Read `docs/lifecycle_contract.md`, inspect desired resources, prior state,
observations, policy, runner, and public tests, then repair
`src/lifecycle_plan.py` as a general pure implementation. Do not hard-code
resource addresses, attributes, or fixture values.

Run the public unittest suite and `python bin/build_plan.py`. The final run must
create `out/plan.json` and `out/summary.json`; parse both again. Write
`LIFECYCLE_NOTES.md` covering moved-state identity, drift versus configuration,
ignore rules, immutable and triggered replacement, unknown observations,
prevent-destroy, create-before-destroy propagation, dependency order, sensitive
redaction, strict validation, commands, and results.

Do not edit evidence, invoke Terraform, contact a provider, mutate state or
infrastructure, or claim that any live plan or apply was run.
