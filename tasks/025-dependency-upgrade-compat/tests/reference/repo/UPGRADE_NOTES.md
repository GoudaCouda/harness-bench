# Dependency upgrade handoff

## Decision

`python-slugify` is the only runtime dependency and now uses the approved
`>=8,<9` range in `pyproject.toml`. The change to `slugger.py` removes the local
fallback and delegates directly to that package. It preserves the existing
three-argument public function and explicitly forwards both the Unicode choice
and separator. No unrelated package, vendored code, or network path was added.

## Verification

I ran the repository's immutable public suite from the repository root with:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider
```

All three public tests passed against the task image's installed 8.x package. I
also exercised an invalid separator and non-string title locally and observed
the documented `ValueError` behavior. This was local verification only; no
deployment or production action was performed.

## Compatibility risks and rollback

The main compatibility risks are Unicode transliteration versus preservation,
custom separator forwarding, punctuation collapse, and callers that previously
relied on implicit coercion. The wrapper keeps those decisions explicit and
rejects unsupported values before entering the dependency.

If a downstream regression is found during review, hold the release and pin the
dependency to the task image's tested, approved 8.0.4 version. Revert only an
application-wrapper change that has first been retested against that approved
version; if no prior wrapper is compatible, keep the rollout blocked and
prepare a forward compatibility fix. This is a proposed rollback and
containment procedure, not an action already performed.
