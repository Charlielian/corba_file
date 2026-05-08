#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载模块
从 conf.yaml 读取统一配置，提供类型安全的属性访问。
兼容 PyInstaller 打包：优先从 exe 同目录读取，找不到再从打包内部读取。
"""

import os
import sys
import multiprocessing
import yaml


def _resolve_config_path(config_path: str) -> str:
    """
    解析配置文件路径（兼容 PyInstaller 打包）

    查找顺序：
    1. 如果传入的是绝对路径且存在，直接使用
    2. 在 exe/脚本所在目录下查找
    3. 在 PyInstaller 的 _MEIPASS 临时目录下查找（打包时嵌入的文件）
    """
    # 绝对路径且存在，直接返回
    if os.path.isabs(config_path) and os.path.exists(config_path):
        return config_path

    # 在 exe/脚本所在目录下查找
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    local_path = os.path.join(app_dir, os.path.basename(config_path))
    if os.path.exists(local_path):
        return local_path

    # 在 PyInstaller _MEIPASS 中查找
    if getattr(sys, 'frozen', False):
        bundle_dir = sys._MEIPASS
        bundle_path = os.path.join(bundle_dir, os.path.basename(config_path))
        if os.path.exists(bundle_path):
            return bundle_path

    # 都找不到，返回本地路径（让调用方报错）
    return local_path


class Config:
    """统一配置管理器（YAML）"""

    def __init__(self, config_path: str = 'conf.yaml'):
        resolved = _resolve_config_path(config_path)
        if not os.path.exists(resolved):
            raise FileNotFoundError(
                f"配置文件不存在: {config_path}\n"
                f"已尝试路径: {resolved}\n"
                f"请将 conf.yaml 放在 exe 同目录下"
            )
        with open(resolved, 'r', encoding='utf-8') as f:
            self._raw = yaml.safe_load(f)

    # ---------- 通用 ----------

    @property
    def pg_config(self) -> dict:
        return self._raw['postgres_config']

    @property
    def pool_min(self) -> int:
        return self.pg_config.get('connection_pool', {}).get('min_connections', 2)

    @property
    def pool_max(self) -> int:
        return self.pg_config.get('connection_pool', {}).get('max_connections', 10)

    @property
    def batch_page_size(self) -> int:
        return self.pg_config.get('batch_insert', {}).get('page_size', 5000)

    @property
    def log_retention_days(self) -> int:
        return self._raw.get('global', {}).get('log_retention_days', 30)

    @property
    def worker_processes(self) -> int:
        return self._raw.get('global', {}).get('worker_processes', multiprocessing.cpu_count())

    @property
    def dynamic_pool(self) -> dict:
        return self._raw.get('global', {}).get('dynamic_pool', {
            'enabled': True,
            'min_workers': 1,
            'max_workers': None,
            'file_size_threshold': 50,
            'large_file_workers': 2,
            'history_window': 5,
        })

    # ---------- 4G ----------

    @property
    def cfg_4g(self) -> dict:
        return self._raw.get('4g', {})

    @property
    def input_path_4g(self) -> str:
        return self.cfg_4g['input_path']

    @property
    def parsed_path_4g(self) -> str:
        return self.cfg_4g['parsed_path']

    @property
    def target_table_4g(self) -> str:
        return self.cfg_4g.get('target_table', 'pp_cell')

    @property
    def parsed_retention_days_4g(self) -> int:
        return self.cfg_4g.get('parsed_retention_days', 15)

    @property
    def filter_rules_4g(self) -> dict:
        return self.cfg_4g.get('filter_rules', {
            'full_omcr_prefix': 'omcr7',
            'filter_keyword': '阳江',
        })

    @property
    def counter_list_4g(self) -> list:
        return self.cfg_4g.get('counter_list', [])

    # ---------- 5G ----------

    @property
    def cfg_5g(self) -> dict:
        return self._raw.get('5g', {})

    @property
    def input_path_5g(self) -> str:
        return self.cfg_5g['input_path']

    @property
    def parsed_path_5g(self) -> str:
        return self.cfg_5g['parsed_path']

    @property
    def parsed_retention_days_5g(self) -> int:
        return self.cfg_5g.get('parsed_retention_days', 15)

    @property
    def logs_retention_days_5g(self) -> int:
        return self.cfg_5g.get('logs_retention_days', 30)
