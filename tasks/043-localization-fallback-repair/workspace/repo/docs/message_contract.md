# Message resolution contract

`render_message(catalogs, parent_locales, locale, key, variables, count)` returns
`{"text", "locale_used", "plural_category", "fallback_chain"}`.

- Locale tags use ASCII language/script/region subtags separated by `-` or `_`.
  Canonicalize language lowercase, four-letter script titlecase, two-letter
  region uppercase, and other subtags lowercase. Canonicalize catalog and parent
  keys too; canonical collisions are invalid.
- Build a chain from requested locale. At each step use its explicit
  `parent_locales` entry if present; otherwise remove the final subtag. End at
  `root`, included once. Cycles are invalid.
- A key present in a catalog wins even when its value is the empty string. Only
  an absent key continues fallback. If absent everywhere, raise `ValueError`.
- A message is either a string or a plural object. Plural objects contain one or
  more selectors and must contain `other`. If count is missing for a plural,
  raise `ValueError`. First match exact selector `=<count>` for integer counts;
  otherwise select the requested locale language's cardinal category:
  English: integer 1 is `one`; French: integer 0 or 1 is `one`; Russian:
  integers ending 1 but not 11 are `one`, endings 2–4 but not 12–14 are `few`,
  endings 0 or 5–9 or 11–14 are `many`; all other values/languages are `other`.
  A missing category falls back to `other`. Report the selected category or
  exact selector; plain strings report `plural_category: null`.
- String placeholders are unescaped `{identifier}` tokens. Identifiers contain
  letters, digits, or underscore and cannot start with a digit. Every token must
  be supplied by `variables`, except `{count}` may use count. Missing variables,
  unmatched braces, nested braces, non-string keys, unsupported catalog values,
  nonnumeric/bool counts, and non-scalar interpolation values raise `ValueError`.
  Extra variables are allowed. Replace values using `str` without locale number
  formatting. Inputs are immutable.
