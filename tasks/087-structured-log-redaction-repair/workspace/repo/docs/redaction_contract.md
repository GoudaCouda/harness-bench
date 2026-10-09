# Structured log redaction contract

Implement `redact_event(event, policy)` in `src/redactor.py`.

## Inputs and result

`event` must be a JSON object whose keys are strings. Values may be JSON null,
booleans, finite integers/floats, strings, arrays, or objects, to at most 12
container levels. Reject every other value with `ValueError`.

`policy` is an object with exactly these fields:

- `sensitive_keys`: a non-empty list of unique non-empty strings;
- `replacement`: the exact non-empty replacement string;
- `text_assignments`: a non-empty list of unique non-empty names.

Policy names and event keys compare with Unicode `casefold()`. Reject duplicate
names after case folding and reject a replacement that case-insensitively equals
a sensitive key or assignment name.

Return exactly:

```json
{"event": {}, "redactions": [{"path": "/field", "kind": "sensitive_key"}]}
```

Do not mutate either input. Object member order is preserved. Findings are in
depth-first traversal order; at each string, text substitutions are recorded in
left-to-right match order. Paths use JSON Pointer escaping (`~` becomes `~0`,
`/` becomes `~1`) and decimal array indexes.

## Structured values

When an object key exactly matches a `sensitive_keys` name after case folding,
replace its entire value with `replacement` and add one `sensitive_key`
finding. Do not descend into the replaced value. Key matching is exact:
`token_count`, `tokenizer`, and `passwordless` are not sensitive merely because
they contain a sensitive word.

If a matched value already equals `replacement`, leave it and add no finding.

## Free text

For strings under non-sensitive keys, replace these non-overlapping forms:

1. `Bearer` (case-insensitive), one or more spaces, then a non-empty token made
   from ASCII letters, digits, `.`, `_`, `~`, `+`, `/`, `-`, or `=`. Preserve
   the original `Bearer` spelling and spaces; replace only the token. Kind:
   `bearer_token`.
2. An exact `text_assignments` name at an ASCII word boundary, optional spaces,
   `=`, optional spaces, then a non-empty value ending before whitespace,
   comma, or semicolon. Preserve name, spaces, and `=`; replace only the value.
   Matching is case-insensitive. Kind: `assignment`.
3. URL userinfo of the form `scheme://user:password@`, where scheme uses ASCII
   letters/digits/`+.-`, and user/password are non-empty with no whitespace,
   `/`, or `@`. Preserve `scheme://`; replace the complete `user:password`.
   Kind: `url_userinfo`.

Choose the earliest next match. If alternatives start together, use the order
above. Continue after the matched source span, so replacements are not scanned
again. A value already equal to `replacement` is not a credential match.

Do not redact emails, request/user/trace IDs, ordinary prose, or harmless
substrings not matching these forms.
