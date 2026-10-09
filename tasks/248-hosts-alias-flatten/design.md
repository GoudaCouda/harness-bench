# Task Design: `248-hosts-alias-flatten`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** operator flattening a mill hosts file
- **Trigger:** api.mill.local aliases through edge while a/b loop
- **Objective:** emit IPv4 records and a loop list
- **Irreversible boundary:** no nameserver update is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| GITHUB-CODEOWNERS | GitHub CODEOWNERS | https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners | 2026-09-11 | Grounds name-to-target mapping |
| JSONRPC-20 | JSON-RPC 2.0 specification | https://www.jsonrpc.org/specification | 2026-09-11 | Motivates fail-closed walks of structured names |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file and record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** A tiny alias list makes CNAME flattening executable without DNS.

## 3. Real-workflow justification

Partial flattening that stops after one hop leaves web.mill.local as a name. Loops must not be emitted as records.

## 4. Agent-visible inputs

`docs/hosts_contract.md` is highest authority. `hosts.json` rows carry `host_id`, `name`, and `target`.

## 5. Hidden ground truth

The evaluator recomputes records and loops independently. web.mill.local must resolve through two hops to 10.1.2.3.

The required final workspace state is `hosts_flat.json`.
The durable record keeps a stable key for each decision in `hosts_flat.json`.

## 6. Expected workflow

1. Read the contract and hosts.json.
2. Follow each name until an IPv4 literal or a repeated name.
3. Write hosts_flat.json and notes.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `233-dns-cache-zone-admission` | DNS naming | 233 admits cache records; 248 flattens a local alias file |
| `248-pcap-dhcp-lease-conflict-rebuild` | mill net wording | the old 248 was a clerk drain |

1. Read the protected inputs and record their state before editing `hosts_flat.json`.
2. Apply the published rule to the key fields that determine `hosts_flat.json`.
3. Write `hosts_flat.json` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires walking aliases, detecting loops, writing JSON, and staying offline.

## 8. Stressors and difficulty

- **Stressors:** two-hop aliases, two-node loops, IPv4 terminals
- **Difficulty:** hard; one-hop flattening leaves web.mill.local pointing at api.mill.local
- **Plausible failure mode:** emit looped names as records, or stop after one alias

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`flattened_records` (0.50 core) checks the IPv4 map. `loop_names` (0.30 core) checks the loop list. Notes 0.20.

### Adjacent examples

- **Nearest valid:** web and api both map to 10.1.2.3; a and b are loops.
- **Nearest wrong 1:** only flatten one hop.
- **Nearest wrong 2:** drop looped names from both maps without listing them.

`hosts_flat.json` is a required final artifact checked by the hidden evaluator.
`FLATTEN_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

The prompt does not print the IPv4 map.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect one-hop flattening.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
