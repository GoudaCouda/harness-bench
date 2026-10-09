Task: Offline Knowledge QA with Insufficient Evidence Detection

Use only:
- `$WORKSPACE/kb/*.md`
- `$WORKSPACE/questions.json`

Do not use the internet, product assumptions, or common knowledge to fill gaps.

Write `$WORKSPACE/answers.json`.

Output shape:

{
  "answers": [
    {
      "question_id": "Q01",
      "status": "answered",
      "answer": "...",
      "sources": [
        {
          "source_file": "kb/product_manual.md",
          "evidence_id": "PM-1",
          "quote_or_signal": "..."
        }
      ],
      "missing_evidence": []
    }
  ]
}

Requirements:
- Include exactly one answer per question in `questions.json`.
- `status` must be exactly `answered`, `partial`, or `insufficient_evidence`.
- For `answered`, provide a concise answer and at least one source.
- For `partial`, answer only the supported part and list missing evidence in `missing_evidence`.
- For `insufficient_evidence`, set `answer` to `insufficient_evidence`, leave `sources` empty or cite only a related but insufficient source, and explain the missing evidence.
- Missing evidence may be described with an equivalent precise phrase (for
  example, an approved, authorized, official, or valid phone number); no hidden
  exact wording is required.
- `source_file` must be a relative path such as `kb/security_bulletin.md`.
- Do not output Markdown wrapping around the JSON.
