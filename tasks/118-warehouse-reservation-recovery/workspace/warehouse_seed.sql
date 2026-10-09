CREATE TABLE inventory(sku TEXT PRIMARY KEY, on_hand INTEGER NOT NULL, available INTEGER NOT NULL, reserved INTEGER NOT NULL, shipped INTEGER NOT NULL);
CREATE TABLE orders(order_id TEXT PRIMARY KEY, status TEXT NOT NULL);
CREATE TABLE reservations(reservation_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, sku TEXT NOT NULL, quantity INTEGER NOT NULL, idempotency_key TEXT NOT NULL, sequence INTEGER NOT NULL, status TEXT NOT NULL, expires_at TEXT NOT NULL, pick_confirmed INTEGER NOT NULL);
CREATE TABLE recovery_transactions(
  recovery_id TEXT PRIMARY KEY,
  source_state_sha256 TEXT NOT NULL,
  semantic_plan_sha256 TEXT NOT NULL,
  applied_at TEXT NOT NULL,
  action_count INTEGER NOT NULL
);
INSERT INTO inventory VALUES ('SKU-A',12,1,11,0),('SKU-B',8,3,5,0);
INSERT INTO orders VALUES ('O-100','reserved'),('O-200','picked'),('O-300','reserved');
INSERT INTO reservations VALUES
 ('RSV-100-A','O-100','SKU-A',4,'IDEMP-O100',1,'held','2026-08-17T00:00:00Z',0),
 ('RSV-100-B','O-100','SKU-A',4,'IDEMP-O100',2,'held','2026-08-17T00:00:00Z',0),
 ('RSV-200','O-200','SKU-A',3,'IDEMP-O200',1,'held','2026-08-17T00:00:00Z',1),
 ('RSV-300','O-300','SKU-B',5,'IDEMP-O300',1,'held','2026-08-15T00:00:00Z',0);
