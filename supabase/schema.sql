-- FeatureBot application tables (run in Supabase → SQL Editor)
-- LangGraph checkpoint tables (checkpoints, checkpoint_blobs, etc.) are
-- created automatically by PostgresSaver.setup() on first app start.

-- Maps GitHub issues back to Google Chat threads (for webhook routing)
CREATE TABLE IF NOT EXISTS issue_thread_map (
    repo TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    thread_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (repo, issue_number)
);

CREATE INDEX IF NOT EXISTS idx_issue_thread_map_thread_id
    ON issue_thread_map (thread_id);

-- Maps Chat threads to linked GitHub repos (per-thread repo binding)
CREATE TABLE IF NOT EXISTS thread_repo_map (
    thread_id TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional: enable Row Level Security (RLS) if exposing via Supabase API.
-- The app connects with the service role / direct Postgres URL, so RLS is
-- not required for server-side use. Uncomment if you add client-side access:
--
-- ALTER TABLE issue_thread_map ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE thread_repo_map ENABLE ROW LEVEL SECURITY;
