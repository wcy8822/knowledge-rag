#!/usr/bin/env python3
"""Loki ↔ Claude 反馈闭环 Phase 1: query 日志写入

每次 MCP 知识检索类工具调用后，追加一行 JSONL 到 ~/Work/projects/knowledge-rag-知识库/logs/queries.jsonl。
设计目标：
- 非阻塞：任何写入失败一律吞掉，不影响 MCP 响应
- 追加模式：单条写完即关，避免长事务
- 字段精简：ts/tool/query/n_requested/n_returned/top_files/latency_ms[/extra]
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_LOG_PATH = Path.home() / "Work/projects/knowledge-rag-知识库/logs/queries.jsonl"


@dataclass(frozen=True)
class QueryLogEntry:
    ts: str
    tool: str
    query: str
    n_requested: int
    n_returned: int
    top_files: tuple
    latency_ms: int
    extra: dict = field(default_factory=dict)

    def to_jsonl(self) -> str:
        d = asdict(self)
        d["top_files"] = list(self.top_files)
        return json.dumps(d, ensure_ascii=False)


def build_entry(
    tool: str,
    query: str,
    n_requested: int,
    n_returned: int,
    top_files: Iterable[str],
    latency_ms: int,
    extra: Optional[dict] = None,
    ts: Optional[str] = None,
) -> QueryLogEntry:
    """构造一条 query log 条目（不可变）。"""
    if ts is None:
        ts = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())
    files = list(top_files or [])[:10]
    return QueryLogEntry(
        ts=ts,
        tool=str(tool),
        query=str(query)[:500],
        n_requested=int(n_requested),
        n_returned=int(n_returned),
        top_files=tuple(str(f) for f in files),
        latency_ms=int(latency_ms),
        extra=dict(extra or {}),
    )


def write_entry(entry: QueryLogEntry, log_path: Optional[Path] = None) -> bool:
    """以追加模式写入一行 JSONL。失败返回 False（吞掉异常）。"""
    target = Path(log_path) if log_path else DEFAULT_LOG_PATH
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(entry.to_jsonl() + "\n")
        return True
    except Exception as e:
        sys.stderr.write(f"[query_logger] 写入失败: {e}\n")
        return False


def log_query(
    tool: str,
    query: str,
    n_requested: int,
    n_returned: int,
    top_files: Iterable[str],
    latency_ms: int,
    extra: Optional[dict] = None,
    log_path: Optional[Path] = None,
) -> bool:
    """便捷入口：构造 + 写入。失败不抛。"""
    try:
        entry = build_entry(
            tool=tool,
            query=query,
            n_requested=n_requested,
            n_returned=n_returned,
            top_files=top_files,
            latency_ms=latency_ms,
            extra=extra,
        )
        return write_entry(entry, log_path=log_path)
    except Exception as e:
        sys.stderr.write(f"[query_logger] 构造失败: {e}\n")
        return False


class QueryTimer:
    """with 语境下的毫秒级计时器。"""

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.latency_ms = int((time.perf_counter() - self._start) * 1000)
        return False
