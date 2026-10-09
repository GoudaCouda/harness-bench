# Bibliography contract

1. Entries start at `@type{key,`.
2. The first time a key appears it is kept.
3. Later entries with that key are renamed to `{key}-{n}` where `n` is the
   1-based occurrence count (so the second is `{key}-2`).
4. `duplicates` lists original keys that occurred more than once, sorted.
5. `renamed` maps new keys to the original key.
6. Cites in `paper.tex` that still name the original key refer to the first
   entry; do not rewrite the tex file.

Do not invent keys.
