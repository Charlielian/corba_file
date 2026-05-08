#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析日志表管理
logs_4g / logs_5g 表的初始化、去重检查、记录、清理。
"""

from datetime import datetime

from .db import pg_execute, pg_query, pg_connection
from .utils import LOGGER


def init_parse_logs(pool_mgr, pg_config, mode: str):
    """初始化解析日志表"""
    table = f"logs_{mode}"
    sql = f"""
    CREATE TABLE IF NOT EXISTS {table} (
        id SERIAL PRIMARY KEY,
        filename VARCHAR(500) UNIQUE NOT NULL,
        parse_time TIMESTAMP NOT NULL,
        rows_inserted INTEGER NOT NULL DEFAULT 0,
        file_size BIGINT,
        omcr VARCHAR(50),
        status VARCHAR(20) NOT NULL DEFAULT 'success',
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_{table}_created_at ON {table}(created_at);
    CREATE INDEX IF NOT EXISTS idx_{table}_filename ON {table}(filename);
    """
    pg_execute(pool_mgr, pg_config, sql)
    LOGGER.info(f"{table} 表初始化成功")


def is_file_parsed(filename: str, pool_mgr, pg_config, mode: str) -> bool:
    table = f"logs_{mode}"
    rows = pg_query(pool_mgr, pg_config,
                    f"SELECT EXISTS(SELECT 1 FROM {table} WHERE filename = %s) as flag",
                    (filename,))
    return rows[0]['flag'] if rows else False


def log_parsed_file(filename: str, rows_inserted: int, pool_mgr, pg_config,
                    mode: str, omcr: str = '', status: str = 'success',
                    error_msg: str = '', file_size: int = 0):
    """记录文件解析结果"""
    table = f"logs_{mode}"
    sql = f"""
    INSERT INTO {table} (filename, parse_time, rows_inserted, file_size, omcr, status, error_message)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (filename) DO UPDATE SET
        parse_time = EXCLUDED.parse_time,
        rows_inserted = EXCLUDED.rows_inserted,
        file_size = EXCLUDED.file_size,
        omcr = EXCLUDED.omcr,
        status = EXCLUDED.status,
        error_message = EXCLUDED.error_message,
        created_at = CURRENT_TIMESTAMP
    """
    pg_execute(pool_mgr, pg_config, sql,
               (filename, datetime.now(), rows_inserted, file_size, omcr, status, error_msg))


def clean_parse_logs(pool_mgr, pg_config, mode: str, retention_days: int):
    """清理旧的解析日志"""
    table = f"logs_{mode}"
    with pg_connection(pool_mgr, pg_config) as conn:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table} WHERE created_at < NOW() - INTERVAL '%s days'",
                        (retention_days,))
            deleted = cur.rowcount
    LOGGER.info(f"清理 {table} 表：删除了 {deleted} 条超过 {retention_days} 天的记录")
