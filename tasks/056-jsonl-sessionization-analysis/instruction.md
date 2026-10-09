# Build an auditable clickstream session dataset

You are the product analytics engineer. A campaign analysis is blocked by dirty JSONL, duplicate events, bot traffic, anonymous-to-login transitions, and session boundary edge cases.

Your job is to produce the session table used by analysts while conserving every rejected input line in a diagnostic ledger.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs include:
- `campaign_map.csv`
- `clickstream.jsonl`
- `session_rules.md`

## Deliverables

- `reject_ledger.csv`: Use columns line_number, event_id, reason, notes; each excluded line appears once.
- `session_summary.json`: Include total_sessions, converted_sessions, excluded_bot_users, deduped_event_ids, malformed_line_numbers, missing_timestamp_event_ids, and unknown_event_type_ids.
- `sessionization_notes.md`: Document identity stitching, the exact 30-minute boundary, campaign carry-forward, and dirty-data caveats.
- `sessions.csv`: Use columns session_id, user_key, session_start, session_end, event_count, landing_page, last_page, converted, campaign_source.

These files are a handoff to another practitioner, so choose clear prose and stable local identifiers. The named business fields are required where stated, but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Parse line by line and use the rejection precedence in session_rules.md. Only events surviving earlier filters participate in duplicate detection.
2. Sort valid events by timestamp, stitch an anonymous identity to its later login, and start a new session only after more than 30 minutes of inactivity.
3. Select the first mapped campaign in a session and carry the latest mapped source to later sessions for the same stitched user when needed.
4. Use timezone-aware timestamps and reconcile accepted plus rejected lines to the input without silently dropping data.

Keep all source evidence byte-for-byte unchanged except for a path explicitly named as an in-place deliverable. Work offline. Do not execute or claim an external, production, payment, filing, deletion, message-send, booking, or account action. Before finishing, re-open the final CSV/JSON files and reconcile their keys and totals across the handoff.
