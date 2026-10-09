# Repair MIME multipart decoding and attachment selection repair notes

The repaired `plan_mime_multipart_decoding` follows the documented protocol contract for nested boundaries, transfer encodings, filename parameters, duplicate content IDs, malformed parts, and bounded decode failures. It preserves stable identity ordering, rejects malformed and duplicate input, separates missing evidence from explicit values, and leaves protected input unchanged.

Verification: `python3 -m unittest discover -s tests -v` passed, `python3 bin/run_repair.py` completed, and `out/result.json` was re-opened and parsed. Boundary cases include precedence overlap, exact limits, stale or conflicting state, deterministic replay, and fail-closed invalid input. This was an offline local repair; no external service, production mutation, deployment, message, or irreversible action was performed.
