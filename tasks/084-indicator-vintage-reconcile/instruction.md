# Reconcile a paginated indicator release with its prior vintage

You are the data analyst updating a country-comparison workbook before a
planning meeting. The downloaded release is split across pages and contains
several similarly named series. The existing workbook was built from an older
vintage, so the handoff must make revisions auditable rather than silently
overwriting them.

Use only the local files in `$WORKSPACE`:

- `request.md`
- `metadata.json`
- `page1.json`, `page2.json`, and `page3.json`
- `prior_vintage.csv`

Prepare these files in `$WORKSPACE`:

- `indicator_panel.csv` — one row per requested country and year, with columns
  `country,year,indicator,unit,value,revision_from_prior` in that order.
- `vintage_state.json` — the selected `indicator` and `unit`, source `vintage`,
  the identifiers of every `pages_consumed`, final `row_count`, and the
  `2025_leader` among the requested countries.
- `revision_note.md` — a short analyst handoff identifying the chosen series,
  page coverage, material signed revisions from the prior vintage, and the
  scope of the 2025 comparison.

Match records by country, year, and indicator code. Do not substitute a
current-price or differently rebased series because its label looks similar.
Only requested countries and years belong in the panel. A blank prior value
means that no comparable earlier observation was supplied; it is not a zero
revision. Derive the state file from the completed panel, then parse and
reconcile all three deliverables before finishing.

Do not modify the supplied evidence, use the network, or claim that any
external report or production system was updated.
