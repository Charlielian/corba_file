# 北向文件统一解析器（4G + 5G）

一套代码同时处理 4G 和 5G 北向数据文件解析入库。

## 功能特性

- **统一解析**：4G/5G 一套代码，配置驱动
- **多格式支持**：.gz / .zip 压缩文件直接读取，无需解压到磁盘
- **动态并发**：根据文件数量、大小、历史耗时自动调整并发数
- **去重机制**：已解析文件记录到数据库，避免重复入库
- **自动清理**：定期清理过期文件和日志
- **PostgreSQL**：统一使用 PostgreSQL + 连接池

## 目录结构

```
unified_parser/
├── conf.yaml              # 配置文件（YAML）
├── init_tables.sql        # 建表脚本
├── unified_parser.py      # 入口脚本
├── config.py              # 配置加载
├── db.py                  # 数据库操作
├── compress_reader.py     # 压缩文件读取
├── utils.py               # 工具函数
├── scheduler.py           # 动态调度器
├── parse_logs.py          # 解析日志管理
├── base_parser.py         # 解析器基类
├── parser_4g.py           # 4G 解析器
└── parser_5g.py           # 5G 解析器
```

## 快速开始

### 1. 安装依赖

```bash
pip install psycopg2-binary pyyaml
```

### 2. 创建数据库表

```bash
psql -U postgres -f init_tables.sql
```

### 3. 修改配置

编辑 `conf.yaml`，配置数据库连接和文件路径。

### 4. 运行

```bash
# 同时运行 4G + 5G
python unified_parser.py

# 只运行 4G
python unified_parser.py --4g-only

# 只运行 5G
python unified_parser.py --5g-only

# 只跑一轮（适合定时任务）
python unified_parser.py --once
```

## 配置说明

```yaml
global:
  worker_processes: 10        # 最大并发进程数
  log_retention_days: 30      # 日志保留天数
  dynamic_pool:               # 动态并发配置
    enabled: true
    min_workers: 1
    max_workers: null         # null = 使用 worker_processes
    file_size_threshold: 50   # 大文件阈值（MB）
    large_file_workers: 2     # 大文件等效占用的 worker 数

postgres_config:
  host: localhost
  port: 5432
  user: postgres
  password: "10300"
  database: postgres

4g:
  input_path: /path/to/4g/input
  parsed_path: /path/to/4g/output
  target_table: pp_cell
  filter_rules:
    full_omcr_prefix: omcr7   # 此前缀的 OMC 全部入库
    filter_keyword: 阳江      # 其他 OMC 只入库包含此关键字的小区

5g:
  input_path: /path/to/5g/input
  parsed_path: /path/to/5g/output
```

## 作者

charlie
