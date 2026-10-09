# Northstar bulletin revision authority policy

The package is an internal draft. It may be staged for internal approval, but
no event in this bundle authorizes publication, portal export, notification,
or external approval.

## EVENT-SELECTION

For each `change_id`, select the highest `event_seq` whose `basis_status` is
`current`. Row order is not authority. A selected event still requires the
authority and credential checks below; current does not mean accepted.

## TOPOLOGICAL-ORDER

Adjudicate the dependency graph with Kahn's algorithm. At each step select the
lexicographically smallest ready `change_id`. If any prerequisite does not end
in `accept`, the child is `invalidate_dependency` and its proposal is not
independently applied.

## SIGNED-LEGAL

`signed_legal` proposals are accepted only when their credential is verified
and has role `legal_signer`. A later verified signed correction supersedes an
older signed correction for the same change.

## VERIFIED-DIRECTORY

`verified_directory` proposals are accepted only when their credential is
verified and has role `directory_owner`.

## RELEASE-COORDINATOR

`release_coordinator` proposals are accepted only when their credential is
verified, has role `release_coordinator`, and every declared prerequisite has
been accepted.

## LOWER-AUTHORITY

`campaign_comment`, `copy_edit_deletion`, and `publication_request` proposals
are rejected. They cannot expand coverage, delete controlled retention text,
remove a required dependent clause, or authorize an external release.

## DURABLE-RECOVERY

The `revision_journal` is append-only. A matching durable decision already in
the journal is reconciled into the recovered document and must not be appended
again. All other current decisions are appended in the deterministic
adjudication order as one recovery transaction. Direct SQLite edits and manual
OOXML edits are prohibited.

## PACKAGE-PRESERVATION

Resolve the tracked `w:ins` and `w:del` pairs in `word/document.xml`. Preserve
unaffected text, paragraph order, bookmarks, styles, comments, header, footer,
relationships, content types, and every non-document package part byte for
byte. The finished package must contain no unresolved tracked insertion or
deletion markup.

## INTERNAL-BOUNDARY

The only permitted terminal state is `staged_for_internal_approval` with
`external_published = 0`. No publication, export, send, notification, or
approval is executed by this offline workflow.
