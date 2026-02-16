-- CMK auth tables on top of BetterAuth's "user" table.
-- Run AFTER `npx @better-auth/cli migrate` which creates
-- user, session, account, verification tables.

-- Extend BetterAuth user table with CMK columns
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS plan TEXT DEFAULT 'free';
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ;

-- API keys (cmk-sk-... hashed with SHA256)
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES "user"(id),
    name TEXT DEFAULT '',
    key_hash TEXT UNIQUE NOT NULL,
    prefix TEXT NOT NULL,
    created TIMESTAMPTZ DEFAULT NOW(),
    last_used TIMESTAMPTZ,
    revoked BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash) WHERE NOT revoked;

-- Teams
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES "user"(id),
    created TIMESTAMPTZ DEFAULT NOW()
);

-- Team membership
CREATE TABLE IF NOT EXISTS team_members (
    team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES "user"(id),
    role TEXT NOT NULL DEFAULT 'member',
    joined TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (team_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id);
