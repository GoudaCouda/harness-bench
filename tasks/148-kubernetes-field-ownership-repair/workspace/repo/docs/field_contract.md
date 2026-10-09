# Field ownership apply contract

Implement `apply_intents(live, ownership, defaults, intents, policy)` without
mutating inputs. Exact structural violations raise `ValueError` before any
partial output.

The live object and defaults are flat maps from canonical field paths to JSON
scalar values (string, integer, boolean, or null). A canonical path starts with
one slash, has no empty, `.` or `..` segment, has no trailing slash, and uses
only lowercase ASCII letters, digits, `_`, `-`, `.`, `=`, `[` and `]` inside
segments. Booleans are scalar values, not integers for structural checks.

Policy has exact keys `allowed_paths` and `protected_prefixes`, both sorted
unique canonical path lists. Every live/default/intent field is in
`allowed_paths`. A protected prefix matches itself and slash-delimited
descendants.

Ownership is sorted by path. Each entry has exact keys `path` and `managers`;
managers are sorted unique nonempty lowercase tokens and the path exists in the
live object. Live fields without an entry are unowned.

Every intent has exact keys `request_id`, `manager`, `force`, and `fields`.
Request IDs are unique lowercase tokens, manager is a lowercase token, force is
boolean, and fields is a possibly empty scalar map. Intents are processed in
input order, and each accepted intent changes the state seen by later intents.

Before changing anything for an intent, find every asserted field whose live
value differs and which is owned by another manager. Same-value assertions do
not conflict and add shared ownership. Without force, any conflict rejects the
entire intent. With force, a conflict under a protected prefix has status
`protected` and also rejects the entire intent. Rejection must not release
omitted fields. Otherwise force changes each conflicting value, removes every
other owner for that field, and records it as forced.

On an accepted intent, first release fields previously owned by this manager but
omitted from its new fully specified intent. Shared fields retain their value
and remaining owners. A field losing its final owner resets to its default when
one exists, otherwise it is deleted. Then apply asserted values. A changed
field is owned solely by the applying manager unless it was unowned; an
unchanged field adds the manager alongside existing owners. New fields are
created and owned by the manager.

Return `object` as a path-sorted map, `ownership` as sorted nonempty ownership
entries, and one decision per intent in order. Decisions have exact keys
`request_id`, `manager`, `status`, `conflicts`, `changed_paths`,
`acquired_paths`, `released_paths`, and `forced_paths`; all path lists are
sorted unique. Rejected decisions have empty change/acquire/release/force lists.
No cluster, network, filesystem, clock, random, process, or environment access
is allowed.
