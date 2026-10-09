# Repair MIME multipart decoding and attachment selection contract

Parse bounded synthetic MIME multipart messages using declared outer boundaries, CRLF or LF header separators, and recursive multipart `boundary` parameters. Decode 7bit/8bit, UTF-8 base64, and quoted-printable (hex escapes and soft LF breaks). Extract content type, angle-bracket-normalized Content-ID, filename parameter, decoded body, and nested integer path. Closing boundaries are mandatory; duplicate Content-IDs, malformed headers/encoding, or more than `max_parts` raise `ValueError`. Return id-sorted messages, all leaf parts, attachment subsets, and total attachment count.

The output object has exactly `messages,attachment_count`. Each id-sorted message has exactly `id,parts,attachments`; each leaf part in either list has exactly `path,content_type,content_id,filename,body`. Attachments are the leaf records whose filename is not null.

The function must not mutate inputs. Run `python3 -m unittest discover -s tests -v` and `python3 bin/run_repair.py`, re-open `out/result.json`, and document verification evidence plus the offline boundary in `REPAIR_NOTES.md`.
