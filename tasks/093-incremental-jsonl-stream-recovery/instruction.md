# Repair incremental JSONL stream recovery

A local ingestion worker resumes at the wrong offsets, emits duplicates after
replay, and loses a partial record when the source rotates.

Work only in `/workspace/repo`. Read `docs/stream_contract.md`, inspect the
checkpoint, segments, runner, and public tests, then repair
`src/stream_consumer.py` as a general pure implementation. Run the unit tests
and `python bin/replay_stream.py`. The final run must create records,
quarantine, and checkpoint JSON outputs; re-parse all three. Create
`STREAM_NOTES.md` explaining offsets, pending fragments, newline parsing,
duplicate IDs, malformed lines, rotation, EOF, validation, immutability, exact
commands, and results.

Do not edit protected evidence, use filesystem/network/process capabilities
from the consumer, include raw quarantined content, or claim a live ingestion.
