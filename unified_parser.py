#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北向文件统一解析器（4G + 5G）— 入口脚本
==========================================

功能分散到各子模块：
  config.py          配置加载（YAML）
  db.py              数据库连接池与操作
  compress_reader.py 压缩文件读取（.gz / .zip）
  utils.py           通用工具函数
  scheduler.py       动态线程池调度
  parse_logs.py      解析日志表管理
  base_parser.py     解析器抽象基类
  parser_4g.py       4G 解析器
  parser_5g.py       5G 解析器

使用方法：
    python unified_parser.py              # 同时运行 4G + 5G
    python unified_parser.py --4g-only    # 只运行 4G
    python unified_parser.py --5g-only    # 只运行 5G
    python unified_parser.py --once       # 只跑一轮就退出

作者：charlie
版本：2.0（模块化 + YAML 配置）
日期：2026-05-08
"""

import os
import sys
import argparse
import traceback
import multiprocessing
import concurrent.futures
import time

# 将脚本所在目录加入 path，确保包导入正常
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from db import ConnectionPoolManager, init_pool
from utils import setup_logger, LOGGER, ensure_dir, clean_old_files
from parse_logs import init_parse_logs, clean_parse_logs
from scheduler import DynamicPoolScheduler
from parser_4g import Parser4G
from parser_5g import Parser5G


def _worker_init(pg_config, pool_min, pool_max):
    init_pool(pg_config, pool_min, pool_max)


def run_parser_loop(parser, input_path, parsed_path, label, once=False):
    ensure_dir(parsed_path)
    idle_count = 0
    scheduler = DynamicPoolScheduler(
        max_workers=parser.config.worker_processes,
        pool_max=parser.config.pool_max,
        pool_cfg=parser.config.dynamic_pool,
    )

    pg_config = parser.pg_config
    pool_min = parser.config.pool_min
    pool_max = parser.config.pool_max

    executor = None

    while True:
        try:
            files = [f for f in os.listdir(input_path)
                     if f.endswith('.gz') or f.endswith('.zip')]
            total = len(files)

            if total > 0:
                idle_count = 0
                pool_size = scheduler.calculate(files, input_path)
                LOGGER.info(f"[{label}] 本轮待解析: {total} 个文件, 动态并发数: {pool_size}")

                if executor is not None:
                    executor.shutdown(wait=True)
                executor = concurrent.futures.ProcessPoolExecutor(
                    max_workers=pool_size,
                    initializer=_worker_init,
                    initargs=(pg_config, pool_min, pool_max),
                )

                start = time.time()
                futures = []
                for i, fname in enumerate(files, 1):
                    fut = executor.submit(parser.parse_file,
                                          input_path, fname, parsed_path, total, i)
                    futures.append(fut)

                for fut in concurrent.futures.as_completed(futures):
                    try:
                        fut.result()
                    except Exception as exc:
                        LOGGER.error(f"[{label}] 子任务异常: {exc}")

                elapsed = time.time() - start
                scheduler.record_round(total, elapsed, pool_size)
                LOGGER.info(f"[{label}] 本轮完成, 耗时 {elapsed:.2f}s, "
                            f"平均 {elapsed / total:.2f}s/文件")
                time.sleep(10)
            else:
                idle_count += 1
                if once and idle_count >= 1:
                    LOGGER.info(f"[{label}] 守护模式关闭，退出")
                    break
                if idle_count >= 5:
                    LOGGER.info(f"[{label}] 连续 5 轮无新文件，退出")
                    break
                time.sleep(30)

        except KeyboardInterrupt:
            LOGGER.warning(f"[{label}] 用户中断")
            break
        except Exception as e:
            LOGGER.error(f"[{label}] 主循环出错: {e}")
            traceback.print_exc()
            time.sleep(30)

    if executor is not None:
        executor.shutdown(wait=True)


def main():
    ap = argparse.ArgumentParser(description='北向文件统一解析器（4G + 5G）')
    ap.add_argument('--4g-only', action='store_true', help='只运行 4G')
    ap.add_argument('--5g-only', action='store_true', help='只运行 5G')
    ap.add_argument('--once', action='store_true', help='只跑一轮')
    ap.add_argument('--config', default='conf.yaml', help='配置文件路径')
    args = ap.parse_args()

    run_4g = not args._5g_only
    run_5g = not args._4g_only

    config = Config(args.config)

    base_path = os.path.dirname(os.path.abspath(__file__))
    setup_logger(base_path, config.log_retention_days)

    LOGGER.info("=" * 60)
    LOGGER.info("北向文件统一解析器启动 (v2.0 模块化)")
    mode_str = '4G+5G' if run_4g and run_5g else '仅4G' if run_4g else '仅5G'
    LOGGER.info(f"模式: {mode_str} | 守护: {'否' if args.once else '是'}")
    LOGGER.info("=" * 60)

    pool_mgr = ConnectionPoolManager(config.pg_config, config.pool_min, config.pool_max)

    try:
        if run_4g:
            init_parse_logs(pool_mgr, config.pg_config, '4g')
        if run_5g:
            init_parse_logs(pool_mgr, config.pg_config, '5g')

        parsers = []
        if run_4g:
            parsers.append(('4G', Parser4G(config, pool_mgr),
                            config.input_path_4g, config.parsed_path_4g))
        if run_5g:
            parsers.append(('5G', Parser5G(config, pool_mgr),
                            config.input_path_5g, config.parsed_path_5g))

        processes = []
        for label, p, inp, out in parsers:
            proc = multiprocessing.Process(
                target=run_parser_loop,
                args=(p, inp, out, label, args.once),
                name=f"parser_{label}", daemon=True,
            )
            proc.start()
            processes.append(proc)
            LOGGER.info(f"[{label}] 解析进程已启动 (PID: {proc.pid})")

        for proc in processes:
            proc.join()

        if run_4g:
            clean_old_files(config.parsed_path_4g, config.parsed_retention_days_4g)
        if run_5g:
            clean_old_files(config.parsed_path_5g, config.parsed_retention_days_5g)
            clean_parse_logs(pool_mgr, config.pg_config, '5g', config.logs_retention_days_5g)

    except Exception as e:
        LOGGER.error(f"程序异常: {e}")
        traceback.print_exc()
    finally:
        pool_mgr.closeall()
        LOGGER.info("程序退出")


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
