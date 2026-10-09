# Release version contract

`release_tag` and `previous_tag` are strict release identifiers: an optional
leading `v`, three non-zero-padded numeric components, and optionally
`-alpha.N`, `-beta.N`, or `-rc.N`. Build metadata is not accepted. The new
release must have strictly greater SemVer precedence than the previous release.

Every manifest record has exactly `path`, `ecosystem`, `current`, and
`publish`. Paths are safe relative paths and unique. Supported ecosystems and
required basenames are `python`/`pyproject.toml`, `npm`/`package.json`, and
`cargo`/`Cargo.toml`; `publish` is Boolean. Current values must use canonical
ecosystem spelling.

npm and Cargo use the canonical tag without `v`. Python maps alpha, beta, and
release-candidate suffixes to `aN`, `bN`, and `rcN`. Return the canonical
release and previous identity, a prerelease flag, and path-sorted changes with
`from`, `to`, `action` (`update` or `noop`), ecosystem, and publish flag. Any
invalid record blocks the entire plan; never return a partial manifest set.
