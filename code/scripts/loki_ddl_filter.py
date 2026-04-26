#!/usr/bin/env python3
"""DDL 入库前过滤：跳过备份/归档/临时表

设计原则（保守 — 宁可漏过滤，不要误杀业务表）：
  1. 整库黑名单：_archive / _trash / _staging 等以下划线开头的归档库
  2. 表名硬模式：_backup / _bak / _old / _staging / _tmp / _temp
     用 word boundary 避免误伤 backup_strategy_log 之类合法表
  3. 不过滤 _v2 / _new / 日期后缀（信号弱，可能是合法版本表）

调用：loki_pipeline.run_ddl 在 todo 生成处调；loki_chroma_gc ddl-blacklist 模式批量删。
"""

from __future__ import annotations

import re
from typing import Iterable

EXCLUDED_DB_PREFIXES = ("_archive", "_trash", "_staging")

_TABLE_EXCLUDE_RE = re.compile(
    r"(_backup(_\d+)?(_\d+)?$|_backup_|_bak$|_bak_|_bk$|_old$|_old_|_staging$|_tmp$|_temp$)",
    re.IGNORECASE,
)


def is_excluded_db(db: str) -> bool:
    if not db:
        return False
    return any(db.startswith(p) for p in EXCLUDED_DB_PREFIXES)


def is_excluded_table_name(table: str) -> bool:
    if not table:
        return False
    return bool(_TABLE_EXCLUDE_RE.search(table))


def is_excluded_table(db: str, table: str) -> bool:
    """库 + 表 综合判定。任一命中即排除。"""
    return is_excluded_db(db) or is_excluded_table_name(table)


def filter_pairs(pairs: Iterable[tuple]) -> list:
    """从 (db, table, ...) 序列里剔除被排除的，保持原顺序。"""
    out = []
    for p in pairs:
        if len(p) < 2:
            continue
        if not is_excluded_table(p[0], p[1]):
            out.append(p)
    return out
