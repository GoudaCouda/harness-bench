# Incremental stream handoff

The checkpoint offset counts every accepted ASCII character, including a
pending fragment. Continuation starts exactly at that offset and joins pending
text before newline parsing; CRLF removes the terminal carriage return. Valid
record IDs at or below the last emitted ID are duplicate replay and are not
emitted again.

Malformed JSON, invalid record shapes, and empty lines enter a metadata-only
quarantine with file ID, starting offset, and reason—never raw content. File
rotation quarantines an old partial record as `truncated_on_rotation`, resets
the new offset to zero, and retains the last record ID. EOF similarly records
`truncated_at_eof`. Complete preflight validation covers segment offsets,
rotation starts, ASCII, pending limits, exact shapes, and integer/boolean
distinctions before replay. Deep copies keep inputs immutable.

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` passed, and
`PYTHONDONTWRITEBYTECODE=1 python bin/replay_stream.py` succeeded. Records,
quarantine, and checkpoint outputs were parsed again. No live ingestion ran.
