# Repair localization fallback

A notification service treats intentionally empty translations as missing,
falls through the wrong parent locale, and chooses English plural rules for all
languages. Repair the local message resolver.

Work only in `repo/`. Preserve
`render_message(catalogs, parent_locales, locale, key, variables, count)`.
Create the repaired source, an ordered `render_report.json` for the visible
cases, and `REPAIR_NOTES.md` explaining parent resolution, empty versus missing,
plural selection/fallback, interpolation validation, exact verification result,
and risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`.
Do not edit catalogs, parent data, or tests, and do not claim translation
publication or production rollout.
