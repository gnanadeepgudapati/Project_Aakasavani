-- 002_seen_prefetch.sql
-- S-007 (logs/SESSIONS.md): pre-fetched front-page text needs a TTL'd home,
-- not a permanent one. `read` is permanent and means "what you opened" -
-- writing full text there for all ~39 front-page articles regardless of
-- whether the user ever opens them would be exactly the "permanent archive
-- of unread articles" ROADMAP.md rules out, and would make dwell_seconds/
-- read_at meaningless for rows nobody read.
--
-- `seen` already expires in 30 days and already has precedent for holding
-- (and stripping) text - Rule 5's "text stripped" sweep. Adding full_text
-- here keeps the pre-fetch cache naturally bounded by the same TTL, with
-- no separate cache-eviction mechanism needed.

ALTER TABLE seen ADD COLUMN full_text TEXT;
ALTER TABLE seen ADD COLUMN fetched_via TEXT CHECK (fetched_via IN ('feed','live','wayback'));
