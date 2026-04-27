#!/usr/bin/env python3
"""一次性清退 chroma 中混入的第三方库 / 虚拟环境路径条目

按 loki_scan_filter.is_excluded_path 标准识别脏数据。删除前导出
(id + path + metadata + document_preview) 到 logs/loki_scan_cleanup.<col>.<ts>.jsonl。
同步剔除 state.json v2.docs 中被删 path。

CLI:
  loki_scan_cleanup.py --dry-run                 # 默认：只报告
  loki_scan_cleanup.py --apply                   # 备份 + 删除 + 同步 state
  loki_scan_cleanup.py --apply --collections summaries,chunks
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loki_scan_filter import is_excluded_path  # noqa: E402

DEFAULT_CHROMA = Path.home() / "Work/data/vectors/data/chroma-doc-knowledge-bge"
DEFAULT_STATE = Path.home() / "Work/projects/knowledge-rag-知识库/code/scripts/logs/loki_state.json"
DEFAULT_BACKUP_DIR = Path.home() / "Work/projects/knowledge-rag-知识库/code/scripts/logs"

DEFAULT_COLLECTIONS = ("summaries", "chunks")
COLLECTION_NAME_MAP = {
    "summaries": "doc_knowledge_bge_m3",
    "chunks": "doc_knowledge_chunks",
}


def scan_excluded(client, col_name: str) -> list:
    """返回 [(id, path, document_preview, metadata)] 待清理列表。"""
    col = client.get_collection(col_name)
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
            p = m.get("path") or m.get("source_file") or ""
            if p and is_excluded_path(p):
                results.append((did, p, (d or "")[:300], m))
        if len(ids) < batch:
            break
        offset += batch
    return results


def export_backup(items: list, backup_path: Path) -> int:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with open(backup_path, "w", encoding="utf-8") as f:
        for did, p, preview, meta in items:
            f.write(json.dumps({
                "id": did,
                "path": p,
                "metadata": meta,
                "document_preview": preview,
            }, ensure_ascii=False) + "\n")
    return len(items)


def delete_from_chroma(client, col_name: str, ids: list, batch: int = 500) -> int:
    if not ids:
        return 0
    col = client.get_collection(col_name)
    deleted = 0
    for i in range(0, len(ids), batch):
        sub = ids[i:i + batch]
        try:
            col.delete(ids=sub)
            deleted += len(sub)
        except Exception as e:
            sys.stderr.write(f"[scan_cleanup] {col_name} 删 batch {i} 失败: {e}\n")
    return deleted


def sync_state_docs(state_path: Path, deleted_paths: list) -> tuple:
    """从 state.json v2.docs 中剔除已删 path。返回 (before, after)。"""
    if not state_path.exists():
        return 0, 0
    raw = json.loads(state_path.read_text(encoding="utf-8"))
    if not (isinstance(raw, dict) and raw.get("version") == 2):
        sys.stderr.write("[scan_cleanup] state 非 v2 格式，跳过同步\n")
        return 0, 0
    docs = dict(raw.get("docs") or {})
    before = len(docs)
    deleted_set = set(deleted_paths)
    new_docs = {p: fp for p, fp in docs.items() if p not in deleted_set}
    raw["docs"] = new_docs
    state_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return before, len(new_docs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="清退 chroma 中第三方库/虚拟环境路径条目")
    ap.add_argument("--chroma", default=str(DEFAULT_CHROMA))
    ap.add_argument("--state", default=str(DEFAULT_STATE))
    ap.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    ap.add_argument("--collections", default=",".join(DEFAULT_COLLECTIONS),
                    help=f"逗号分隔，候选: {','.join(COLLECTION_NAME_MAP)}")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    if not args.dry_run and not args.apply:
        ap.error("必须指定 --dry-run 或 --apply 之一")

    import chromadb
    client = chromadb.PersistentClient(path=args.chroma)

    kinds = [k.strip() for k in args.collections.split(",") if k.strip()]
    all_results = {}
    for kind in kinds:
        col_name = COLLECTION_NAME_MAP.get(kind)
        if not col_name:
            sys.stderr.write(f"[scan_cleanup] 未知 collection 类型: {kind}\n")
            continue
        col = client.get_collection(col_name)
        total = col.count()
        items = scan_excluded(client, col_name)
        all_results[kind] = items
        print(f"\n[{kind}] total={total}  excluded={len(items)} ({len(items)*100//max(total,1)}%)")
        for did, p, _pv, _m in items[:5]:
            print(f"  - {p[:100]}")
        if len(items) > 5:
            print(f"  ... 还有 {len(items) - 5} 条")

    if args.dry_run:
        print("\n--dry-run 模式，未删除。")
        return 0

    ts = time.strftime("%Y%m%d%H%M%S")
    deleted_paths_all = []
    for kind, items in all_results.items():
        if not items:
            continue
        col_name = COLLECTION_NAME_MAP[kind]
        bak = Path(args.backup_dir) / f"loki_scan_cleanup.{kind}.{ts}.jsonl"
        n_bak = export_backup(items, bak)
        print(f"\n[{kind}] 备份 {n_bak} 条 → {bak}")

        ids = [it[0] for it in items]
        n_del = delete_from_chroma(client, col_name, ids)
        print(f"[{kind}] 删除 {n_del} 条")
        deleted_paths_all.extend(it[1] for it in items)

    if deleted_paths_all:
        before, after = sync_state_docs(Path(args.state), deleted_paths_all)
        print(f"\n[state] docs {before} → {after}（剔除 {before - after}）")

    print("\n✅ scan cleanup 完成。建议跑一次 benchmark 验证 Recall 回升。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
