# Pointer contract

`resolve_pointer(document, pointer)` implements JSON Pointer:

1. An empty pointer returns `document`.
2. Any other pointer must start with `/`.
3. Split on `/` and drop the first empty token.
4. Unescape each token by replacing `~1` with `/`, then `~0` with `~`.
5. Walk dict keys or non-negative decimal array indexes.
6. Raise `ValueError` when the pointer is malformed or a member is missing.
   Test `token in current` for objects and `0 <= index < len(current)` for
   arrays; do not catch `IndexError` or `KeyError`.

Do not invent mill identifiers.
