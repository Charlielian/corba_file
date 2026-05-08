-- ============================================================
-- 北向文件统一解析器 - 建表脚本
-- 包含 4G 日志表、5G 日志表
-- ============================================================

-- ----------------------------
-- 4G 解析日志表
-- ----------------------------
DROP TABLE IF EXISTS logs_4g;
CREATE TABLE logs_4g (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) UNIQUE NOT NULL,
    parse_time TIMESTAMP NOT NULL DEFAULT NOW(),
    rows_inserted INTEGER NOT NULL DEFAULT 0,
    file_size BIGINT,
    omcr VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_logs_4g_created_at ON logs_4g(created_at DESC);
CREATE INDEX idx_logs_4g_filename ON logs_4g(filename);
CREATE INDEX idx_logs_4g_omcr ON logs_4g(omcr);

COMMENT ON TABLE logs_4g IS '4G文件解析日志表，防止重复解析';
COMMENT ON COLUMN logs_4g.status IS 'success/failed/skipped';

-- ----------------------------
-- 5G 解析日志表
-- ----------------------------
DROP TABLE IF EXISTS logs_5g;
CREATE TABLE logs_5g (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) UNIQUE NOT NULL,
    parse_time TIMESTAMP NOT NULL DEFAULT NOW(),
    rows_inserted INTEGER NOT NULL DEFAULT 0,
    file_size BIGINT,
    omcr VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_logs_5g_created_at ON logs_5g(created_at DESC);
CREATE INDEX idx_logs_5g_filename ON logs_5g(filename);
CREATE INDEX idx_logs_5g_omcr ON logs_5g(omcr);

COMMENT ON TABLE logs_5g IS '5G文件解析日志表，防止重复解析';
COMMENT ON COLUMN logs_5g.status IS 'success/failed/skipped';
