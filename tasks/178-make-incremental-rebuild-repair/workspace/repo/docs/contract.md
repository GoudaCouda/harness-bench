# Repair an incremental build dependency plan contract

Plan a GNU-Make-like requested dependency closure. Topologically order normal and order-only prerequisites. Missing nodes or cycles block the plan. A recipe target rebuilds when phony, missing its mtime, any normal prerequisite rebuilt, or a normal prerequisite is strictly newer; order-only prerequisites affect order but never freshness. Non-recipe source nodes are not listed as rebuilds. Return exact `order,rebuild,up_to_date,missing,cycles`; all lists are deterministic. Malformed mtimes/dependencies and duplicate targets raise `ValueError`.

The output object has exactly `order,rebuild,up_to_date,missing,cycles`; all five values are deterministic lists and cycles are closed target-id paths.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.
