# Repair certificate path selection contract

Build all acyclic certificate paths from one leaf to configured trust-anchor ids using issuer/subject equality. Every certificate must be valid in the half-open time window; every issuer above the leaf must be a CA; a CA `path_len` limits the number of CA certificates below it; and the leaf must contain the requested DNS name. Choose the shortest valid path, then lexical id sequence. Report every valid path and rejected path/reason. Return `status,selected_path,valid_paths,rejected`; malformed intervals and duplicate ids raise `ValueError`.

The output has exactly `status,selected_path,valid_paths,rejected`. Status is `selected` or `no_valid_path`. Every rejected record has exactly `path,reason`; reason is `issuer_missing`, `time_invalid`, `issuer_not_ca`, `path_length`, or `name_mismatch`. Rejections are sorted by path and then reason.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.
