# Repair a Unix permission transition plan contract

Compute creation modes and a bounded POSIX symbolic chmod transition. `create` uses explicit `requested_mode`, or 0666/0777 defaults for file/directory, then applies `umask` and clears special bits. `chmod` starts from `current_mode` and applies comma-separated clauses with optional `u/g/o`, one `+/-/=`, and `rwx`; omitted who means all. When `preserve_special` is true, chmod restores the original setuid/setgid/sticky bits after ordinary-bit changes. Return id-sorted decisions with four-digit octal mode strings, operation, and changed flag plus operation counts. Invalid modes/clauses and duplicate ids raise `ValueError`.

The output object has exactly `decisions,summary`. Each id-sorted decision has exactly `id,mode,changed,operation`; mode is a four-character octal string and operation is `create` or `chmod`. Summary has exactly `created,chmod`.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.
