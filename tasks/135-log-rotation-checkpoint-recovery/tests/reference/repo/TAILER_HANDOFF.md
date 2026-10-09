# Rotated tailer recovery handoff

The checkpoint identified the inode of `service.log.1` and stopped after r401, but the durable processed ledger already covered r400 through r404. I treated the ledger as the duplicate-suppression authority and the device/inode plus byte offset as the physical scan location. The later rotation meant the active path now had a different identity.

I inspected both files and state, then ran `python3 tools/tailer_recovery.py --ack-ledger-ahead`. Only r405 and r406 were written to the recovered delta and appended to processed state. The checkpoint now identifies the actual active `service.log` inode, its exact EOF offset, and last record r406.

A copied-state second `python3 tools/tailer_recovery.py` recovery produced an empty output with `new_record_ids: []` and left checkpoint and ledger unchanged, proving the no-op property. Verification was offline against supplied logs; no service or external system was contacted.
