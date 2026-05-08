#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载模块
从 conf.yaml 读取统一配置，提供类型安全的属性访问。
"""

import os
import multiprocessing
import yaml


class Config:
    """统一配置管理器（YAML）"""

    def __init__(self, config_path: str = 'conf.yaml'):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件不存在: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
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
