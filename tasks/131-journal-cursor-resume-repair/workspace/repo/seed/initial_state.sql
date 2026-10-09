PRAGMA foreign_keys=ON;
CREATE TABLE accounts (
  account_id TEXT PRIMARY KEY,
  balance_cents INTEGER NOT NULL,
  version INTEGER NOT NULL
);
CREATE TABLE applied_events (
  event_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  delta_cents INTEGER NOT NULL,
  source_segment TEXT NOT NULL,
  source_line INTEGER NOT NULL,
  applied_at TEXT NOT NULL
);
CREATE TABLE consumer_cursor (
  consumer TEXT PRIMARY KEY,
  segment TEXT NOT NULL,
  line_no INTEGER NOT NULL,
  event_id TEXT NOT NULL
);
INSERT INTO accounts VALUES
  ('acct-a', 1100, 3),
  ('acct-b', 500, 1),
  ('acct-c', 700, 1);
INSERT INTO applied_events VALUES
  ('e100','acct-a',1000,'segment-00041.jsonl',1,'2026-08-28T09:00:01Z'),
  ('e101','acct-b',500,'segment-00041.jsonl',2,'2026-08-28T09:00:03Z'),
  ('e102','acct-a',-200,'segment-00041.jsonl',3,'2026-08-28T09:00:06Z'),
  ('e103','acct-c',700,'segment-00041.jsonl',4,'2026-08-28T09:00:08Z'),
  ('e104','acct-a',300,'segment-00042.jsonl',2,'2026-08-28T09:01:01Z');
INSERT INTO consumer_cursor VALUES
  ('account-projection','segment-00041.jsonl',3,'e102');
