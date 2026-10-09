# Infrastructure lifecycle planning handoff

The repaired planner first validates both dependency graphs and all observation
coverage, then resolves every `moved_from` identity before comparing values. A
move remaps prior state, observation, and prior dependency references; it does
not invent a delete/create pair. Destination collisions, reused sources, missing
sources, and graph cycles fail the complete batch.

Diffing separates desired configuration from prior state and known remote drift.
Managed mutable differences converge with update, changed immutable fields use
replacement, and a missing remote object uses create. An unknown observation on
a managed immutable field is blocked because safe replacement cannot be chosen.
`ignore_changes` suppresses both configuration and observed drift during update
planning and preserves the known remote value, or prior value when unknown.

Replacement triggers are evaluated repeatedly, so a change can propagate across
more than one resource. `prevent_destroy` blocks replacement and emits no step.
Removed configuration is deleted only when the supplied destroy policy permits
it; an already missing object is a no-op. Create-before-destroy is propagated
from a replacing dependant to replacing dependencies. The final schedule uses
forward dependency order for creates and updates and reverse dependency order
for destructive phases, including deposed-object cleanup and removals.

Before and after maps redact every policy-sensitive key as `<sensitive>` and use
`<unknown>` only for unresolved nonsensitive observations. Therefore passwords
and equivalent captured values cannot leak through the plan or summary.

Verification used `python -m unittest discover -s tests` and
`python bin/build_plan.py`, followed by parsing `out/plan.json` and
`out/summary.json`. Both commands passed and the artifacts matched a fresh pure
function result. This was offline lifecycle planning only: Terraform was not
invoked, no provider was contacted, no state was written, and no live plan or
apply changed infrastructure.
