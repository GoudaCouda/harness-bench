# Repair Kubernetes finalizer recovery ordering contract

Plan removal only for resources already marked for deletion. Protected resources, unknown finalizers, and (under foreground propagation) remaining dependents are blocked. Among eligible resources, remove child finalizers before owner finalizers; owner cycles block every remaining member. Orphan propagation does not wait for dependents. Return ordered `remove_finalizers`, id-sorted blocked reason records, and id-sorted untouched live resources. Unknown owner ids, malformed owners/finalizers, and duplicate ids raise `ValueError`.

The output object has exactly `remove_finalizers,blocked,untouched`. Each id-sorted blocked record has exactly `id,reason`, where reason is `protected`, `unknown_finalizer`, `dependents_remaining`, or `owner_cycle`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.
