# Watch recovery contract

Implement recover_watches(watches, policy) without mutation, I/O, clocks, or
environment access. Treat every Kubernetes resourceVersion as an opaque
non-empty ASCII string: equality may identify an immediate replay, but numeric
or lexical ordering is forbidden. Compaction is known only from GONE (HTTP
410) evidence returned by the API server.

Policy has exactly positive integer max_attempts and boolean
require_initial_bookmark. Booleans are not integers. Watches are sorted by
unique lowercase token watch_id. Each exact record has mode
(watch/streaming_list), nullable opaque requested_rv, nullable rv_match
(Exact/NotOlderThan), booleans send_initial_events, allow_bookmarks, and
initial_complete, nullable opaque last_applied_rv, outcome
(EVENT, BOOKMARK, GONE, EOF, ERROR), nullable event_type
(ADDED, MODIFIED, DELETED), nullable opaque event_rv, and positive integer
attempt.

Streaming-list mode requires send_initial_events, NotOlderThan, and bookmarks;
ordinary watch forbids initial events and starts complete. EVENT alone has event
type and RV. BOOKMARK alone has an RV. Other outcomes have neither.
initial_complete false is valid only for streaming lists.

Return decisions in order with exactly watch_id, action, reason, nullable
next_rv, boolean next_initial_complete, and boolean reset_state.

1. GONE is relist / gone, clears the cursor and initial state, and resets.
2. EVENT whose opaque RV equals the last applied RV is ignore /
   duplicate_event. Any different cursor is the next ordered event supplied by
   the captured stream: use apply_initial before streaming-list completion or
   apply_event afterward, and checkpoint that exact opaque RV.
3. BOOKMARK is block / unexpected_bookmark when bookmarks were not requested.
   Otherwise it is checkpoint / bookmark, stores the exact bookmark RV, and
   marks a streaming list complete when policy requires the initial bookmark.
   A bookmark is progress metadata, never an object mutation.
4. EOF and ERROR first block on attempt >= max_attempts with attempt_budget.
   With a checkpoint they resume_watch using reason eof or error and the exact
   last cursor. Without one they relist / missing_checkpoint, reset state, and
   return null RV.

Ignore/block decisions retain cursor and completion and never reset. Summary is
exactly watch_count, apply_initial, apply_event, ignore, checkpoint,
resume_watch, relist, block, and state_resets.
