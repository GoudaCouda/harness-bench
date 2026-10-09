# Task authoring and acceptance

## Package contract

Every task is a self-contained directory:

```text
NNN-truthful-semantic-slug/
├── task.yaml
├── design.md
├── instruction.md
├── environment/
│   └── Dockerfile
├── workspace/                  initial agent-visible state
└── tests/                      never agent-visible
    ├── cases.yaml
    ├── test_outcome.py
    ├── reference/
    └── ground_truth/           optional hidden fixtures/builders
```

`task.yaml` declares domain, construction difficulty, capability tags, harness
demands, stressors, prompt files, workspace, required artifacts, exact mutation
ownership, evaluator paths, timeout, and honest provenance/source IDs.

`design.md` records the user need, adaptation, workflow, final state, failure
modes, difficulty rationale, scoring blocks, leakage analysis, and pilot status.
`instruction.md` states the task and boundaries without embedding the instance
answer. The Dockerfile pins its base, creates the agreed unprivileged agent
identity, sets `HOME`, and leaves a writable work directory.

## What makes a task valuable

A task models a recognizable workflow with dependent decisions, evidence
integration, tool use, state, and verification. A static read-table/write-table
conversion, keyword check, or renamed copy of an existing state machine is not
enough. Prefer diversity in execution shape: repositories, databases, binary
documents, graph constraints, time/version logic, recovery, local services,
office artifacts, and multi-source adjudication.

The task must be solvable from visible evidence and public rules, but not from
the prompt alone. Public controllers may expose schema, vocabulary, inspect,
query, preview, and object/field/rule diagnostics. They must not export answer
constructors, item-keyed final maps, corrected values, or complete final state.

## Evaluator contract

- The hidden evaluator does not import or execute the public controller.
- Reference builders and ground truth remain hidden from the agent.
- Correctness is recomputed from protected sources or independently encoded
  relations, not candidate-authored verification files.
- Protected inputs, controller code, and irreversible boundaries are checked.
- Equivalent valid serialization/reordering is accepted where semantics are
  set-like; conflicting replay and stale checkpoints fail without mutation.
- Mutation/recovery tasks evaluate durable state and verification, not only a
  proposed plan.
- Semantic LLM fallback is bounded to genuine prose and cannot rescue structured
  state, calculation, evidence, integrity, or safety.
- Core scoring resolves to two or three natural effective blocks. Dependent
  diagnostic cases may share a snake-case `score_group`; the whole group earns
  credit only when every member passes. Each effective core block weighs at
  least `0.20`, while genuinely independent cohorts remain separate.
- Task-level zero-weight gates are optional. Use one only for a concrete
  integrity, disclosure, path-escape, dangerous-payload, or irreversible-action
  red line. Malformed input and ordinary implementation restrictions belong in
  scored core cases.
- Pure-code tasks inherit the shared computation-only standard-library and
  ordinary value/container method policy. Do not create per-task hidden style
  allowlists for harmless operations.

## Required acceptance evidence

Before a new package enters a release:

1. focused contracts pass, including adjacent wrong answers and reward hacking;
2. empty, untouched, malformed, and reference workspaces score `0/0/0/1`;
3. the evaluator is deterministic and read-only;
4. the public-leakage validator passes;
5. design and package validators pass;
6. source aliases, permissions, pinned image, and Docker reference grade pass;
7. replay, conflict, stale-plan, source-tamper, symlink/special-node, and
   prohibited-action cases behave as declared;
8. an automated release-readiness review confirms that the task represents a
   recognizable, dependent, multi-source workflow rather than a renamed lookup,
   answer-copying controller, or single-table transformation;
9. a fresh model/harness run uses current package/controller/grader/model
   identities, preserves every terminal outcome in the denominator, and passes
   automated trajectory and scoring-integrity audits.

Static correctness is necessary but does not prove task quality. Model score is
also not an admission rule: high scores can reveal shallow work, and low scores
can reveal useful difficulty or an unfair interface. Model score calibrates and
diagnoses the task; it is not by itself an admission gate, and current admission
has no manual-acceptance requirement.
