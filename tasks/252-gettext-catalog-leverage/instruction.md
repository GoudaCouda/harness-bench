# Leverage the mill gettext catalog

Incoming mill UI strings should reuse exact catalog translations. Read
`docs/catalog_contract.md`, `catalog.po`, and `incoming.json`.

Write `leverage.json` using the `string_id` values already present in
`incoming.json`. Create `CATALOG_NOTES.md` covering msgid matching, empty
msgstr, untranslated rows, one verification step, and one remaining risk.

Do not modify the catalog, contact a translation service, or claim strings
were published.
