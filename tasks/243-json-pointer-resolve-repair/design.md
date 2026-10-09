# Task Design: `243-json-pointer-resolve-repair`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** platform engineer repairing JSON Pointer lookup
- **Trigger:** escaped mill keys were treated as literals
- **Objective:** resolve RFC 6901 pointers including empty and tilde escapes
- **Irreversible boundary:** no mill API call or document publish is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| JSONRPC-20 | JSON-RPC 2.0 specification | https://www.jsonrpc.org/specification | 2026-09-11 | Grounds structured JSON request paths |
| OPENRPC-SPEC | OpenRPC specification | https://spec.open-rpc.org/ | 2026-09-11 | Motivates pointer-style member selection |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file and record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** A small mill document makes RFC 6901 executable without a JSON-RPC server.

## 3. Real-workflow justification

Pointer bugs swap west/east mills when `~1` is not unescaped before `~0`.

## 4. Agent-visible inputs

`repo/docs/pointer_contract.md` is highest authority. `repo/document.json` and `repo/query.json` are protected.

## 5. Hidden ground truth

Hidden cases cover empty pointers, array indexes, `a/b` keys, and missing paths. The evaluator does not import public tests.

The required final workspace state is `repo/src/pointer.py`.
The durable record keeps a stable key for each decision in `repo/src/pointer.py`.

## 6. Expected workflow

1. Read the contract and JSON inputs.
2. Run public tests.
3. Implement resolve_pointer.
4. Write resolved.json and notes.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `010-layered-config-resolution` | JSON code repair | 010 resolves layered config; 243 walks RFC 6901 pointers |
| `243-ifc-clash-detection-gate` | mill wording | the old 243 was a clerk drain |

1. Read the protected inputs and record their state before editing `repo/src/pointer.py`.
2. Apply the published rule to the key fields that determine `repo/src/pointer.py`.
3. Write `repo/src/pointer.py` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires code repair, tests, a snapshot, and an offline boundary.

## 8. Stressors and difficulty

- **Stressors:** tilde unescape order, missing paths, empty pointer
- **Difficulty:** hard; replacing `~0` before `~1` corrupts keys that contain both
- **Plausible failure mode:** reject the empty pointer, or treat `/plant/mills/1` as a string key

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`function_behavior` (0.50 core) runs hidden cases. `visible_snapshot` (0.30 core) checks resolved.json. Notes are optional 0.20.

### Adjacent examples

- **Nearest valid:** `/plant/mills/1/gate/code` is `G-2`.
- **Nearest wrong 1:** unescape `~0` first so `~01` becomes `/`.
- **Nearest wrong 2:** missing paths return None.

`repo/src/pointer.py` is a required final artifact checked by the hidden evaluator.
`repo/resolved.json` is a required final artifact checked by the hidden evaluator.
`repo/IMPLEMENTATION_NOTES.md` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

Hidden escape cases are not in the public tests.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect literal `~1` lookups.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
