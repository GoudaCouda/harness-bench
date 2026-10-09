# Repair the bounded cache state machine

A local metadata cache evicts the wrong entries at TTL boundaries and destroys
useful entries before discovering that a pinned-capacity write cannot fit.

Work only in `/workspace/repo`. Read `docs/cache_contract.md`, inspect the
state, operations, runner, and public tests, then repair `src/cache_engine.py`
as a general pure implementation. Do not hard-code visible keys or values.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` and
`PYTHONDONTWRITEBYTECODE=1 python bin/replay_cache.py`. The final run must create
`out/state.json` and `out/events.json`; re-parse both. Create `CACHE_NOTES.md`
covering TTL boundaries, access ordering, lexical LRU ties, pinned entries,
overwrite accounting, transactional failed puts, validation, immutability,
exact commands, and results.

Do not edit protected inputs, use filesystem/network/process capabilities from
the engine, or claim that a production cache was changed.
