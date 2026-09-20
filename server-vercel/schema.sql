-- Automation Hub Database Schema for PostgreSQL / Neon
-- Compatible with Neon Serverless Postgres

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(32) UNIQUE NOT NULL,
    label VARCHAR(64) NOT NULL
);

INSERT INTO roles (id, name, label) VALUES
(1, 'super_admin', 'Super Admin'),
(2, 'admin', 'Admin'),
(3, 'team_member', 'Team Member')
ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id SMALLINT NOT NULL DEFAULT 3 REFERENCES roles(id),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled', 'banned')),
    display_name VARCHAR(128) DEFAULT NULL,
    email VARCHAR(128) DEFAULT NULL,
    last_login_at TIMESTAMPTZ DEFAULT NULL,
    last_login_ip VARCHAR(45) DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Default super admin: username=superadmin password=Admin@12345
INSERT INTO users (id, username, password_hash, role_id, status, display_name)
VALUES (1, 'superadmin', '$2a$10$OKB8Am967zxMhVM03.dvx.1CdXSwqfwWyePBDAl8JJjFzXpylDUCu', 1, 'active', 'Super Admin')
ON CONFLICT (username) DO NOTHING;

CREATE TABLE IF NOT EXISTS licenses (
    id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'trial', 'revoked')),
    is_trial SMALLINT NOT NULL DEFAULT 0,
    starts_at TIMESTAMPTZ DEFAULT NULL,
    expires_at TIMESTAMPTZ DEFAULT NULL,
    notes VARCHAR(255) DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create perpetual license for default superadmin
INSERT INTO licenses (user_id, status, expires_at)
VALUES (1, 'active', '2099-12-31 23:59:59+00')
ON CONFLICT (user_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(128) NOT NULL,
    pc_name VARCHAR(128) DEFAULT NULL,
    fingerprint_hash VARCHAR(128) DEFAULT NULL,
    is_authorized SMALLINT NOT NULL DEFAULT 1,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, device_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token_hash VARCHAR(128) NOT NULL,
    refresh_token_hash VARCHAR(128) NOT NULL,
    device_id VARCHAR(128) DEFAULT NULL,
    pc_name VARCHAR(128) DEFAULT NULL,
    ip_address VARCHAR(45) DEFAULT NULL,
    user_agent VARCHAR(255) DEFAULT NULL,
    is_active SMALLINT NOT NULL DEFAULT 1,
    force_logout SMALLINT NOT NULL DEFAULT 0,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active, last_seen_at);
CREATE INDEX IF NOT EXISTS idx_sessions_refresh ON sessions(refresh_token_hash);

CREATE TABLE IF NOT EXISTS activity_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    ip_address VARCHAR(45) DEFAULT NULL,
    device_id VARCHAR(128) DEFAULT NULL,
    pc_name VARCHAR(128) DEFAULT NULL,
    details TEXT DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_logs(created_at);

CREATE TABLE IF NOT EXISTS link_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    browser VARCHAR(64) DEFAULT NULL,
    device_id VARCHAR(128) DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_link_user ON link_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_link_created ON link_logs(created_at);

CREATE TABLE IF NOT EXISTS login_history (
    id BIGSERIAL PRIMARY KEY,
    user_id INT DEFAULT NULL,
    username VARCHAR(64) DEFAULT NULL,
    success SMALLINT NOT NULL DEFAULT 0,
    ip_address VARCHAR(45) DEFAULT NULL,
    device_id VARCHAR(128) DEFAULT NULL,
    pc_name VARCHAR(128) DEFAULT NULL,
    reason VARCHAR(128) DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_login_user ON login_history(user_id);
CREATE INDEX IF NOT EXISTS idx_login_created ON login_history(created_at);

CREATE TABLE IF NOT EXISTS heartbeat_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INT DEFAULT NULL,
    session_id BIGINT DEFAULT NULL,
    status VARCHAR(32) NOT NULL,
    ip_address VARCHAR(45) DEFAULT NULL,
    device_id VARCHAR(128) DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_user ON heartbeat_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_heartbeat_created ON heartbeat_logs(created_at);

CREATE TABLE IF NOT EXISTS settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(64) UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO settings (setting_key, setting_value) VALUES
('heartbeat_interval', '45'),
('session_timeout', '3600'),
('offline_grace_seconds', '300'),
('single_session', '1'),
('app_name', 'Automation Hub')
ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value;

CREATE TABLE IF NOT EXISTS rate_limits (
    id BIGSERIAL PRIMARY KEY,
    rate_key VARCHAR(128) UNIQUE NOT NULL,
    hits INT NOT NULL DEFAULT 1,
    window_start TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
