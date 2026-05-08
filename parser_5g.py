#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
5G 北向文件解析器
"""

import os
import time
import traceback
from typing import Dict, List, Optional

from .base_parser import BaseFileParser
from .compress_reader import CompressedFileReader
from .db import get_table_columns, pg_batch_insert
from .parse_logs import is_file_parsed, log_parsed_file
from .utils import (
    LOGGER, extract_omc_name, extract_date_from_filename,
    get_table_type_5g, normalize_cell_id_5g, safe_float,
)


class Parser5G(BaseFileParser):

    _HANDLER_MAP = {
        'nrcellduphysical':   '_handle_nrcellduphysical',
        'nrcellcuphysical':   '_handle_nrcellcuphysical',
        'nrcellcu':           '_handle_nrcellcu',
        'nrcelldu':           '_handle_nrcelldu',
        'inventoryunitrru':   '_handle_inventoryunitrru',
        'inventoryunitshelf': '_handle_inventoryunitshelf',
    }

    def parse_file(self, input_path: str, filename: str, parsed_path: str,
                   total: int, index: int) -> int:
        mode = '5g'
        file_path = os.path.join(input_path, filename)
        omc_name = extract_omc_name(filename)
        date_str = extract_date_from_filename(filename)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        if is_file_parsed(filename, self.pool_mgr, self.pg_config, mode):
            LOGGER.info(f"[5G] 文件已解析，跳过: {filename} [{index}/{total}]")
            if os.path.exists(file_path):
                self._move_to_parsed(file_path, filename, parsed_path, date_str, omc_name)
            return 0

        start = time.time()
        table_type = get_table_type_5g(filename)
        rows_inserted = 0

        try:
            if table_type:
                data_dict = self._read_and_parse(file_path, omc_name, table_type)
                if data_dict:
                    columns = get_table_columns(table_type, self.pool_mgr, self.pg_config)
                    if columns:
                        rows_inserted = self._insert_data(data_dict, columns, table_type)
                    else:
                        LOGGER.warning(f"无法获取表 {table_type} 的列名")
            else:
                LOGGER.warning(f"无法识别 5G 文件类型: {filename}")

            log_parsed_file(filename, rows_inserted, self.pool_mgr, self.pg_config,
                            mode, omc=omc_name, file_size=file_size)

            if os.path.exists(file_path):
                self._move_to_parsed(file_path, filename, parsed_path, date_str, omc_name)

            elapsed = time.time() - start
            LOGGER.info(f"[5G] {omc_name} {table_type} 完成, "
                        f"写入 {rows_inserted} 行, 耗时 {elapsed:.2f}s [{index}/{total}]")
            return rows_inserted

        except Exception as e:
            LOGGER.error(f"[5G] 处理文件失败 {filename}: {e}")
            log_parsed_file(filename, 0, self.pool_mgr, self.pg_config,
                            mode, omc=omc_name, status='failed',
                            error_msg=str(e)[:500], file_size=file_size)
            traceback.print_exc()
            return 0

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _read_and_parse(self, file_path: str, omc_name: str,
                        table_type: str) -> Dict[str, Dict]:
        data_dict, title = {}, {}
        handler = self._get_handler(table_type)

        for line in CompressedFileReader.read_lines(file_path):
            if 'UserLabel' in line or 'StartTime' in line or 'rmUID' in line:
                tt = line.split("|")
                for n in range(4, len(tt)):
                    title[n] = tt[n].replace("\n", '').replace(".", '_').lower()
                continue

            if 'CMCC-YJ-' not in line:
                continue
            if '46000-' not in line and table_type not in ('inventoryunitrru', 'inventoryunitshelf'):
                continue

            tt = line.split("|")
            segments = tt[1].split(",") if len(tt) > 1 else []
            if handler:
                handler(tt, segments, title, omc_name, data_dict)

        return data_dict

    # ---------- 策略模式：每种表类型一个 handler ----------

    def _get_handler(self, table_type: str):
        method_name = self._HANDLER_MAP.get(table_type)
        return getattr(self, method_name) if method_name else None

    def _common_fields(self, tt, segments, omc_name):
        return {
            'rmuid': tt[0], 'start_time': tt[3],
            'gnb': segments[2].replace("ManagedElement=", "") if len(segments) > 2 else '',
            'userlabel': tt[2].replace('"', ''), 'omcr': omc_name,
        }

    def _add_counters(self, tt, title, data_dict, key, as_float=True):
        for n in range(4, len(tt)):
            if n in title:
                data_dict[key][title[n]] = safe_float(tt[n]) if as_float else tt[n].replace("\n", '')

    def _handle_nrcellduphysical(self, tt, segments, title, omc_name, dd):
        k = normalize_cell_id_5g(segments[3].replace("NRCellDUPhysical", "")) if len(segments) > 3 else ''
        if k not in dd:
            dd[k] = self._common_fields(tt, segments, omc_name)
            dd[k]['phyid'] = tt[2].replace('"', '').replace("NRCellDUPhysical=", "")
            dd[k]['ncgi'] = k
            self._add_counters(tt, title, dd, k)

    def _handle_nrcellcuphysical(self, tt, segments, title, omc_name, dd):
        k = normalize_cell_id_5g(segments[3].replace("NRCellCUPhysical", "")) if len(segments) > 3 else ''
        if k not in dd:
            dd[k] = self._common_fields(tt, segments, omc_name)
            dd[k]['phyid'] = tt[2].replace('"', '').replace("NRCellCUPhysical=", "")
            dd[k]['ncgi'] = k
            self._add_counters(tt, title, dd, k, as_float=False)

    def _handle_nrcellcu(self, tt, segments, title, omc_name, dd):
        k = normalize_cell_id_5g(segments[4].replace("NRCellCU=", "")) if len(segments) > 4 else ''
        if k not in dd:
            gnbcu = segments[3].replace("GNBCUCPFunction=", "") if len(segments) > 3 else ''
            dd[k] = self._common_fields(tt, segments, omc_name)
            dd[k]['lcrid'] = segments[4].replace('NRCellCU=', '').replace(gnbcu + "-", "") if len(segments) > 4 else ''
            dd[k]['ncgi'] = k
            self._add_counters(tt, title, dd, k)

    def _handle_nrcelldu(self, tt, segments, title, omc_name, dd):
        k = normalize_cell_id_5g(segments[4].replace("NRCellDU=", "")) if len(segments) > 4 else ''
        if k not in dd:
            gnbcu = segments[3].replace("GNBDUFunction=", "") if len(segments) > 3 else ''
            dd[k] = self._common_fields(tt, segments, omc_name)
            dd[k]['lcrid'] = segments[4].replace('NRCellDU=', '').replace(gnbcu + "-", "") if len(segments) > 4 else ''
            dd[k]['ncgi'] = k
            self._add_counters(tt, title, dd, k)

    def _handle_inventoryunitrru(self, tt, segments, title, omc_name, dd):
        gnb = segments[2].replace("ManagedElement=", "") if len(segments) > 2 else ''
        inv = segments[3].replace("InventoryUnitRru=", "") if len(segments) > 3 else ''
        k = f"{gnb}-{inv}"
        if k not in dd:
            dd[k] = self._common_fields(tt, segments, omc_name)
            dd[k]['inventoryunitrru'] = inv
            dd[k]['ncgi'] = k
            self._add_counters(tt, title, dd, k)

    def _handle_inventoryunitshelf(self, tt, segments, title, omc_name, dd):
        gnb = segments[2].replace("ManagedElement=", "") if len(segments) > 2 else ''
        rack = segments[3].replace("InventoryUnitRack=", "") if len(segments) > 3 else ''
        shelf = segments[4].replace("InventoryUnitShelf=", "") if len(segments) > 4 else ''
        k = f"{gnb}-{rack}-{shelf}"
        if k not in dd:
            dd[k] = self._common_fields(tt, segments, omc_name)
            dd[k]['inventoryunitrack'] = rack
            dd[k]['inventoryunitshelf'] = shelf
            dd[k]['ncgi'] = k
            self._add_counters(tt, title, dd, k)

    # ---------- 入库 ----------

    def _insert_data(self, data_dict: Dict, columns: List[str], table_type: str) -> int:
        col_lower_map = {c.lower(): c for c in columns}
        rmuid_idx = None
        for i, col in enumerate(columns):
            if col.lower() == 'rmuid':
                rmuid_idx = i
                break
        rows, skipped = [], 0

        for key, item in data_dict.items():
            item_key_map = {k.lower(): v for k, v in item.items()}
            row = []
            for col in columns:
                val = item_key_map.get(col.lower())
                row.append(val if val not in (None, '') else None)

            if rmuid_idx is not None and row[rmuid_idx] in (None, ''):
                skipped += 1
                continue
            rows.append(tuple(row))

        if rows:
            col_str = ','.join([f'"{c}"' for c in columns])
            sql = f'INSERT INTO {table_type} ({col_str}) VALUES %s ON CONFLICT DO NOTHING'
            pg_batch_insert(self.pool_mgr, self.pg_config, sql, rows,
                            page_size=self.config.batch_page_size)

        if skipped:
            LOGGER.warning(f"[5G] 跳过 {skipped} 行（rmUID 为 NULL）")
        return len(rows)
