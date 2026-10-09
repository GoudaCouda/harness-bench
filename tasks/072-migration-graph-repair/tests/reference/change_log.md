# Change log — Repair a split migration graph without losing reversibility

The split heads `orders.0007_add_region` and
`orders.0007_backfill_region` were both accepted. The minimal repair creates
one merge head, `orders.0008_merge_region`, with both branches as merge
dependencies; neither shipped branch is deleted or rewritten.

The data operation uses the historical model, fills only null regions, and is
idempotent on repeat. Local validator evidence covers both the fresh replay and
the upgrade replay from 0006. The reverse path uses
`restore_null_region`, restoring only values introduced by this migration and
preserving pre-existing manual values.

Validation was performed locally. Inputs other than the declared config stayed
unchanged, and no production change was executed.
