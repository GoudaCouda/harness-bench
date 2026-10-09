# Plugin lifecycle reconciliation contract

Implement `reconcile_plugins(state, catalog, request, faults)` as a pure
function. Validate all inputs before planning; invalid structures raise
`ValueError` and arguments remain unchanged.

`catalog` is a list of plugin objects with exactly `name`, `depends`, and
`hooks`. Names are unique non-empty strings. Dependency and hook lists contain
unique non-empty strings. Every dependency exists, self-dependencies and cycles
are invalid. A hook name may be owned by only one plugin.

`state` has exactly `generation`, `active`, and `registrations`. Generation is a
non-negative integer excluding booleans. Active is a unique list of known plugin
names whose dependency closure is already active. Registrations is a list of
objects with exactly `plugin` and `hook`; it may contain stale, missing, or
duplicate rows because cleanup is part of reconciliation.

`request` has exactly unique `enable` and `disable` lists. `faults` has exactly
unique `activate` and `deactivate` lists; all members are non-empty strings.
Unknown requested names or a name in both request lists is a business rejection,
not malformed input. Fault names may be unknown because unused injected faults
must be harmless.

Enabling a plugin includes its complete dependency closure. Disabling includes
all currently active reverse dependents. If the two closures intersect, reject
the request. Activation order is a deterministic topological order with lexical
ties; deactivation is the reverse dependency order with reverse-lexical ties.

Attempt deactivations, then activations. A named injected fault occurs before
that plugin changes. Any fault rolls the whole request back to the byte-equivalent
input state, including stale registrations and generation. `rollback_order`
lists successfully changed plugins in reverse attempt order. A rejected request
also preserves the exact input state and has no attempts.

On success, active names are lexical. Registrations are rebuilt exactly once
from all hooks owned by active plugins and sorted by `(plugin, hook)`, removing
stale/duplicate rows. Generation increments by one only if active state or
registrations changed; a canonical no-op keeps it unchanged.

Return exactly `{"state": ..., "journal": ...}`. Journal has exactly `status`
(`committed`, `rolled_back`, or `rejected`), `reason` (`ok`, `no_change`,
`request_conflict`, `unknown_plugin`, `activate_failed`, `deactivate_failed`),
`activation_order`, `deactivation_order`, `failed_plugin` (string or null), and
`rollback_order`.
