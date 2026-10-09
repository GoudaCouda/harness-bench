# Repair backup chunk garbage-collection reachability contract

Compute backup chunk reachability. Roots are explicitly retained snapshots plus every held or partial snapshot; follow parent ancestry and chunk references. Tombstoned snapshots are not roots unless retained/held. Missing parent snapshots or chunks block all deletion, put every known chunk in `keep_chunks`, and leave `delete_chunks` empty. Otherwise delete only chunks unreachable from every root. Return sorted keep/delete chunks, reachable snapshots, missing ids, and blocked flag. Duplicate ids, unknown retained roots, and malformed snapshot state raise `ValueError`.

The output object has exactly `keep_chunks,delete_chunks,reachable_snapshots,missing,blocked`; the four collections are sorted id lists and blocked is exactly whether missing is nonempty.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.
