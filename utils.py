#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用工具函数
"""

import os
import re
import shutil
import logging
from datetime import datetime, timedelta
from typing import Optional


LOGGER: Optional[logging.Logger] = None


def ensure_dir(path: str):
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def normalize_cell_id_5g(cell_id: str) -> str:
    """5G 小区ID标准化"""
    return cell_id.replace("46000-", "460-00-").replace("=", "")


def safe_float(value: str) -> float:
    try:
        cleaned = value.strip().replace('\n', '')
        if not cleaned or cleaned == '-':
            return 0.0
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def extract_omc_name(filename: str) -> str:
    """从文件名提取 OMC 名称"""
    return filename.split("_")[0]


def extract_date_from_filename(filename: str) -> str:
    """从文件名提取日期（8位数字）"""
    m = re.search(r'(\d{8})', filename)
    return m.group(1) if m else datetime.now().strftime('%Y%m%d')


def get_tech_type_4g(filename: str) -> str:
    """根据文件名判断 4G 技术类型"""
    if 'EUTRANCELLFDD' in filename:
        return 'FDD'
    return 'TDD'


def get_table_type_5g(filename: str) -> str:
    """根据文件名判断 5G 表类型"""
    TABLE_TYPE_PATTERNS_5G = {
        'nrcellduphysical':    '-SA-NRCELLDUPHYSICAL-',
        'nrcellcuphysical':    '-SA-NRCELLCUPHYSICAL-',
        'nrcellcu':            '-SA-NRCELLCU-',
        'nrcelldu':            '-SA-NRCELLDU-',
        'inventoryunitrru':    '-SA-INVENTORYUNITRRU-',
        'inventoryunitshelf':  '-SA-INVENTORYUNITSHELF-',
    }
    for ttype, pattern in TABLE_TYPE_PATTERNS_5G.items():
        if pattern in filename:
            return ttype
    return ''


def clean_old_files(base_path: str, retention_days: int):
    """清理超过指定天数的文件和空文件夹"""
    if not os.path.exists(base_path):
        return
    cutoff = datetime.now() - timedelta(days=retention_days)
    deleted_files = deleted_folders = 0

    for root, dirs, files in os.walk(base_path, topdown=False):
        for f in files:
            fp = os.path.join(root, f)
            try:
                if datetime.fromtimestamp(os.path.getmtime(fp)) < cutoff:
                    os.remove(fp)
                    deleted_files += 1
            except Exception as e:
                if LOGGER:
                    LOGGER.warning(f"删除文件失败 {fp}: {e}")

        for d in dirs:
            dp = os.path.join(root, d)
            try:
                if not os.listdir(dp):
                    os.rmdir(dp)
                    deleted_folders += 1
            except Exception as e:
                if LOGGER:
                    LOGGER.warning(f"删除文件夹失败 {dp}: {e}")

    if LOGGER:
        LOGGER.info(f"清理 {base_path}：删除 {deleted_files} 个文件, {deleted_folders} 个空文件夹")


def setup_logger(base_path: str, retention_days: int) -> logging.Logger:
    """初始化日志系统"""
    global LOGGER
    log_dir = os.path.join(base_path, "log")
    ensure_dir(log_dir)

    today = datetime.now().strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"unified_parser_{today}.log")

    logger = logging.getLogger("unified_parser")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(fmt)
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(sh)

    LOGGER = logger
    LOGGER.info(f"日志文件: {log_file}")
    clean_old_files(log_dir, retention_days)
    return logger
