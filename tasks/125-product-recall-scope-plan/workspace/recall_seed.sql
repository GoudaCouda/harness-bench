PRAGMA foreign_keys=ON;

CREATE TABLE lots (
  lot_id TEXT PRIMARY KEY,
  product_code TEXT NOT NULL,
  manufactured_at TEXT NOT NULL,
  total_units INTEGER NOT NULL CHECK(total_units >= 0),
  recall_status TEXT NOT NULL
);
CREATE TABLE component_batches (
  batch_id TEXT PRIMARY KEY,
  parent_batch_id TEXT,
  material_code TEXT NOT NULL,
  trace_status TEXT NOT NULL
);
CREATE TABLE lot_components (
  lot_id TEXT NOT NULL REFERENCES lots(lot_id),
  batch_id TEXT NOT NULL REFERENCES component_batches(batch_id),
  quantity INTEGER NOT NULL CHECK(quantity > 0),
  PRIMARY KEY(lot_id, batch_id)
);
CREATE TABLE inventory (
  lot_id TEXT PRIMARY KEY REFERENCES lots(lot_id),
  on_hand INTEGER NOT NULL,
  available INTEGER NOT NULL,
  quarantined INTEGER NOT NULL,
  stop_sale_status TEXT NOT NULL
);
CREATE TABLE channels (
  channel_id TEXT PRIMARY KEY,
  channel_type TEXT NOT NULL,
  authority_status TEXT NOT NULL,
  local_draft_status TEXT NOT NULL
);
CREATE TABLE shipments (
  shipment_id TEXT PRIMARY KEY,
  lot_id TEXT NOT NULL REFERENCES lots(lot_id),
  channel_id TEXT NOT NULL REFERENCES channels(channel_id),
  quantity INTEGER NOT NULL,
  status TEXT NOT NULL,
  last_sequence INTEGER NOT NULL,
  last_event_id TEXT NOT NULL,
  stop_sale_status TEXT NOT NULL
);
CREATE TABLE event_ledger (
  event_id TEXT PRIMARY KEY,
  disposition TEXT NOT NULL,
  applied_at TEXT NOT NULL
);
CREATE TABLE event_quarantine (
  event_id TEXT PRIMARY KEY,
  reason TEXT NOT NULL
);
CREATE TABLE recall_transactions (
  recall_id TEXT PRIMARY KEY,
  source_state_sha256 TEXT NOT NULL,
  semantic_plan_sha256 TEXT NOT NULL,
  action_count INTEGER NOT NULL,
  committed_at TEXT NOT NULL
);
CREATE TABLE recall_journal (
  recall_id TEXT PRIMARY KEY,
  phase TEXT NOT NULL,
  prepared_action_key TEXT,
  source_state_sha256 TEXT NOT NULL,
  semantic_plan_sha256 TEXT,
  committed_at TEXT
);

INSERT INTO lots VALUES
 ('LOT-A','NOVA-100','2026-08-08T10:00:00Z',70,'open'),
 ('LOT-B','NOVA-100','2026-08-09T11:00:00Z',30,'open'),
 ('LOT-C','NOVA-200','2026-08-11T09:00:00Z',25,'open'),
 ('LOT-D','NOVA-100','2026-08-12T12:00:00Z',18,'open'),
 ('LOT-E','NOVA-300','2026-08-13T08:00:00Z',22,'open'),
 ('LOT-F','NOVA-100','2026-07-15T08:00:00Z',10,'open');

INSERT INTO component_batches VALUES
 ('CB-77','PB-RED','ADH-RED','verified'),
 ('CB-77-D','CB-77','ADH-RED','verified'),
 ('CB-SAFE','PB-BLUE','ADH-BLUE','verified'),
 ('CB-UNK',NULL,'ADH-RED','unresolved_parent');

INSERT INTO lot_components VALUES
 ('LOT-A','CB-77',12),
 ('LOT-B','CB-77',5),
 ('LOT-B','CB-SAFE',4),
 ('LOT-C','CB-SAFE',6),
 ('LOT-D','CB-UNK',3),
 ('LOT-E','CB-77-D',7),
 ('LOT-F','CB-77',2);

INSERT INTO inventory VALUES
 ('LOT-A',40,40,0,'none'),
 ('LOT-B',20,20,0,'none'),
 ('LOT-C',25,25,0,'none'),
 ('LOT-D',12,12,0,'none'),
 ('LOT-E',7,7,0,'none'),
 ('LOT-F',10,10,0,'none');

INSERT INTO channels VALUES
 ('CH-DIST','distributor','pending','none'),
 ('CH-MKT','marketplace','verified','none'),
 ('CH-RETAIL','retailer','verified','none');

INSERT INTO shipments VALUES
 ('SH-A','LOT-A','CH-RETAIL',30,'packed',1,'INIT-SH-A','none'),
 ('SH-B','LOT-B','CH-DIST',10,'packed',0,'INIT-SH-B','none'),
 ('SH-D','LOT-D','CH-MKT',6,'packed',1,'INIT-SH-D','none'),
 ('SH-E','LOT-E','CH-RETAIL',15,'packed',1,'INIT-SH-E','none');

INSERT INTO recall_journal VALUES
 ('RC-2026-0417','prepared','EV-504','PENDING',NULL,NULL);
