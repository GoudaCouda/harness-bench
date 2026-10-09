# Infrastructure lifecycle planning contract

Implement `build_lifecycle_plan(resources, prior_state, observed, policy)`
without mutating inputs. Exact structural violations raise `ValueError` before
producing partial output.

Addresses and attribute keys are nonempty lowercase ASCII tokens. Lists named
below are sorted and unique. Attribute values are JSON scalars: string, integer,
boolean, or null. Booleans are not integers for structural checks.

Each desired resource has exact keys `address`, `depends_on`, `attributes`,
`immutable`, and `lifecycle`. Lifecycle has exact keys `create_before_destroy`,
`prevent_destroy`, `ignore_changes`, `replace_triggered_by`, and `moved_from`.
The first two are booleans, the next two are sorted unique lists, and
`moved_from` is null or an address. Dependencies reference desired resources;
replacement triggers reference a desired or prior-state address. Self references
and dependency cycles are invalid. Immutable keys occur in desired attributes.

Each prior-state row has exact keys `address`, `generation`, `depends_on`, and
`attributes`; generation is positive. Prior dependencies reference prior rows
and form an acyclic graph. Each prior address has exactly one observation with
exact keys `address`, `exists`, `attributes`, and `unknown`. If `exists` is
false, attributes and unknown are empty. Otherwise known attributes and unknown
keys are disjoint and together equal the prior attribute keys.

Policy has exact keys `allow_destroy` (boolean) and `sensitive_keys` (a sorted
unique attribute-key list). Duplicate addresses are invalid throughout.

Resolve moves before diffing. A nonnull `moved_from` must identify one prior
row, no two resources may move the same row, and prior state cannot already
contain the destination. Remap that row, its observation, and prior dependency
references to the destination. A move is identity preservation, not create and
delete.

For an existing resource, compare desired configuration, prior state, and known
remote observation. Ignore every key in `ignore_changes` during update planning;
its projected value is the known observed value, or prior value when unknown.
For managed keys, configuration changes, known drift, added/removed keys, and
unknown observations require convergence. A changed immutable key requires
`replace`. An unknown managed immutable key is `blocked`, because replacement
safety cannot be established. A missing observed object is `create`. A resource
without prior state is also `create`; otherwise unchanged resources are `no-op`
and mutable differences are `update`.

After base diffs, repeatedly apply `replace_triggered_by`: an existing no-op or
update resource becomes `replace` when any referenced resource has an actionable
create, update, replace, or delete. This is transitive. Create and blocked
resources retain their action. `prevent_destroy` converts replacement to
`blocked`. A prior object absent from desired configuration is `delete`, unless
already absent remotely (`no-op`) or policy disallows destruction (`blocked`).

For replacement resources, propagate `create_before_destroy` from a replacement
to any of its dependencies that are also replacements, to a fixed point. Steps
are deterministic: non-create-before-destroy replacement destroys occur first
in reverse desired dependency order; creates, updates, and all replacement
creates occur in forward dependency order; create-before-destroy deposed-object
destroys occur next in reverse order; removals occur last in reverse prior
dependency order. Blocked and no-op resources emit no step.

`plan.resources` is sorted by address. Each item has exact keys `address`,
`action`, `reasons`, `before`, `after`, and `create_before_destroy`. Reasons are
sorted unique. Before and after maps use `"<unknown>"` for unknown observations
and `"<sensitive>"` for every policy-sensitive value. Deletion has null after;
creation has null before. Steps have exact keys `address` and `operation`.
Summary has counts for `create`, `update`, `replace`, `delete`, `no-op`,
`blocked`, plus `step_count` and `moved_count`.

Return `{"plan":{"resources":[...],"steps":[...]},"summary":{...}}`.
No provider, network, filesystem, state, clock, random, process, or environment
access is allowed.
