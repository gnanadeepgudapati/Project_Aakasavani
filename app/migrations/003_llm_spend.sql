-- 003_llm_spend.sql
-- ARCHITECTURE.md §6: "A ledger appended to after the fact does not cap
-- anything." This table IS the ledger the wrapper checks BEFORE calling -
-- the cap enforcement lives in app/research/budget.py's check function,
-- not in this table's existence.

CREATE TABLE llm_spend (
  id       INTEGER PRIMARY KEY,
  ts       INTEGER NOT NULL,
  model    TEXT NOT NULL,
  purpose  TEXT,
  usd_cost REAL NOT NULL
);
CREATE INDEX idx_llm_spend_ts ON llm_spend(ts);
