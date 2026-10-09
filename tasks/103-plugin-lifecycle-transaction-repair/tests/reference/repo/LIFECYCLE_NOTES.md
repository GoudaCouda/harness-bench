# Plugin lifecycle handoff

The engine validates the complete catalog and active dependency closure before
planning. Enable requests add the transitive dependency closure; disable
requests add active reverse dependents. Deterministic topological order uses
lexical ties for activation and the reverse order for deactivation, so
dependents leave before requirements.

A successful commit rebuilds registrations from hook ownership for the final
active set, removing stale and duplicate rows. Generation increments only when
active or registration state changes; a canonical no-op keeps both generation
and journal reason stable. Unknown or intersecting requests are rejected before
attempts. Injected activation or deactivation faults occur before that plugin
changes and roll back every prior attempt in reverse order, preserving the
input state byte-equivalently.

Strict validation covers graph cycles, missing dependencies, duplicate hook
owners, active closure, malformed registrations, and all request/fault lists.
`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` passed, and
`PYTHONDONTWRITEBYTECODE=1 python bin/reconcile_plugins.py` succeeded. I parsed
both output files again. This offline registry simulation did not import,
install, activate, or disable plugins in a live host.
