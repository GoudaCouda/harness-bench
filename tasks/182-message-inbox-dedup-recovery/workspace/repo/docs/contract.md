# Recover an idempotent message inbox contract

Sort inbox events by at/id. Exact full-event duplicates are ignored; reuse of an event id with different content raises `ValueError`. `(producer,epoch,seq)` with a different payload hash is a reported conflict and is never processed. Higher producer epochs reset sequence/tombstone state; lower epochs are stale. Tombstones suppress same-epoch sequence numbers up to and including their sequence. Process only strictly increasing receive sequences. Return process records, conflicts, and producer-sorted ledger. Inputs are immutable.

The output object has exactly `process,conflicts,ledger`. Each process record has exactly `producer,epoch,seq,payload_hash`; each conflict has exactly `producer,epoch,seq`. Ledger keys are producer ids in lexical order and each value has exactly `epoch,seq,tombstone`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.
