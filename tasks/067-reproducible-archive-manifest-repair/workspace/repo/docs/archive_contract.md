# Reproducible archive-member contract

`canonical_archive_manifest(entries, source_date_epoch, build_root)` returns a
list of canonical member records and performs no filesystem write.

- `source_date_epoch` is a non-negative integer, not a boolean. Values after
  `4354819198` are invalid. ZIP timestamps are clamped to the 1980 lower bound
  `315532800` and rounded down to an even second.
- `build_root` is a non-empty POSIX relative path with no empty, `.`, `..`, or
  backslash component. Every input path must be strictly below it.
- Each entry has exactly `path`, `kind`, `sha256`, `executable`, and `mtime`.
  `kind` is `file` or `dir`; symlinks and special files are rejected.
- Output paths strip `build_root`, use `/`, and directories end in `/`. Empty,
  absolute, dot-segment, backslash, or duplicate canonical members are invalid.
- File SHA-256 values are 64 lowercase hexadecimal characters. Directories use
  null SHA-256 and cannot be executable. Input mtimes are ignored.
- Canonical modes are decimal `493` (`0755`) for directories and executable
  files, otherwise `420` (`0644`). Members sort by canonical path.
- Each output record has exactly `path`, `kind`, `sha256`, `mode`, and
  `timestamp`.

The downstream writer must consume this ordered manifest without reintroducing
host paths, current time, source modes, locale ordering, or duplicate names.
