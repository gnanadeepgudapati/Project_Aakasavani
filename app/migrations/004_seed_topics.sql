-- 004_seed_topics.sql
-- plans/27-ui-completion.md (G-2). EDITION-AND-UI.md §2.2's own example
-- topics/queries, seeded verbatim so the topic chip row has something to
-- show on a fresh install rather than shipping the UI with an empty list.
-- Still fully user-editable at runtime via app/topics.py - this is a
-- starting point, not a fixed list.

INSERT INTO topics (name, query) VALUES
  ('Energy',      'oil OR gas OR OPEC OR solar OR renewable OR "power grid" OR coal'),
  ('AI',          '"artificial intelligence" OR LLM OR OpenAI OR Anthropic OR "machine learning"'),
  ('Geopolitics', 'sanctions OR treaty OR "border dispute" OR NATO OR tariff OR diplomatic'),
  ('Crypto',      'bitcoin OR ethereum OR crypto OR stablecoin OR blockchain');
