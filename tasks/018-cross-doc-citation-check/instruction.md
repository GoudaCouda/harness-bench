The Q2 support-operations report is at publication review. Audit its inline
claims and References section against the local source package and citation
registry. Read `review_context.md` first, then reconcile `report.md`,
`appendix.md`, and every file under `sources/`.

The registry controls active citation IDs; a plausible title or a source that
supports a nearby metric is not enough. Preserve the report's claim locations
and distinguish a wrong References entry from a wrong, retired, or absent
inline citation.

Create:

- `citation_audit.csv` with header
  `citation_id,location,issue,expected_source,recommended_fix`. Include exactly
  one row for each distinct citation defect. Use a concrete location such as
  `Claim C` or `References`. `expected_source` is the workspace-relative source
  that supports the repair; use `N/A` when a retired References entry should
  simply be removed. Describe the problem and affirmative repair in ordinary
  editorial language.
- `fixed_references.md`, the complete corrected References section, using
  `[S1] title - sources/file.md`. Include every source needed by the four
  published claims, use only active IDs, and preserve the registry titles and
  paths.

Do not rewrite source evidence, invent a citation, or reuse an ID marked retired;
never reuse an ID marked retired. Do not add
audit rows for valid citations, or use the network.
