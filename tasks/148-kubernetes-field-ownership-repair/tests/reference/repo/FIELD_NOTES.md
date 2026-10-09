# Field ownership repair handoff

The planner validates the complete flattened object, defaults, managed-field
ownership, intents, and policy before projecting anything. Each intent is then
transactional: conflicts are calculated before omission release or value
updates. A rejected conflict therefore leaves both values and all owners
unchanged. A force request can take conflicting ownership, but a conflict under
a protected path rejects the whole request instead of partially forcing safe
fields.

An assertion matching the current value is not a conflict. It adds shared
ownership, which supports coordinated manager handoff. A changed value owned by
another manager conflicts unless force is accepted; accepted force removes the
displaced owners for that field. Unowned and newly created paths become owned by
the applying manager.

Accepted intents are fully specified for that manager. Omitted paths release
its previous ownership. Shared paths remain live for their remaining managers.
When the final owner releases a path, the field resets to the declared default
if present and otherwise is deleted. Later intents read the exact object and
ownership produced by earlier accepted requests, while rejected requests have
no sequential side effect.

Verification used `python -m unittest discover -s tests` and
`python bin/apply_intents.py`, followed by parsing `out/object.json`,
`out/ownership.json`, and `out/decisions.json`. Both commands passed and all
artifacts matched a fresh pure-function result. This was an offline preview:
no Kubernetes API was contacted, no manifest was applied, and no live
managedFields or controller state was changed.
