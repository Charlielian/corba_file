#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态线程池调度器
根据文件数量、文件大小、历史耗时动态计算最优并发数。
"""

import os
from typing import List, Tuple

from .utils import LOGGER


class DynamicPoolScheduler:
    """
    动态线程/进程池调度器

    调度因子：
    1. 文件数量 — 少量文件减少并发，避免进程启动开销
    2. 文件大小 — 大文件占用更多资源，自动降低并发
    3. 历史耗时 — 参考最近几轮的平均处理速度，自适应调整
    4. CPU / 连接池上限 — 硬性约束
    """

    def __init__(self, max_workers: int, pool_max: int, pool_cfg: dict):
        self.max_workers = max_workers
        self.pool_max = pool_max
        self.pool_cfg = pool_cfg
        self.min_workers = pool_cfg.get('min_workers', 1)
        self._history: List[Tuple[int, float, int]] = []

    def calculate(self, files: List[str], input_path: str) -> int:
        """根据当前任务情况计算最优并发数"""
        if not self.pool_cfg.get('enabled', True):
            return max(1, min(self.max_workers, len(files)))

        total = len(files)
        if total == 0:
            return 0

        base = self._base_from_count(total)
        size_adjusted = self._adjust_by_file_size(base, files, input_path)
        history_adjusted = self._adjust_by_history(size_adjusted, total)
        final = self._clamp(history_adjusted)

        LOGGER.info(
            f"[调度] 文件数={total}, 基础={base}, "
            f"大小调整={size_adjusted}, 历史调整={history_adjusted}, "
            f"最终={final}"
        )
        return final

    def _base_from_count(self, total: int) -> int:
        if total <= 1:
            return 1
        if total <= 3:
            return total
        if total <= self.max_workers:
            return total
        return self.max_workers

    def _adjust_by_file_size(self, base: int, files: List[str], input_path: str) -> int:
        threshold = self.pool_cfg.get('file_size_threshold', 50) * 1024 * 1024
        weight = self.pool_cfg.get('large_file_workers', 2)
        total_weight = 0

        for fname in files:
            fpath = os.path.join(input_path, fname)
            try:
                if os.path.getsize(fpath) > threshold:
                    total_weight += weight
                else:
                    total_weight += 1
            except OSError:
                total_weight += 1

        if total_weight > 0:
            adjusted = max(1, int(self.max_workers * len(files) / total_weight))
        else:
            adjusted = base
        return min(adjusted, base)

    def _adjust_by_history(self, current: int, total: int) -> int:
        window = self.pool_cfg.get('history_window', 5)
        recent = self._history[-window:]
        if len(recent) < 2:
            return current

        total_files_hist = sum(h[0] for h in recent)
        total_time_hist = sum(h[1] for h in recent)
        if total_files_hist == 0:
            return current

        avg = total_time_hist / total_files_hist
        if avg < 1.0:
            factor = 1.2
        elif avg < 5.0:
            factor = 1.0
        elif avg < 15.0:
            factor = 0.8
        else:
            factor = 0.6

        return max(self.min_workers, int(current * factor))

    def _clamp(self, value: int) -> int:
        value = min(value, self.max_workers)
        value = min(value, max(1, self.pool_max - 1))
        return max(self.min_workers, value)

    def record_round(self, file_count: int, elapsed: float, pool_size: int):
        """记录一轮历史数据"""
        self._history.append((file_count, elapsed, pool_size))
        if len(self._history) > 20:
            self._history = self._history[-20:]
