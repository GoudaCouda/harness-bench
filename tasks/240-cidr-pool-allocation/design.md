# Task Design: `240-cidr-pool-allocation`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** IPAM engineer allocating mill prefixes
- **Trigger:** four prefix requests compete for 10.8.0.0/22
- **Objective:** allocate aligned subnets largest-first without overlap
- **Irreversible boundary:** no router update or prefix publish is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| HB-S200-BOUNDED-ALLOCATION | bounded-capacity scheduling family | https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/ | 2026-09-11 | Grounds refusing work that does not fit remaining capacity |
| OCI-CONTENT-ADDRESSABLE | OCI image spec content addressability | https://github.com/opencontainers/image-spec/blob/main/descriptor.md | 2026-09-11 | Motivates exact address identity for allocated blocks |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file and record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** IPv4 prefix arithmetic makes first-fit IPAM executable without a network controller.

## 3. Real-workflow justification

IPAM fails when requests are served in file order or when a later /24 overlaps an earlier /22. The task leaves a durable allocation map.

## 4. Agent-visible inputs

`docs/ipam_contract.md` is the highest authority. `pool.json` and `requests.json` are protected. Identifiers are `request_id` values.

## 5. Hidden ground truth

The evaluator recomputes allocations with Python ipaddress and does not import a candidate allocator. net-eps takes the whole /22 under largest-first.

The required final workspace state is `allocation.json`.
The durable record keeps a stable key for each decision in `allocation.json`.

## 6. Expected workflow

1. Read the contract and both JSON inputs.
2. Sort by prefix_len then request_id.
3. First-fit the lowest aligned subnet that does not overlap.
4. Write allocation.json and notes.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `246-interval-capacity-packing` | first-fit under a capacity | 246 packs time intervals; 240 allocates aligned IPv4 prefixes |
| `240-rpki-roa-route-origin-gate` | mill networking wording | the old 240 was a clerk drain; this package is IPAM |

1. Read the protected inputs and record their state before editing `allocation.json`.
2. Apply the published rule to the key fields that determine `allocation.json`.
3. Write `allocation.json` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires combining a pool and a request list, applying prefix arithmetic, writing an exact map, and staying offline.

## 8. Stressors and difficulty

- **Stressors:** largest-first versus file order, alignment, leftover unplaced
- **Difficulty:** hard; file-order first-fit yields a different winner than prefix_len order
- **Plausible failure mode:** serve requests in JSON order or skip alignment

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`allocated_prefixes` (0.50 core) checks the allocation map. `unplaced_requests` (0.30 core) checks unplaced ids. `verification_handoff` (0.20 optional) checks notes.

### Adjacent examples

- **Nearest valid:** net-eps receives 10.8.0.0/22; the others are unplaced.
- **Nearest wrong 1:** file order gives net-gamma a /24 before net-eps.
- **Nearest wrong 2:** overlapping leftover /24s are still issued after a /22.

`allocation.json` is a required final artifact checked by the hidden evaluator.
`ALLOC_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

The prompt does not print the allocation map. The evaluator recomputes from pool.json and requests.json.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect file-order allocation.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
