#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyInstaller 打包配置
用法: pyinstaller build.spec
"""

import os
from PyInstaller.utils.hooks import collect_data_files

APP_ROOT = os.path.dirname(os.path.abspath(__file__))

a = Analysis(
    ['unified_parser.py'],
    pathex=[APP_ROOT],
    binaries=[],
    datas=[
        # 把配置文件和建表脚本打包进去（作为数据文件）
        (os.path.join(APP_ROOT, 'conf.yaml'), '.'),
        (os.path.join(APP_ROOT, 'init_tables.sql'), '.'),
    ],
    hiddenimports=[
        'psycopg2',
        'psycopg2.extensions',
        'psycopg2.extras',
        'yaml',
        'gzip',
        'zipfile',
        'config',
        'db',
        'utils',
        'scheduler',
        'parse_logs',
        'base_parser',
        'parser_4g',
        'parser_5g',
        'compress_reader',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='unified_parser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # 保留控制台窗口，方便看日志
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
