# Localization repair notes

Locale tags are canonicalized before lookup, and the fallback chain honors an
explicit parent before ordinary subtag truncation. Catalog lookup tests key
presence rather than truthiness, so an intentionally empty translation wins
while a missing key continues toward root. Parent cycles and canonical key
collisions fail closed.

Plural selection uses the requested language, checks an exact numeric selector
first, applies the bounded English, French, or Russian cardinal rule, and falls
back to `other` when the chosen category is unavailable. Interpolation parses
each placeholder, supplies `{count}` explicitly, and rejects missing variables
or malformed braces rather than shipping unresolved text. Verification used
`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`; all tests
passed successfully. Integration risk: this bounded implementation supports only
three cardinal rule sets, so additional locales require versioned CLDR data
rather than guessed rules. No translation publication or rollout was performed.
