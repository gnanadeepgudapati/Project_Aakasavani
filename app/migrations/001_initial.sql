-- 001_initial.sql
-- plans/00-implementation-plan.md §2. 12 documented changes from the
-- ARCHITECTURE.md §3 draft - see that plan for the full rationale table.

CREATE TABLE schema_migrations (
  version    INTEGER PRIMARY KEY,
  applied_at INTEGER NOT NULL
);

-- ── feeds : source registry, loaded from data/feeds.yaml (step 01) ────
CREATE TABLE feeds (
  id            INTEGER PRIMARY KEY,
  url           TEXT UNIQUE NOT NULL,
  name          TEXT NOT NULL,
  section       TEXT NOT NULL
                CHECK (section IN ('tech','finance','world_india')),
  source_weight INTEGER NOT NULL DEFAULT 3
                CHECK (source_weight BETWEEN 1 AND 5),
  has_full_text INTEGER NOT NULL DEFAULT 0,
  enabled       INTEGER NOT NULL DEFAULT 1,
  etag          TEXT,
  last_modified TEXT,
  last_polled   INTEGER,
  fail_count    INTEGER NOT NULL DEFAULT 0
);

-- ── seen : the firehose. TTL'd. Hash retained forever ──────────────────
CREATE TABLE seen (
  url_hash      BLOB PRIMARY KEY,
  canonical_url TEXT,
  title         TEXT,
  source        TEXT,
  feed_id       INTEGER REFERENCES feeds(id),
  published_at  INTEGER,
  description   TEXT,
  image_url     TEXT,
  section       TEXT
                CHECK (section IN ('tech','finance','world_india')),
  first_seen    INTEGER NOT NULL,
  expires_at    INTEGER NOT NULL,
  expired       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_seen_pub     ON seen(published_at DESC);
CREATE INDEX idx_seen_expires ON seen(expires_at) WHERE expired = 0;
CREATE INDEX idx_seen_section ON seen(section, published_at DESC);

-- ── read : what you opened. Permanent. Never TTL'd ─────────────────────
CREATE TABLE read (
  url_hash          BLOB PRIMARY KEY,
  canonical_url     TEXT NOT NULL,
  title             TEXT,
  source            TEXT,
  published_at      INTEGER,
  full_text         TEXT,
  content_hash      BLOB,
  fetched_via       TEXT CHECK (fetched_via IN ('feed','live','wayback')),
  read_at           INTEGER NOT NULL,
  dwell_seconds     INTEGER,
  ia_snapshot       TEXT,
  starter_questions TEXT
);
CREATE INDEX idx_read_at  ON read(read_at DESC);
CREATE INDEX idx_read_pub ON read(published_at DESC);

-- ── editions : the atomic swap ──────────────────────────────────────────
CREATE TABLE editions (
  id            INTEGER PRIMARY KEY,
  edition_date  TEXT NOT NULL,
  built_at      INTEGER,
  status        TEXT NOT NULL
                CHECK (status IN ('building','live','failed','superseded')),
  article_count INTEGER,
  read_minutes  INTEGER
);
CREATE INDEX idx_editions_live ON editions(status, built_at DESC);

CREATE TABLE edition_items (
  edition_id    INTEGER NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
  url_hash      BLOB NOT NULL,
  section       TEXT NOT NULL,
  rank_position INTEGER NOT NULL,
  PRIMARY KEY (edition_id, url_hash)
);

-- ── topics : saved FTS5 queries, user-editable ──────────────────────────
CREATE TABLE topics (
  id      INTEGER PRIMARY KEY,
  name    TEXT UNIQUE NOT NULL,
  query   TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1
);

-- ── ia_queue ─────────────────────────────────────────────────────────────
CREATE TABLE ia_queue (
  url_hash        BLOB PRIMARY KEY,
  url             TEXT NOT NULL,
  queued_at       INTEGER NOT NULL,
  attempts        INTEGER NOT NULL DEFAULT 0,
  last_attempt_at INTEGER,
  done            INTEGER NOT NULL DEFAULT 0
);

-- ── FTS5 ───────────────────────────────────────────────────────────────
CREATE VIRTUAL TABLE read_fts USING fts5(
  title, full_text, source, content='read', content_rowid='rowid'
);
CREATE VIRTUAL TABLE seen_fts USING fts5(
  title, description, source, content='seen', content_rowid='rowid'
);

-- read_fts sync triggers - external-content FTS5 tables need these by hand;
-- SQLite does not maintain them automatically. This was a bug in the
-- ARCHITECTURE.md §3 draft (content='read' declared with no triggers at
-- all, which silently yields a permanently empty index) - see
-- plans/00-implementation-plan.md §2.
CREATE TRIGGER read_ai AFTER INSERT ON read BEGIN
  INSERT INTO read_fts(rowid, title, full_text, source)
  VALUES (new.rowid, new.title, new.full_text, new.source);
END;

CREATE TRIGGER read_ad AFTER DELETE ON read BEGIN
  INSERT INTO read_fts(read_fts, rowid, title, full_text, source)
  VALUES ('delete', old.rowid, old.title, old.full_text, old.source);
END;

CREATE TRIGGER read_au AFTER UPDATE ON read BEGIN
  INSERT INTO read_fts(read_fts, rowid, title, full_text, source)
  VALUES ('delete', old.rowid, old.title, old.full_text, old.source);
  INSERT INTO read_fts(rowid, title, full_text, source)
  VALUES (new.rowid, new.title, new.full_text, new.source);
END;

-- seen_fts sync triggers - EDITION-AND-UI.md §2.2 queries seen_fts for topic
-- matching; the §3 draft never defined this table at all.
CREATE TRIGGER seen_ai AFTER INSERT ON seen BEGIN
  INSERT INTO seen_fts(rowid, title, description, source)
  VALUES (new.rowid, new.title, new.description, new.source);
END;

CREATE TRIGGER seen_ad AFTER DELETE ON seen BEGIN
  INSERT INTO seen_fts(seen_fts, rowid, title, description, source)
  VALUES ('delete', old.rowid, old.title, old.description, old.source);
END;

CREATE TRIGGER seen_au AFTER UPDATE ON seen BEGIN
  INSERT INTO seen_fts(seen_fts, rowid, title, description, source)
  VALUES ('delete', old.rowid, old.title, old.description, old.source);
  INSERT INTO seen_fts(rowid, title, description, source)
  VALUES (new.rowid, new.title, new.description, new.source);
END;
