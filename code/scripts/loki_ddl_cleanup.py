#!/usr/bin/env python3
"""一次性清理 chroma ddl_schema_bge_m3 中的备份/归档/临时表 DDL

按 loki_ddl_filter.is_excluded_table 标准识别脏数据。删除前导出
(id + db + table + metadata + document_preview) 到 logs/loki_ddl_cleanup.<ts>.jsonl。
同步剔除 state.json v2.ddl 中被删 ids。

CLI:
  loki_ddl_cleanup.py --dry-run     # 默认：只报告
  loki_ddl_cleanup.py --apply       # 备份 + 删除 + 同步 state
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loki_ddl_filter import is_excluded_table  # noqa: E402

DEFAULT_CHROMA = Path.home() / "Work/data/vectors/data/chroma-doc-knowledge-bge"
DEFAULT_STATE = Path.home() / "Work/projects/knowledge-rag-知识库/code/scripts/logs/loki_state.json"
DEFAULT_BACKUP_DIR = Path.home() / "Work/projects/knowledge-rag-知识库/code/scripts/logs"
DDL_COL = "ddl_schema_bge_m3"


def scan_excluded(client) -> list:
    """返回 [(id, db, table, document_preview, metadata)] 待清理列表。"""
    col = client.get_collection(DDL_COL)
    results = []
    offset = 0
    batch = 5000
    while True:
        got = col.get(include=["metadatas", "documents"], limit=batch, offset=offset)
        ids = got.get("ids") or []
        metas = got.get("metadatas") or []
        docs = got.get("documents") or []
        if not ids:
            break
        for did, m, d in zip(ids, metas, docs):
            if not m:
                continue
            db = m.get("db") or ""
            tbl = m.get("table") or ""
            if is_excluded_table(db, tbl):
                results.append((did, db, tbl, (d or "")[:300], m))
        if len(ids) < batch:
            break
        offset += batch
    return results


def export_backup(items: list, backup_path: Path) -> int:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with open(backup_path, "w", encoding="utf-8") as f:
        for did, db, tbl, preview, meta in items:
            f.write(json.dumps({
                "id": did,
                "db": db,
                "table": tbl,
                "metadata": meta,
                "document_preview": preview,
            }, ensure_ascii=False) + "\n")
    return len(items)


def delete_from_chroma(client, ids: list, batch: int = 500) -> int:
    if not ids:
        return 0
    col = client.get_collection(DDL_COL)
    deleted = 0
    for i in range(0, len(ids), batch):
        sub = ids[i:i + batch]
        try:
            col.delete(ids=sub)
            deleted += len(sub)
        except Exception as e:
            sys.stderr.write(f"[ddl_cleanup] 删 batch {i} 失败: {e}\n")
    return deleted


def sync_state_ddl(state_path: Path, deleted_ids: list) -> tuple:
    if not state_path.exists():
        return 0, 0
    raw = json.loads(state_path.read_text(encoding="utf-8"))
    if not (isinstance(raw, dict) and raw.get("version") == 2):
        sys.stderr.write("[ddl_cleanup] state 非 v2 格式，跳过同步\n")
        return 0, 0
    ddl = list(raw.get("ddl") or [])
    before = len(ddl)
    deleted_set = set(deleted_ids)
    new_ddl = sorted(d for d in ddl if d not in deleted_set)
    raw["ddl"] = new_ddl
    state_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return before, len(new_ddl)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="清理 chroma 中备份/归档/临时表 DDL")
    ap.add_argument("--chroma", default=str(DEFAULT_CHROMA))
    ap.add_argument("--state", default=str(DEFAULT_STATE))
    ap.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    if not args.dry_run and not args.apply:
        ap.error("必须指定 --dry-run 或 --apply 之一")

    import chromadb
    client = chromadb.PersistentClient(path=args.chroma)

    items = scan_excluded(client)
    print(f"\n[ddl] 命中 备份/归档/临时表: {len(items)} 条")
    for did, db, tbl, _p, _m in items[:8]:
        print(f"  - {db}.{tbl}  (id={did[:12]}...)")
    if len(items) > 8:
        print(f"  ... 还有 {len(items) - 8} 条")

    if args.dry_run:
        print("\n--dry-run 模式，未删除。")
        return 0

    ts = time.strftime("%Y%m%d%H%M%S")
    bak = Path(args.backup_dir) / f"loki_ddl_cleanup.{ts}.jsonl"
    n_bak = export_backup(items, bak)
    print(f"\n备份 {n_bak} 条 → {bak}")

    ids = [it[0] for it in items]
    n_del = delete_from_chroma(client, ids)
    print(f"删除 {n_del} 条")

    before, after = sync_state_ddl(Path(args.state), ids)
    print(f"state.ddl {before} → {after}")
    print("\n✅ DDL 备份表清理完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
