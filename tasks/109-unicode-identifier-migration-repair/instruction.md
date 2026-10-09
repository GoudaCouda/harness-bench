# Repair the Unicode identifier migration

A service is moving legacy display identifiers to case-insensitive canonical
keys. The current script silently merges compatibility-equivalent accounts and
drops references to blocked records. Work only in `/workspace/repo`.

Read `docs/identifier_contract.md`, inspect records, reserved identifiers,
policy, runner, and public tests, then repair `src/identifier_migrator.py` as a
general pure implementation. Do not hard-code fixture strings or IDs.

Run the unittest suite and `python bin/migrate_identifiers.py`. The final run
must create `out/records.json` and `out/conflicts.json`; parse both again. Write
`IDENTIFIER_NOTES.md` covering NFKC case folding, syntax and length checks,
reserved keys, collision quarantine, display spelling, reference resolution,
confusable non-merging, strict validation, commands, and results.

Do not edit protected inputs, call identity services, or claim that accounts,
logins, or production keys were changed.
