# Repair Python wheel selection

A deployment planner is choosing the first release asset whose filename looks
roughly right. It has selected incompatible ABI and platform builds. Repair the
offline selector before an installer or package index is called.

Work only in `repo/`. Preserve `select_wheel(target, assets)`. Read the tag
contract, broken implementation, visible release batches, and public tests.

Deliver repaired `repo/src/wheel_selector.py`, ordered
`repo/selection_report.json` containing every visible `case_id` and exact
result, and `repo/SELECTION_NOTES.md`. Explain wheel filename parsing,
compressed-tag expansion, ordered interpreter/ABI/platform compatibility,
build-tag precedence, yanked handling, ambiguity, verification, and residual
installer risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. Do not query a package index, download or install a wheel, publish a
release, mutate an environment, or claim an external action.
