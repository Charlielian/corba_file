#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析器抽象基类
所有解析器（4G / 5G）的公共接口和通用逻辑。
"""

import os
import shutil
import traceback
from abc import ABC, abstractmethod
from typing import Dict

from .config import Config
from .db import ConnectionPoolManager, get_pool
from .utils import LOGGER, ensure_dir, extract_omc_name, extract_date_from_filename


class BaseFileParser(ABC):

    def __init__(self, config: Config, pool_mgr: ConnectionPoolManager = None):
        self.config = config
        self._pool_mgr_arg = pool_mgr
        self.pg_config = config.pg_config

    @property
    def pool_mgr(self) -> ConnectionPoolManager:
        if self._pool_mgr_arg is not None:
            return self._pool_mgr_arg
        return get_pool()

    @abstractmethod
    def parse_file(self, input_path: str, filename: str, parsed_path: str,
                   total: int, index: int) -> int:
        """
        解析单个文件

        Returns:
            int: 入库行数
        """
        ...

    def _move_to_parsed(self, src_path: str, filename: str,
                        parsed_path: str, date_str: str, omc_name: str,
                        sub_dir: str = ''):
        """将已处理文件移动到分类目录"""
        target = os.path.join(parsed_path, date_str, omc_name, sub_dir) if sub_dir \
            else os.path.join(parsed_path, date_str, omc_name)
        ensure_dir(target)
        shutil.move(src_path, os.path.join(target, filename))
