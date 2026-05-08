#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库模块
PostgreSQL 连接池管理与 CRUD 操作封装。
"""

from contextlib import contextmanager
from typing import Dict, List, Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extras import execute_values, RealDictCursor


# 表字段缓存
COLUMN_CACHE: Dict[str, List[str]] = {}

_pool_mgr_instance: Optional['ConnectionPoolManager'] = None


def init_pool(pg_config: dict, minconn: int = 2, maxconn: int = 10):
    """在子进程中初始化连接池（fork 安全）"""
    global _pool_mgr_instance
    if _pool_mgr_instance is None:
        _pool_mgr_instance = ConnectionPoolManager(pg_config, minconn, maxconn)
    return _pool_mgr_instance


def get_pool() -> 'ConnectionPoolManager':
    """获取当前进程的连接池实例"""
    if _pool_mgr_instance is None:
        raise RuntimeError("连接池未初始化，请先调用 init_pool()")
    return _pool_mgr_instance


class ConnectionPoolManager:
    """PostgreSQL 连接池管理器"""

    def __init__(self, pg_config: dict, minconn: int = 2, maxconn: int = 10):
        self._pool = pool.SimpleConnectionPool(
            minconn, maxconn,
            host=pg_config['host'],
            port=pg_config['port'],
            user=pg_config['user'],
            password=pg_config['password'],
            database=pg_config['database'],
        )

    def getconn(self):
        return self._pool.getconn()

    def putconn(self, conn):
        self._pool.putconn(conn)

    def closeall(self):
        self._pool.closeall()


@contextmanager
def pg_connection(pool_mgr: ConnectionPoolManager, pg_config: dict, readonly=False):
    conn = None
    try:
        conn = pool_mgr.getconn()
        if readonly:
            conn.autocommit = True
        yield conn
    except Exception:
        if conn:
            conn.rollback()
        raise
    else:
        if not readonly:
            conn.commit()
    finally:
        if conn:
            if readonly:
                conn.autocommit = False
            pool_mgr.putconn(conn)


def pg_query(pool_mgr, pg_config, sql, params=None):
    with pg_connection(pool_mgr, pg_config, readonly=True) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params) if params else cur.execute(sql)
            return cur.fetchall()


def pg_execute(pool_mgr, pg_config, sql, params=None):
    """执行写操作"""
    with pg_connection(pool_mgr, pg_config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params) if params else cur.execute(sql)


def pg_batch_insert(pool_mgr, pg_config, sql, data, page_size=5000):
    """批量插入（execute_values）"""
    with pg_connection(pool_mgr, pg_config) as conn:
        with conn.cursor() as cur:
            execute_values(cur, sql, data, page_size=page_size)


def get_table_columns(table_name: str, pool_mgr, pg_config) -> List[str]:
    """获取表列名（带缓存）"""
    if table_name in COLUMN_CACHE:
        return COLUMN_CACHE[table_name]
    rows = pg_query(pool_mgr, pg_config,
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = %s ORDER BY ordinal_position",
                    (table_name,))
    cols = [r['column_name'] for r in rows]
    COLUMN_CACHE[table_name] = cols
    return cols
