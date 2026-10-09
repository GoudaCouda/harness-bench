# Kubernetes watch recovery handoff

The repaired planner treats every resourceVersion as an opaque cursor. It never
uses numeric or lexical ordering: a different cursor from the ordered event
stream is new progress, while an event whose cursor exactly equals the last
applied cursor is a duplicate. Compaction is not inferred locally. Only the API
server's 410 Gone evidence causes relist, cursor clear, initial-state reset, and
restart from a new list result.

Ordinary watch inputs preserve Exact or NotOlderThan request semantics and begin
with initial state complete. A streaming list requires NotOlderThan,
send-initial-events, and bookmark support. Initial events are applied with
apply_initial. A permitted BOOKMARK checkpoints its exact opaque cursor and,
when required by policy, marks initial delivery complete; it is progress
metadata and never an object mutation. An unrequested bookmark is blocked.

EOF and ERROR use the last checkpoint for resume. Without a checkpoint the
planner relists and resets rather than inventing a resourceVersion. Attempt
budget exhaustion blocks before another reconnect. A 410 Gone always relists
because server compaction evidence overrides local resume state.

Verification ran python -m unittest discover -s tests and
python bin/recover_watches.py. Unit tests passed; decisions and summary parsed
as JSON. The visible replay applies one event, ignores one equal-cursor
duplicate, checkpoints one initial bookmark, resumes two interrupted watches,
relists the 410 case, and records one state reset.

This was offline deterministic replay only. No Kubernetes API, cluster
credentials, socket, live list, watch, relist, controller update, or production
validation was used or claimed.
