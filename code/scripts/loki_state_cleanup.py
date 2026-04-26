#!/usr/bin/env python3
"""Loki state.json 一次性清洗工具

修复 fingerprint 152K vs 库容 63K 差额（详见 OB 笔记 202604261735+Loki-fingerprint差额追溯）：
  - 剔除 mtime 变更/失败/空文件残留 fingerprint
  - 补回已入库但 state 未持久化的 id

策略：state_new = chroma_summaries_ids ∪ chroma_ddl_ids
原 state.json 备份到 loki_state.json.bak.<ts>。

CLI:
  python loki_state_cleanup.py --dry-run          # 只报告，不写
  python loki_state_cleanup.py --apply            # 备份 + 实际清洗
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_STATE = Path.home() / "Work/projects/knowledge-rag-知识库/code/scripts/logs/loki_state.json"
DEFAULT_CHROMA = Path.home() / "Work/data/vectors/data/chroma-doc-knowledge-bge"
SUMMARIES_COL = "doc_knowledge_bge_m3"
DDL_COL = "ddl_schema_bge_m3"


@dataclass
class CleanupReport:
    state_size: int
    summaries_size: int
    ddl_size: int
    state_new_size: int
    removed: int
    added: int

    def to_text(self) -> str:
        return (
            f"原 state: {self.state_size}\n"
            f"chroma summaries ids: {self.summaries_size}\n"
            f"chroma ddl ids: {self.ddl_size}\n"
            f"清洗后 state: {self.state_new_size}\n"
            f"  剔除: {self.removed}\n"
            f"  补回: {self.added}\n"
        )


def load_state_ids(path: Path) -> set:
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")))


def fetch_chroma_ids(chroma_path: Path, col_name: str) -> set:
    import chromadb
    client = chromadb.PersistentClient(path=str(chroma_path))
    try:
        col = client.get_collection(col_name)
    except Exception:
        return set()
    ids = set()
    offset = 0
    batch = 10000
    while True:
        got = col.get(include=[], limit=batch, offset=offset)
        chunk = got.get("ids") or []
        if not chunk:
            break
        ids.update(chunk)
        if len(chunk) < batch:
            break
        offset += batch
    return ids


def compute_new_state(
    state_old: Iterable[str],
    summaries_ids: Iterable[str],
    ddl_ids: Iterable[str],
) -> tuple:
    """state_new = summaries_ids ∪ ddl_ids（chroma 真值）。返回 (new_set, report)。"""
    state_old_set = set(state_old)
    summaries_set = set(summaries_ids)
    ddl_set = set(ddl_ids)
    state_new = summaries_set | ddl_set

    removed = len(state_old_set - state_new)
    added = len(state_new - state_old_set)

    return state_new, CleanupReport(
        state_size=len(state_old_set),
        summaries_size=len(summaries_set),
        ddl_size=len(ddl_set),
        state_new_size=len(state_new),
        removed=removed,
        added=added,
    )


def backup_state(state_path: Path, ts: Optional[str] = None) -> Path:
    if ts is None:
        ts = time.strftime("%Y%m%d%H%M%S")
    bak = state_path.with_suffix(state_path.suffix + f".bak.{ts}")
    bak.write_bytes(state_path.read_bytes())
    return bak


def write_state(state_path: Path, ids: Iterable[str]) -> None:
    state_path.write_text(json.dumps(sorted(ids)), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Loki state.json 一次性清洗")
    ap.add_argument("--state", default=str(DEFAULT_STATE))
    ap.add_argument("--chroma", default=str(DEFAULT_CHROMA))
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写")
    ap.add_argument("--apply", action="store_true", help="备份 + 写入新 state")
    args = ap.parse_args(argv)

    if not args.dry_run and not args.apply:
        ap.error("必须指定 --dry-run 或 --apply 之一")

    state_path = Path(args.state)
    chroma_path = Path(args.chroma)

    state_old = load_state_ids(state_path)
    print(f"读取 state: {len(state_old)} ids @ {state_path}")

    summaries_ids = fetch_chroma_ids(chroma_path, SUMMARIES_COL)
    print(f"读取 chroma {SUMMARIES_COL}: {len(summaries_ids)} ids")
    ddl_ids = fetch_chroma_ids(chroma_path, DDL_COL)
    print(f"读取 chroma {DDL_COL}: {len(ddl_ids)} ids")

    state_new, report = compute_new_state(state_old, summaries_ids, ddl_ids)

    print()
    print(report.to_text())

    if args.dry_run:
        print("--dry-run 模式，未写文件。")
        return 0

    bak = backup_state(state_path)
    write_state(state_path, state_new)
    print(f"✅ 备份: {bak}")
    print(f"✅ 写入: {state_path} ({len(state_new)} ids)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
