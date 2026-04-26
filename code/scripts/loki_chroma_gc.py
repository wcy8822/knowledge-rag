#!/usr/bin/env python3
"""Loki ChromaDB 早期 id 体系 GC 工具

清理 chroma 中非 pipeline.fingerprint / md5 体系的脏数据：
  - summaries (doc_knowledge_bge_m3): 删除非 hex32 id（doc_X / oil-algo-* 等）
  - ddl (ddl_schema_bge_m3):           删除非 hex32 id（早期 ddl_<schema>_<table>）
  - chunks (doc_knowledge_chunks):     不动（id 是合法 <hex32>_chunk_NNN）

删前导出待删条目（id + metadata + document 预览）到 JSONL 备份文件。
可选同步清理 state.json v2.ddl 中被删 ids（state.docs 在 v2 迁移时已过滤干净）。

CLI:
  loki_chroma_gc.py --dry-run                          # 默认：只报告
  loki_chroma_gc.py --apply                            # 备份 + 删除
  loki_chroma_gc.py --apply --collections summaries    # 仅清 summaries
  loki_chroma_gc.py --apply --skip-state               # 不同步 state.ddl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_CHROMA = Path.home() / "Work/data/vectors/data/chroma-doc-knowledge-bge"
DEFAULT_STATE = Path.home() / "Work/projects/knowledge-rag-知识库/code/scripts/logs/loki_state.json"
DEFAULT_BACKUP_DIR = Path.home() / "Work/projects/knowledge-rag-知识库/code/scripts/logs"

HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
CHUNK_RE = re.compile(r"^[0-9a-f]{32}_chunk_\d+$")
DEFAULT_COLLECTIONS = ("summaries", "ddl")
COLLECTION_NAME_MAP = {
    "summaries": "doc_knowledge_bge_m3",
    "chunks": "doc_knowledge_chunks",
    "ddl": "ddl_schema_bge_m3",
}


@dataclass
class GcReport:
    collection: str
    total: int = 0
    legacy: int = 0
    sample_legacy_ids: list = field(default_factory=list)


def is_legacy_id(col_kind: str, doc_id: str) -> bool:
    """非 pipeline 体系 → True (待清理)。

    summaries / ddl: 合法 = 32 hex
    chunks:           合法 = <hex32>_chunk_<digits>
    """
    if col_kind == "chunks":
        return not bool(CHUNK_RE.match(doc_id))
    return not bool(HEX32_RE.match(doc_id))


def fetch_collection_ids(client, col_name: str) -> list:
    try:
        col = client.get_collection(col_name)
    except Exception as e:
        sys.stderr.write(f"[chroma_gc] {col_name} 拉取失败: {e}\n")
        return []
    ids = []
    offset = 0
    batch = 10000
    while True:
        got = col.get(include=[], limit=batch, offset=offset)
        chunk = got.get("ids") or []
        if not chunk:
            break
        ids.extend(chunk)
        if len(chunk) < batch:
            break
        offset += batch
    return ids


def scan_legacy(client, kinds: Iterable[str]) -> list:
    reports = []
    for kind in kinds:
        col_name = COLLECTION_NAME_MAP.get(kind)
        if not col_name:
            sys.stderr.write(f"[chroma_gc] 未知 collection 类型: {kind}\n")
            continue
        ids = fetch_collection_ids(client, col_name)
        legacy_ids = [i for i in ids if is_legacy_id(kind, i)]
        reports.append(GcReport(
            collection=kind,
            total=len(ids),
            legacy=len(legacy_ids),
            sample_legacy_ids=legacy_ids[:5],
        ))
    return reports


def export_backup(client, col_name: str, ids: list, backup_path: Path) -> int:
    """把 (id, metadata, document_preview) 写到 JSONL；返回写入条数。"""
    if not ids:
        return 0
    try:
        col = client.get_collection(col_name)
    except Exception as e:
        sys.stderr.write(f"[chroma_gc] {col_name} 备份取 collection 失败: {e}\n")
        return 0
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    chunk = 500
    with open(backup_path, "w", encoding="utf-8") as f:
        for i in range(0, len(ids), chunk):
            sub = ids[i:i + chunk]
            try:
                got = col.get(ids=sub, include=["metadatas", "documents"])
            except Exception as e:
                sys.stderr.write(f"[chroma_gc] 取 batch {i} 备份失败: {e}\n")
                continue
            for j, did in enumerate(got.get("ids") or []):
                meta = (got.get("metadatas") or [None])[j] or {}
                doc = (got.get("documents") or [""])[j] or ""
                f.write(json.dumps({
                    "id": did,
                    "metadata": meta,
                    "document_preview": doc[:300],
                }, ensure_ascii=False) + "\n")
                written += 1
    return written


def delete_ids(client, col_name: str, ids: list, batch: int = 500) -> int:
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
            sys.stderr.write(f"[chroma_gc] 删 batch {i} 失败: {e}\n")
    return deleted


def sync_state_ddl(state_path: Path, deleted_ddl_ids: Iterable[str]) -> tuple:
    """从 state.json v2.ddl 中剔除已删 ids。返回 (before_count, after_count)。"""
    if not state_path.exists():
        return 0, 0
    raw = json.loads(state_path.read_text(encoding="utf-8"))
    if not (isinstance(raw, dict) and raw.get("version") == 2):
        sys.stderr.write("[chroma_gc] state 非 v2 格式，跳过同步\n")
        return 0, 0
    ddl = list(raw.get("ddl") or [])
    before = len(ddl)
    deleted_set = set(deleted_ddl_ids)
    new_ddl = [d for d in ddl if d not in deleted_set]
    raw["ddl"] = sorted(new_ddl)
    state_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return before, len(new_ddl)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Loki ChromaDB GC 工具")
    ap.add_argument("--chroma", default=str(DEFAULT_CHROMA))
    ap.add_argument("--state", default=str(DEFAULT_STATE))
    ap.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    ap.add_argument("--collections", default=",".join(DEFAULT_COLLECTIONS),
                    help=f"逗号分隔，候选: {','.join(COLLECTION_NAME_MAP)}")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不删")
    ap.add_argument("--apply", action="store_true", help="备份 + 删除")
    ap.add_argument("--skip-state", action="store_true", help="不同步 state.ddl")
    args = ap.parse_args(argv)

    if not args.dry_run and not args.apply:
        ap.error("必须指定 --dry-run 或 --apply 之一")

    import chromadb
    client = chromadb.PersistentClient(path=args.chroma)

    kinds = [k.strip() for k in args.collections.split(",") if k.strip()]
    reports = scan_legacy(client, kinds)

    print()
    for r in reports:
        print(f"[{r.collection}] total={r.total} legacy={r.legacy}")
        if r.sample_legacy_ids:
            print(f"  样例: {r.sample_legacy_ids}")
    print()

    if args.dry_run:
        print("--dry-run 模式，未删除。")
        return 0

    ts = time.strftime("%Y%m%d%H%M%S")
    backup_dir = Path(args.backup_dir)
    deleted_ddl_ids = []
    for r in reports:
        if r.legacy == 0:
            continue
        col_name = COLLECTION_NAME_MAP[r.collection]
        ids_all = fetch_collection_ids(client, col_name)
        legacy_ids = [i for i in ids_all if is_legacy_id(r.collection, i)]

        bak = backup_dir / f"loki_chroma_gc.{r.collection}.{ts}.jsonl"
        n_bak = export_backup(client, col_name, legacy_ids, bak)
        print(f"[{r.collection}] 备份 {n_bak} 条 → {bak}")

        n_del = delete_ids(client, col_name, legacy_ids)
        print(f"[{r.collection}] 删除 {n_del} 条")

        if r.collection == "ddl":
            deleted_ddl_ids.extend(legacy_ids)

    if deleted_ddl_ids and not args.skip_state:
        before, after = sync_state_ddl(Path(args.state), deleted_ddl_ids)
        print(f"[state] ddl set {before} → {after}（剔除 {before - after}）")

    print("\n✅ GC 完成。建议下次 pipeline 跑前再用 loki_state_cleanup 对齐一次。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
