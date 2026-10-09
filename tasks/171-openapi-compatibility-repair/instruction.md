# Repair directional OpenAPI compatibility analysis

An API release gate applies request compatibility rules to responses and
ignores read/write annotations and discriminator mappings. Work only in
`/workspace/repo`.

Read `docs/api_compat_contract.md`, inspect old/new normalized schemas, policy,
runner, and public tests, then repair `src/api_compat.py` as a general pure
implementation. Run public tests and `python bin/check_compatibility.py`;
re-parse both files in `out/`. Write `COMPATIBILITY_NOTES.md` covering request
and response variance, active `readOnly`/`writeOnly` fields, additions/removals,
requiredness, types, nullability, enum subset direction, discriminator
requiredness/mappings, policy effects, precedence, commands/results, and the
offline/no-deployment boundary.

Do not contact an API, registry, or deployment system, and do not claim a live
client test, rollout, or production compatibility decision.
