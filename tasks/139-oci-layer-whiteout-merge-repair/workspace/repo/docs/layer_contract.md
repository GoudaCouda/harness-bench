# OCI layer merge contract

Implement `merge_layers(layers, policy)` as a pure function. Validate the whole
batch before constructing state; malformed input raises `ValueError`.

`layers` is an ordered nonempty list of exact objects `{digest, entries}` with
unique nonempty digest strings. Each entry has exactly `{path, kind, digest,
target, mode}`. Paths are nonempty relative POSIX paths: reject absolute paths,
empty/dot/dot-dot segments, backslashes, control characters, and trailing `/`.
Paths are unique within a layer. `kind` is `file`, `dir`, or `symlink`. File
requires a nonempty digest and null target; dir requires null digest/target;
symlink requires null digest and a nonempty relative target. Mode is an integer
0..511. Symlink target resolution from its parent must remain inside root and
must not traverse a symlink already represented by an ancestor.

File entries whose basename begins `.wh.` are OCI markers and must have kind
`file`, digest `sha256:empty`, null target, and mode 0. `.wh.NAME` removes the
lower-layer path `NAME` in the same parent and all descendants. The exact
`.wh..wh..opq` marker removes all lower-layer children and descendants of its
parent, not the parent. Reject other `.wh.` names. Apply every marker before
normal entries in that layer regardless of input order. Markers never appear in
the final rootfs and never remove entries from their own layer.

For normal entries, replacing a lower directory with file/symlink removes all
descendants. Replacing a lower file/symlink with directory removes that node.
Every non-root ancestor must be a directory. Missing ancestors are created as
implicit directories with mode `policy.implicit_dir_mode`, null digest/target,
and the current layer digest. A same-layer non-directory ancestor makes the
manifest invalid rather than order-dependent.

Return `{rootfs, audit}`. Each final row has `path`, `kind`, `digest`, `target`,
`mode`, `layer_digest`, and `implicit`. Sort by path. Audit has `layer_count`,
`entry_count`, sorted unique `removed_paths`, `whiteout_count`,
`opaque_whiteout_count`, and `implicit_directory_count`. This is manifest-only;
no archive or filesystem capability is allowed.
