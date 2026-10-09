# SEC-2418: retire the catalog slug 6.x dependency

Security engineering has approved `python-slugify` version 8 and later within
the 8.x line. The service must not admit version 9 without a separate review.
No other runtime dependency is approved by this ticket.

The ingestion API is already used by scheduled jobs, so preserve
`make_slug(title, preserve_unicode=False, separator="-")`, including positional
callers and the existing defaults.

Compatibility policy:

- titles are strings; a non-string title is rejected with `ValueError` instead
  of being silently coerced;
- an empty title is valid and produces an empty key;
- the supported separators are one-character `-` and `_` values; other values
  are rejected with `ValueError`;
- the default output is ASCII and lower-case;
- `preserve_unicode=True` retains Unicode letters;
- punctuation, whitespace, and legacy underscore runs form one separator, not
  empty path components; and
- both the Unicode choice and requested separator must reach the dependency.

Remove the developer fallback. Production behavior must come from the declared
package so that dependency fixes and future audits have one implementation to
inspect. Do not vendor the package or add a network-dependent path.
