# Bibliography notes

## Decision

Duplicate BibTeX keys keep the first entry. Later collisions are renamed
`{key}-{n}` in appearance order. cite keys in the paper that still name the
original key continue to refer to the first entry.

## Verification

The rewritten .bib has unique keys and the collision report lists the
renamed later smith2020 entry.

## Remaining risk

A later cite that intended the second paper still points at the first.
That adapter needs a human check before rollout. No publisher was
contacted.
