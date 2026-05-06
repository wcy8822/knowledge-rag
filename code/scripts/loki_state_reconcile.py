#!/usr/bin/env python3
"""
Loki state ↔ Chroma 对账工具

从 chroma summaries collection 逐条读 path + content_fp，
对每条在 state 中缺失或指纹不匹配的记录：
  1. 读磁盘文件内容
  2. 算 content_fingerprint(path, content)
  3. 与 chroma entry id (即 content_fp) 比对
  4. 一致 → 标记入 state

绝不盲标——没有磁盘文件、内容变了、chroma 无 path 元数据的都跳过。
"""
import json, hashlib, sys, time
from pathlib import Path

CHROMA_DIR   = "/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge"
DEFAULT_STATE_FILE = Path("/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs/loki_state.json")
COLLECTION   = "doc_knowledge_bge_m3"
DDL_COL      = "ddl_schema_bge_m3"
BATCH        = 5000

# ---- content_fingerprint 与 pipeline 保持一致 ----
def content_fingerprint(path: str, content: bytes) -> str:
    h = hashlib.sha256()
    h.update(path.encode("utf-8", errors="ignore"))
    h.update(b":")
    h.update(content)
    return h.hexdigest()[:32]

def is_32hex(s: str) -> bool:
    return len(s) == 32 and all(c in "0123456789abcdef" for c in s)

def load_state(state_path: str | Path | None = None):
    p = Path(state_path) if state_path else DEFAULT_STATE_FILE
    if not p.exists():
        return {}, set()
    try:
        raw = json.loads(p.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}, set()
    if isinstance(raw, dict) and raw.get("version") == 2:
        return raw.get("docs", {}), set(raw.get("ddl", []))
    return {}, set()

def save_state(docs: dict, ddl: set, state_path: str | Path | None = None):
    p = Path(state_path) if state_path else DEFAULT_STATE_FILE
    p.write_text(json.dumps(
        {"version": 2, "docs": docs, "ddl": sorted(ddl)},
        ensure_ascii=False,
    ), "utf-8")

def read_file_content(path_str: str) -> bytes | None:
    p = Path(path_str)
    if not p.exists() or not p.is_file():
        return None
    try:
        return p.read_bytes()
    except Exception:
        return None

def reconcile():
    import chromadb

    t0 = time.time()
    state_docs, state_ddl = load_state()
    print(f"当前 state: docs={len(state_docs)}  ddl={len(state_ddl)}")

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # ---- 1. summaries 对账 ----
    col = client.get_collection(COLLECTION)
    chroma_count = col.count()
    print(f"chroma {COLLECTION}: {chroma_count} 条")

    offset = 0
    pulled = 0
    in_state = 0
    reconciled = 0
    skipped_no_path = 0
    skipped_no_file = 0
    skipped_mismatch = 0
    skipped_bad_id = 0

    while offset < chroma_count:
        results = col.get(include=["metadatas", "documents"],
                          limit=BATCH, offset=offset)
        ids = results["ids"] or []
        metas = results["metadatas"] or []
        if not ids:
            break

        for chroma_id, meta in zip(ids, metas):
            pulled += 1
            meta_path = (meta or {}).get("path", "")

            valid_fp = is_32hex(chroma_id) and meta_path

            if not valid_fp:
                skipped_bad_id += 1
                continue

            cur_fp = state_docs.get(meta_path)
            if cur_fp == chroma_id:
                in_state += 1
                continue

            # 缺失或指纹不匹配 → 读磁盘验证
            raw = read_file_content(meta_path)
            if raw is None:
                skipped_no_file += 1
                continue

            computed_fp = content_fingerprint(meta_path, raw)

            if computed_fp == chroma_id:
                state_docs[meta_path] = chroma_id
                reconciled += 1
            else:
                skipped_mismatch += 1

        offset += BATCH

    print(f"  已在 state:          {in_state}")
    print(f"  ✅ 新对账标记:        {reconciled}")
    print(f"  ⏭  跳过(无path元数据): {skipped_bad_id}")
    print(f"  ⏭  跳过(磁盘文件不存在): {skipped_no_file}")
    print(f"  ⏭  跳过(内容已被修改):  {skipped_mismatch}")
    print(f"  共拉取 chroma 条目:   {pulled}")

    # ---- 2. DDL 对账 ----
    try:
        col_ddl = client.get_collection(DDL_COL)
        ddl_all = set(col_ddl.get(limit=10000)["ids"] or [])
        old_len = len(state_ddl)
        state_ddl |= ddl_all
        ddl_new = len(state_ddl) - old_len
        print(f"\nchroma {DDL_COL}: {len(ddl_all)} 条")
        print(f"  DDL state 新增:     {ddl_new} (已去重)")
    except Exception as e:
        print(f"  DDL collection 不可用: {e}")

    # ---- 3. 写回 ----
    save_state(state_docs, state_ddl)
    elapsed = time.time() - t0
    print(f"\n写回 state: docs={len(state_docs)} ddl={len(state_ddl)}  耗时={elapsed:.1f}s")

if __name__ == "__main__":
    reconcile()
