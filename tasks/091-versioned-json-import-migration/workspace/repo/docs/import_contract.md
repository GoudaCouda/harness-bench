# Versioned settings import contract

Implement `migrate_batch(records, defaults)` in `src/import_migrator.py`. It is
a pure function and must not mutate either argument.

`defaults` has exactly `retry_limit` (integer 0 through 10, not boolean) and
`region` (non-empty string). `records` is a list of objects with exactly
`source_id` and `document`. Source IDs are unique non-empty strings and each
document is an object. Invalid batch structure, defaults, duplicate source IDs,
or a non-object document raises `ValueError` before any migration.

Each document has an integer `schema_version` (boolean is invalid). A malformed
known-version document is rejected in the returned ledger rather than raising.
An unsupported version is rejected with reason `unsupported_version`; any
other document problem uses `invalid_document`. Rejections contain only
`source_id` and `reason` and never echo source values.

All known versions produce this canonical v3 document, with exactly these keys:

```json
{
  "schema_version": 3,
  "identity": {"name": "..."},
  "connection": {"endpoint": "https://...", "retry_limit": 3, "region": "... or null"},
  "enabled_features": ["sorted", "unique"],
  "extensions": {"x-owner": "preserved JSON value"}
}
```

Names and HTTPS endpoints are non-empty strings; endpoints contain no
whitespace. Retry limits are integers from 0 through 10, excluding booleans.
Regions are null or non-empty strings. Extensions are objects whose keys are
non-empty strings beginning `x-`; values must be finite JSON data with string
object keys and at most eight container levels. Preserve extension values
without aliasing caller data.

## Version 1

Allowed keys are `schema_version`, `name`, `endpoint`, `retries`, `region`, and
`extensions`; the first three are required. Missing `retries` uses
`defaults.retry_limit`, while explicit null means zero retries. Missing
`region` uses `defaults.region`, while explicit null remains null. Version 1
has no enabled features.

## Version 2

Allowed keys are `schema_version`, `identity`, `connection`, `features`, and
`extensions`; the first four are required. `identity` has exactly `name`.
`connection` has exactly `endpoint`, `retry_limit`, and optional `region`.
Missing connection region uses the default; explicit null remains null.
`features` is an object of non-empty feature names to booleans. Canonical
`enabled_features` contains the true names once each in lexical order.

## Version 3

The document must already use exactly the canonical keys and nested shapes.
Accept a unique list of non-empty feature names and canonicalize its lexical
order. A second migration of canonical output must be byte-for-byte equal as
JSON data.

Return exactly `{"migrated": [...], "rejected": [...]}`. Migrated entries are
`{"source_id": ..., "document": ...}`. Preserve input order independently in
both lists.
