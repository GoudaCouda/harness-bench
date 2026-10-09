# Incremental JSONL recovery contract

Implement pure `consume_segments(checkpoint, segments, policy)` without
mutating inputs. `policy` is exactly positive `max_pending_chars`.
`checkpoint` is exactly non-empty `file_id`, non-negative `offset`, string
`pending`, and non-negative integer `last_record_id`; pending contains only
printable ASCII other than newline and its length cannot exceed the policy.

Each segment has exactly non-empty `file_id`, non-negative `start`, ASCII
`data`, and boolean `eof`. Segments are ordered deltas. For the current file,
start must equal checkpoint offset. A different file ID is a rotation and must
start at zero. After rotation it becomes current, so later starts use its
offset. Any structural, offset, type, ASCII, or pending-limit violation raises
`ValueError` before consuming any segment.

On rotation, quarantine an existing pending fragment as
`truncated_on_rotation` at its starting offset, without raw content, then clear
it. Append segment data to pending, advance offset by exactly `len(data)`, and
consume every newline-terminated logical line. A terminal `\r` before `\n` is
removed. Empty lines are quarantined as `empty_line`. Parse JSON objects with
exactly positive integer `id` (not boolean) and `payload`, where payload is
finite JSON data. Parse/schema failures are quarantined as `malformed_record`.
Quarantine entries contain exactly file_id, offset, and reason.

Valid IDs at or below `last_record_id` are replay duplicates: emit nothing.
A higher ID is emitted as a deep copy and advances `last_record_id`; later IDs
at or below that durable high-water mark are therefore also ignored as replay. Offsets in quarantine identify the first character of the
logical line or fragment.

If `eof` is true after complete lines, a remaining pending fragment is
quarantined as `truncated_at_eof` and cleared. Return exactly records,
quarantine, and canonical checkpoint. No quarantine entry may contain content.
