# Catalog notes

## Decision

Incoming sources used exact msgid matches from the PO catalog. Empty msgstr
values and missing msgid strings stay untranslated. string_id values from
the incoming list identify the rows.

## Verification

Each translated string_id equals the catalog msgstr for that exact source.

## Remaining risk

Fuzzy msgid matching would reuse a near string and hide a missing phrase.
That adapter needs a check before rollout. No translation service was
contacted.
