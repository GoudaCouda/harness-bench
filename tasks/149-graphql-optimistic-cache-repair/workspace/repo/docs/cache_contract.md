# Normalized optimistic cache contract

Implement `reconcile_cache(base, events, policy)` without mutating inputs.
Structural or event-state violations raise `ValueError` rather than returning a
partial result.

Policy has exact keys `allowed_typenames` (sorted unique names beginning with an
uppercase ASCII letter) and `max_active_layers` (1..20). A cache ID is
`Typename:key`, where Typename is allowed and alphanumeric and key is a nonempty
lowercase ASCII token. A cache is a map from cache IDs to field maps. Field names
are lowercase tokens. Values are JSON scalars, one exact `{"$ref":"Cache:id"}`
object, or a list containing only such references. Every reference in base and
in every projected visible state must resolve to an existing record.

Every event has exact keys `kind`, `mutation_id`, `mode`, `writes`, and
`aliases`. Mutation IDs are lowercase tokens. Writes are sorted unique records
with exact keys `id` and `fields`; fields merge into a record, so missing fields
are preserved and explicit null overwrites. Aliases map distinct temporary cache
IDs to distinct server cache IDs and may not form a same-event chain.

An `optimistic` event starts one active mutation. Mode `apply` stores its writes
as a new top layer; mode `ignore` requires empty writes and creates no visible
overlay while remaining resolvable. Optimistic aliases are empty. A mutation ID
may start only once. Active mutation count may not exceed the policy limit.

A `success` event has mode `resolve`, references an active mutation, removes
only that mutation's layer, then applies aliases and server writes to canonical
base. Alias rewriting changes references in base and every still-active layer.
If a source record exists in base or a pending layer, rename it to the target;
source fields are merged first and an existing target's fields win. Server writes
then merge last and therefore have authority. Alias sources may exist only in
the resolved optimistic layer, in which case no optimistic fields are committed.

An `error` event has mode `resolve`, empty writes and aliases, and removes only
the named active layer. Later layers remain active and are reprojected over the
new base. Unknown resolutions, duplicate starts, invalid refs, duplicate write
IDs, alias collisions, or a stream ending with invalid projected refs are errors.

Visible cache is recomputed by merging canonical base with active non-ignored
layers in their start order; later layers win field by field. Return sorted
`base`, final `visible`, and one audit row per event with exact keys
`mutation_id`, `kind`, `status`, and `active_layers`. Status is `layer_started`,
`ignored`, `committed`, or `rolled_back`. Active-layer IDs preserve start order
and include unresolved ignored mutations. No GraphQL, network, browser,
filesystem, clock, random, process, or environment access is allowed.
