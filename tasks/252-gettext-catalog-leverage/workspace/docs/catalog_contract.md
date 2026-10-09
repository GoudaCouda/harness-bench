# Catalog contract

1. `catalog.po` contains one-line `msgid` / `msgstr` pairs whose values are
   JSON strings.
2. An incoming `source` leverages a translation only when it equals a `msgid`
   and that `msgstr` is non-empty.
3. `translations` maps those `string_id`s to the `msgstr`.
4. `untranslated` lists the other `string_id`s in input order.

Do not invent string identifiers. Do not fuzzy-match.
