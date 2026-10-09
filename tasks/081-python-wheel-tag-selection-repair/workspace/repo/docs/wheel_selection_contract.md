# Wheel selection contract

`target` has exactly `project`, `version`, `supported_tags`, and
`allow_yanked`. Project is a canonical lowercase name joined by hyphens,
version is a non-empty wheel-safe value, and `allow_yanked` is Boolean.
`supported_tags` is a non-empty, duplicate-free, most-preferred-first list of
exact `python-abi-platform` triples. Each component is one alphanumeric or
underscore tag, not a compressed tag.

Every `assets` record has exactly `filename`, `sha256`, `size`, and `yanked`.
The inventory is authoritative and must be validated in full. Filenames are
basename-only wheel names with five fields, or six when a build tag is present:
`distribution-version(-build)-python-abi-platform.whl`. Distribution uses
wheel normalization, version must equal the target exactly, build starts with
digits, and tag fields may contain dot-compressed alternatives. Expanding a
wheel tag forms the Cartesian product of its Python, ABI, and platform tags.

Ignore well-formed wheels for other projects or versions. Unless policy allows
it, ignore yanked matching wheels. A compatible wheel's rank is the earliest
exact expanded triple in `supported_tags`; substring and host inference are
forbidden. Lower compatibility rank wins. At one rank, the numerically and
then lexically greatest build tag wins, with an absent build below any positive
build. If multiple distinct assets remain tied, return `manual_review` rather
than selecting arbitrarily. Otherwise return `select`; if none match, return
`no_compatible`. Result schemas are exercised by the visible cases and public
tests. The function is pure and may import only `re`; it never queries, downloads,
installs, publishes, or mutates an environment.
