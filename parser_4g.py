#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4G 北向文件解析器
"""

import os
import re
import time
import traceback
from typing import Dict, List, Optional

from .base_parser import BaseFileParser
from .compress_reader import CompressedFileReader
from .db import get_table_columns, pg_batch_insert
from .parse_logs import is_file_parsed, log_parsed_file
from .utils import (
    LOGGER, extract_omc_name, extract_date_from_filename,
    get_tech_type_4g,
)


class Parser4G(BaseFileParser):
    """4G 北向文件解析器"""

    def parse_file(self, input_path: str, filename: str, parsed_path: str,
                   total: int, index: int) -> int:
        mode = '4g'
        file_path = os.path.join(input_path, filename)
        omc_name = extract_omc_name(filename)
        tech_type = get_tech_type_4g(filename)
        date_str = extract_date_from_filename(filename)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        # 去重
        if is_file_parsed(filename, self.pool_mgr, self.pg_config, mode):
            LOGGER.info(f"[4G] 文件已解析，跳过: {filename} [{index}/{total}]")
            if os.path.exists(file_path):
                self._move_to_parsed(file_path, filename, parsed_path,
                                     date_str, omc_name, tech_type)
            return 0

        start = time.time()
        try:
            data_list = self._read_and_parse(file_path, omc_name)
            rows_inserted = self._insert_data(data_list) if data_list else 0

            log_parsed_file(filename, rows_inserted, self.pool_mgr, self.pg_config,
                            mode, omc=omc_name, file_size=file_size)

            if os.path.exists(file_path):
                self._move_to_parsed(file_path, filename, parsed_path,
                                     date_str, omc_name, tech_type)

            elapsed = time.time() - start
            LOGGER.info(f"[4G] {omc_name} {tech_type} 完成, "
                        f"写入 {rows_inserted} 行, 耗时 {elapsed:.2f}s [{index}/{total}]")
            return rows_inserted

        except Exception as e:
            LOGGER.error(f"[4G] 处理文件失败 {filename}: {e}")
            log_parsed_file(filename, 0, self.pool_mgr, self.pg_config,
                            mode, omc=omc_name, status='failed',
                            error_msg=str(e)[:500], file_size=file_size)
            traceback.print_exc()
            return 0

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _read_and_parse(self, file_path: str, omc_name: str) -> List[Dict]:
        rules = self.config.filter_rules_4g
        is_full = omc_name.lower().startswith(rules['full_omcr_prefix'].lower())
        filter_kw = rules['filter_keyword']
        counter_set = set(c.lower() for c in self.config.counter_list_4g) if self.config.counter_list_4g else None

        data_list = []
        title = {}
        title_parsed = False

        for line in CompressedFileReader.read_lines(file_path):
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) < 4:
                continue

            if not title_parsed and 'rmUID' in parts[0]:
                for i in range(4, len(parts)):
                    col_name = parts[i].replace('\n', '').replace('.', '_')
                    if counter_set is None or col_name.lower() in counter_set:
                        title[i] = col_name
                title_parsed = True
                continue

            user_label = parts[2].replace('"', '')
            if not is_full and filter_kw not in user_label:
                continue

            enb_info = self._extract_enb_cell(parts)
            if not enb_info:
                continue

            row = {
                'rmuid': parts[0], 'start_time': parts[3],
                'enbid': enb_info['enbid'], 'lcrid': enb_info['lcrid'],
                'cellname': user_label, 'omcr': omc_name,
            }
            for i in range(4, len(parts)):
                if i in title:
                    val = parts[i].replace('\n', '')
                    row[title[i]] = val if val not in ('', '-', 'None') else None

            data_list.append(row)
        return data_list

    def _extract_enb_cell(self, parts: List[str]) -> Optional[Dict]:
        """从 DN 字段提取 enbid 和 lcrid"""
        enbid = lcrid = None
        for segment in parts[1].split(","):
            segment = segment.strip()
            if "EnbFunction=" in segment:
                enbid = self._extract_int(segment.replace("EnbFunction=", ""))
            elif "EutranCellFdd=" in segment:
                lcrid = self._extract_int(segment.replace("EutranCellFdd=", ""))
            elif "EutranCellTdd=" in segment:
                lcrid = self._extract_int(segment.replace("EutranCellTdd=", ""))
        return {'enbid': enbid, 'lcrid': lcrid} if enbid is not None and lcrid is not None else None

    @staticmethod
    def _extract_int(value: str) -> Optional[int]:
        if value.isdigit():
            return int(value)
        if '-' in value:
            parts = value.split('-')
            if parts[-1].isdigit():
                return int(parts[-1])
        nums = re.findall(r'\d+', value)
        return int(max(nums, key=len)) if nums else None

    def _insert_data(self, data_list: List[Dict]) -> int:
        table = self.config.target_table_4g
        columns = get_table_columns(table, self.pool_mgr, self.pg_config)
        if not columns:
            LOGGER.warning(f"无法获取表 {table} 的列名")
            return 0

        lower_cols = [c.lower() for c in columns]
        col_lower_map = {c.lower(): i for i, c in enumerate(columns)}
        rmuid_idx = col_lower_map.get('rmuid')
        rows, skipped = [], 0

        for item in data_list:
            item_lower = {k.lower(): v for k, v in item.items()}
            row = []
            for col in columns:
                val = item_lower.get(col.lower())
                row.append(val if val not in (None, '') else None)

            if rmuid_idx is not None and row[rmuid_idx] in (None, ''):
                skipped += 1
                continue
            rows.append(tuple(row))

        if rows:
            col_str = ','.join([f'"{c}"' for c in columns])
            sql = f'INSERT INTO {table} ({col_str}) VALUES %s ON CONFLICT DO NOTHING'
            pg_batch_insert(self.pool_mgr, self.pg_config, sql, rows,
                            page_size=self.config.batch_page_size)

        if skipped:
            LOGGER.warning(f"跳过 {skipped} 行（rmUID 为 NULL）")
        return len(rows)
