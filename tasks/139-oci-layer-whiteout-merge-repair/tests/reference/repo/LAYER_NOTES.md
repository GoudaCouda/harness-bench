# OCI layer reconstruction handoff

The merger validates every layer before state changes. It tracks the layer that
introduced each path. An explicit whiteout .wh.NAME removes that lower-layer path and descendants;
an opaque .wh..wh..opq removes lower children of its parent. All markers run
before normal entries regardless of manifest order, and neither marker can
erase additions from its own layer.

Type replacement is explicit: replacing a directory with a file or symlink removes its descendants. Replacing
a lower non-directory with a directory removes the incompatible node. Missing
ancestors become deterministic implicit directories, while a same-layer
non-directory ancestor is invalid. The final state records source layer, mode,
digest or link target, and whether an ancestor was implicit.

Paths reject absolute, dot, dot-dot, backslash, control, and duplicate forms.
Relative symlink targets are resolved from their parent, must remain under root,
and cannot traverse a represented symlink ancestor.

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` passed.
`PYTHONDONTWRITEBYTECODE=1 python bin/merge_layers.py` succeeded, and both JSON
outputs were parsed again. This was manifest-only analysis: no archive was
extracted, no image was mounted, and no container runtime or live filesystem was changed.
