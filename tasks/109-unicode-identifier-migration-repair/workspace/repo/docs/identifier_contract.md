# Unicode identifier migration contract

Implement `migrate_identifiers(records, reserved, policy)` without mutating
arguments. Validate all input before migration; malformed input raises
`ValueError`.

`policy` has exactly `normalization` (`NFKC`), `case_insensitive` (`true`), and
`max_codepoints` (positive integer at most 128, excluding booleans). `reserved`
is a unique list of non-empty strings. `records` is a list of exact
`{record_id, identifier, references}` objects. Record IDs are unique non-empty
strings; identifiers are strings; references are unique known record IDs.

Canonicalize an identifier as
`NFKC(NFKC(identifier).casefold())`. Validate the canonical result, not the
display input: it must be non-empty, at most `max_codepoints`, and satisfy
Python's Unicode `str.isidentifier()` profile. Canonicalize reserved names by
the same algorithm. Reserved entries that canonicalize invalidly make the batch
invalid.

All records are analyzed before assignment. A valid canonical key used by two
or more records is a collision; none of those records receives that key. A key
in the canonical reserved set is reserved. Invalid/empty/overlength identifiers
are invalid. Do not merge visually confusable strings unless the specified
normalization and case fold actually make them equal.

Output records preserve input order and have exactly `record_id`,
`display_identifier` (the original string), `canonical_identifier` (string only
for accepted records, otherwise null), `status` (`accepted`, `collision`,
`reserved`, or `invalid`), `canonical_references`, and
`unresolved_reference_ids`. Resolve a reference only when its target is
accepted; canonical references and unresolved IDs are unique lexical lists.

Conflicts are sorted by `(reason, canonical-or-empty, record_ids)` and have
exactly `reason`, `canonical_identifier`, and `record_ids`. Collision conflicts
group every colliding ID. Reserved conflicts group all records using that
reserved key. Invalid conflicts are one row per record with null canonical.
Return exactly `{"records": [...], "conflicts": [...]}`.
