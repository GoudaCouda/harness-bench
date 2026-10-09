# Repair notes

The planner uses the captured `core.ignoreCase` behavior instead of guessing from the host. A case-only rename or cycle is broken with a deterministic, collision-free temporary hop before the final `git mv` destination. The full batch is validated first: tracked stage-0 sources must be exact, destinations cannot overwrite non-sources, and path/OID records must be canonical. Final entries preserve each object ID through every hop.

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`; all tests pass. Residual risk remains when an executor applies the plan to a changed working tree or index, so it must recheck status, filesystem comparison, index OIDs, and the staged rename diff. No `git mv`, force overwrite, reset, clean, commit, or push was performed.
