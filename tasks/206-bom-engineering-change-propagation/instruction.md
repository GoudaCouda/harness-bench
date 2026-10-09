# Recover an approved ECN across a multi-level configuration baseline

You are the manufacturing configuration analyst for an offline production
cell. Approved `ECN-442` replaces a connector inside an actuator, but a prior
propagation attempt crashed after inserting one target baseline and changing
one work order incorrectly. Recover the protected SQLite configuration store,
propagate the released where-used chain, and stage a reviewable local result.
Do not release engineering, move inventory, alter a physical kit, direct the
shop floor, or place a supplier order.

Begin with:

```bash
python3 bomctl.py inspect
```

Then use `bomctl.py query` for `policy`, `change`, `work-orders`, `bom`, and
`journal`, and run `python3 bomctl.py impact ECN-442`. Inspect
`policy/ecn_policy.json`, signed-off change evidence, work-order evidence, and
the real SQLite tables. The approved ECN, released BOM graph, protected source
revision, serial/lot effectivity, issued material, and approved-substitute list
are separate authorities. Do not infer effectivity from work-order status.

Create `ecn_recovery_plan.json` with exactly these top-level fields:

```json
{
  "schema_version": 1,
  "recovery_id": "ECNREC-20260819-442",
  "ecn_id": "ECN-442",
  "source_checkpoint": "derived protected-source checkpoint",
  "baseline_changes": [],
  "work_order_decisions": [],
  "external_actions_executed": false
}
```

Include one `baseline_changes` row for every item revision in the complete
released where-used closure. Each row has exactly:

```text
item_id, from_revision, to_revision, where_used_path, changed_line_no,
from_component, from_component_revision, to_component,
to_component_revision, quantity, approved_substitutes, evidence_refs
```

Include one `work_order_decisions` row for every protected work order. Each row
has exactly:

```text
work_order_id, end_item, serial_or_lot, effectivity_basis, effectivity_value,
effective, status, kit_state, issued_component, from_revision, to_revision,
disposition, local_mutations, evidence_refs, external_action
```

Use policy vocabulary verbatim. `approved_substitutes`, `local_mutations`, and
`evidence_refs` are sets for comparison. Evidence references are stable local
`file#record` locators. `external_action` is always `none`. New BOM revisions
are local `pending_configuration_review` baselines: retain every released and
as-built revision. Do not carry the old part's substitute to the new part;
carry only the explicitly approved new-part substitute.

Respect irreversible boundaries. An assembled pre-effectivity unit remains its
as-built revision. A post-effectivity kit with the old component is held for
controlled re-kit, but this recovery must not claim or perform a material
return. An unissued post-effectivity order adopts the new baseline. A
pre-effectivity lot keeps its existing kit. A post-effectivity kit may keep an
issued component only when it is an approved substitute for the new part.

Use the guarded workflow rather than hand-editing SQLite or generated receipts:

```bash
python3 bomctl.py preview ecn_recovery_plan.json
python3 bomctl.py apply ecn_recovery_plan.json
python3 bomctl.py verify ecn_recovery_plan.json
python3 bomctl.py stage ecn_recovery_plan.json
python3 bomctl.py replay ecn_recovery_plan.json
```

On a failed preview, `checks.baseline_changes.objects` and
`checks.work_order_decisions.objects` report pass/fail by candidate object and
field. Their `evidence_categories` distinguish the missing local authorities;
they never supply replacement values. Correct only the reported candidate
fields by returning to the cited policy, evidence, and SQLite records.

`apply` restores the interrupted journal before atomically writing the complete
configuration change. The stable recovery ID and protected source checkpoint
identify this recovery. Reordering baseline rows, work-order rows, evidence
references, mutation sets, or substitutes, and changing JSON formatting, is the
same semantic plan and must replay as a byte-stable no-op. A stale checkpoint or
a different semantic plan for the same recovery ID must be rejected before any
write.

Finally write `engineering_handoff.md` for configuration control and production
planning. Explain approval authority, every where-used revision, serial and lot
effectivity, each work-order disposition, substitute handling, restoration of
the partial journal, exact verification, internal staging, and semantic replay.
State that no release, shop-floor or physical-kit action, inventory movement,
supplier order, or other external action occurred.

Keep policy, evidence, controller, released baselines, as-built identity, and
protected source metadata unchanged. Work offline.
