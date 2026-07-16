-- OAuth 存储表（从 JSON 文件迁移到 SQLite）
CREATE TABLE IF NOT EXISTS oauth_users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_clients (
    client_id TEXT PRIMARY KEY,
    client_name TEXT,
    client_secret TEXT,
    redirect_uris TEXT NOT NULL DEFAULT '[]',
    scopes TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_auth_codes (
    code TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT '[]',
    expires_at REAL NOT NULL,
    code_challenge TEXT,
    redirect_uri TEXT,
    redirect_uri_provided_explicitly INTEGER NOT NULL DEFAULT 0,
    used INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS oauth_access_tokens (
    token TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT '[]',
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
    token TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT '[]',
    expires_at REAL NOT NULL
);
