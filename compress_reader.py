#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
压缩文件读取器
统一支持 .gz / .zip / 普通文本文件的逐行读取，无需解压到磁盘。
"""

import os
import gzip
import zipfile
import io
from typing import Iterator


class CompressedFileReader:
    """
    压缩文件统一读取器

    支持：
    - .gz  : gzip 流式读取
    - .zip : 内存解压，逐行迭代
    - 普通文本: 直接读取
    """

    @staticmethod
    def read_lines(file_path: str, encoding: str = 'utf-8') -> Iterator[str]:
        """
        读取压缩文件，返回行迭代器

        Args:
            file_path: 文件路径
            encoding: 文件编码

        Yields:
            str: 文件的每一行
        """
        if not os.path.exists(file_path):
            raise IOError(f"文件不存在: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.gz':
            yield from CompressedFileReader._read_gz(file_path, encoding)
        elif ext == '.zip':
            yield from CompressedFileReader._read_zip(file_path, encoding)
        else:
            with open(file_path, 'r', encoding=encoding) as f:
                yield from f

    @staticmethod
    def _read_gz(file_path: str, encoding: str) -> Iterator[str]:
        with gzip.open(file_path, 'rt', encoding=encoding) as f:
            yield from f

    @staticmethod
    def _read_zip(file_path: str, encoding: str) -> Iterator[str]:
        """读取 .zip（内存解压，不解压到磁盘）"""
        with zipfile.ZipFile(file_path, 'r') as zf:
            file_list = [name for name in zf.namelist() if not name.endswith('/')]
            if not file_list:
                raise ValueError(f"ZIP 文件为空: {file_path}")
            with zf.open(file_list[0]) as inner:
                text_io = io.TextIOWrapper(inner, encoding=encoding)
                yield from text_io

    @staticmethod
    def get_inner_filename(file_path: str) -> str:
        """获取压缩文件内的实际文件名"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.zip':
            with zipfile.ZipFile(file_path, 'r') as zf:
                file_list = [name for name in zf.namelist() if not name.endswith('/')]
                return file_list[0] if file_list else os.path.basename(file_path)
        return os.path.basename(file_path)
