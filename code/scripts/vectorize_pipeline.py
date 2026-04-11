#!/usr/bin/env python3
"""
本地知识向量化流水线
支持两类数据源:
  1. Obsidian 笔记 (~3276个 .md)
  2. MySQL DDL (所有表结构+字段注释)

特性:
  - 断点续跑: 已向量化的跳过 (按文件path+mtime判断)
  - BGE-M3 本地 embedding (1024维, 无网络请求)
  - qwen2.5:7b 生成摘要 (笔记模式)
  - 日志记录每条成功/失败
  - 空闲CPU友好: 每批后sleep可配
"""

import os
import sys
import time
import json
import hashlib
import logging
import traceback
from datetime import datetime
from pathlib import Path

import pymysql
import chromadb
from sentence_transformers import SentenceTransformer
import requests

# ========== 配置 ==========
BGE_MODEL_PATH = "/Users/didi/Work/projects/knowledge-rag-知识库/bge-m3-model/bge-m3/BAAI/bge-m3"
CHROMA_DIR     = "/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge"
OB_VAULT       = "/Users/didi/Work/docs/obsidian-vault/obsidian"
LOG_DIR        = "/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs"

COLLECTION_NOTES = "doc_knowledge_bge_m3"    # 笔记集合 (已有1525条)
COLLECTION_DDL   = "ddl_schema_bge_m3"       # DDL新集合

OLLAMA_URL    = "http://localhost:11434/api/generate"
OLLAMA_MODEL  = "qwen2.5:7b"
BATCH_SIZE    = 10    # 每批处理文件数
SLEEP_BETWEEN = 0.5  # 批间休眠秒数 (0=不休眠)
MAX_DOC_CHARS = 2000  # embedding最大字符

DB_CONFIG = dict(host='localhost', user='root', password='Xjny+1126',
                 charset='utf8mb4', connect_timeout=5)

# ========== 日志 ==========
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
log_file = Path(LOG_DIR) / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger('pipeline')

# ========== 统计 ==========
stats = dict(skipped=0, success=0, failed=0, start=time.time())


# ========== 工具函数 ==========
def file_id(path: str, mtime: float = None) -> str:
    """用 path+mtime 生成唯一ID，文件变更后ID变化触发重跑"""
    key = f"{path}:{mtime:.0f}" if mtime else path
    return hashlib.md5(key.encode()).hexdigest()


def get_existing_ids(col) -> set:
    """取集合里所有已存在的ID"""
    try:
        total = col.count()
        if total == 0:
            return set()
        result = col.get(limit=total, include=[])
        return set(result['ids'])
    except Exception:
        return set()


def ollama_summarize(text: str) -> str:
    """用qwen2.5:7b生成中文摘要，失败返回原文前300字"""
    prompt = f"""请用2-3句中文总结以下文档的核心内容，重点提取关键术语和主要结论：

{text[:3000]}

摘要："""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 200}
        }, timeout=60)
        if resp.ok:
            return resp.json().get('response', text[:300]).strip()
    except Exception as e:
        log.warning(f"ollama摘要失败: {e}")
    return text[:300]


def embed_texts(model, texts: list) -> list:
    """批量embedding"""
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


# ========== Part 1: Obsidian 笔记向量化 ==========
def run_notes_pipeline(model, col):
    log.info("=" * 60)
    log.info("Part 1: Obsidian 笔记向量化")
    log.info(f"  Vault: {OB_VAULT}")
    log.info(f"  已有记录: {col.count()}")

    existing_ids = get_existing_ids(col)
    log.info(f"  已向量化ID数: {len(existing_ids)}")

    # 扫描所有md文件
    md_files = []
    for f in Path(OB_VAULT).rglob("*.md"):
        if '.obsidian' in str(f) or 'Templates' in str(f):
            continue
        md_files.append(f)
    log.info(f"  扫描到文件: {len(md_files)}")

    # 过滤已处理
    todo = []
    for f in md_files:
        try:
            mtime = f.stat().st_mtime
            fid = file_id(str(f), mtime)
            if fid not in existing_ids:
                todo.append((f, mtime, fid))
        except Exception:
            pass

    log.info(f"  待处理: {len(todo)}, 跳过已有: {len(md_files)-len(todo)}")
    stats['skipped'] += len(md_files) - len(todo)

    if not todo:
        log.info("  所有笔记已是最新，跳过")
        return

    # 分批处理
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i+BATCH_SIZE]
        ids, docs, metas = [], [], []

        for f, mtime, fid in batch:
            try:
                text = f.read_text(encoding='utf-8', errors='ignore').strip()
                if len(text) < 30:
                    log.info(f"  SKIP (太短) {f.name}")
                    stats['skipped'] += 1
                    continue

                # 生成摘要作为embedding文本
                summary = ollama_summarize(text)
                embed_text = f"文件: {f.name}\n{summary}"[:MAX_DOC_CHARS]

                # 相对路径作为meta
                rel_path = str(f.relative_to(OB_VAULT))
                ids.append(fid)
                docs.append(embed_text)
                metas.append({
                    'path': rel_path,
                    'mtime': mtime,
                    'source': 'obsidian',
                    'topic': summary[:100],
                })
                log.info(f"  [{i+len(ids)}/{len(todo)}] {f.name}")
            except Exception as e:
                log.error(f"  FAIL {f.name}: {e}")
                stats['failed'] += 1

        if not ids:
            continue

        try:
            embeddings = embed_texts(model, docs)
            col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
            stats['success'] += len(ids)
            log.info(f"  ✅ 批次入库 {len(ids)} 条 (总计 {col.count()})")
        except Exception as e:
            log.error(f"  FAIL 批次入库: {e}")
            stats['failed'] += len(ids)

        if SLEEP_BETWEEN > 0:
            time.sleep(SLEEP_BETWEEN)

    log.info(f"Part 1 完成: {col.count()} 条")


# ========== Part 2: MySQL DDL 向量化 ==========
def run_ddl_pipeline(model, col):
    log.info("=" * 60)
    log.info("Part 2: MySQL DDL 向量化")

    existing_ids = get_existing_ids(col)
    log.info(f"  已有记录: {len(existing_ids)}")

    all_docs = []  # (id, text, meta)

    try:
        # 获取所有数据库
        conn = pymysql.connect(**DB_CONFIG, database='information_schema')
        cur = conn.cursor()
        cur.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_COMMENT
            FROM TABLES
            WHERE TABLE_SCHEMA NOT IN ('information_schema','performance_schema','mysql','sys')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """)
        tables = cur.fetchall()
        log.info(f"  发现表: {len(tables)}")

        for db, table, tcomment in tables:
            # 获取字段定义
            cur.execute(f"""
                SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
                FROM COLUMNS
                WHERE TABLE_SCHEMA='{db}' AND TABLE_NAME='{table}'
                ORDER BY ORDINAL_POSITION
            """)
            cols = cur.fetchall()

            # 拼DDL文本
            lines = [f"数据库: {db}", f"表名: {table}"]
            if tcomment:
                lines.append(f"表注释: {tcomment}")
            lines.append("字段:")
            for cname, ctype, nullable, default, ccomment in cols:
                col_desc = f"  {cname} {ctype}"
                if ccomment:
                    col_desc += f" -- {ccomment}"
                lines.append(col_desc)

            ddl_text = "\n".join(lines)
            doc_id = hashlib.md5(f"{db}.{table}".encode()).hexdigest()

            all_docs.append((doc_id, ddl_text, {
                'db': db,
                'table': table,
                'comment': tcomment or '',
                'source': 'ddl',
                'col_count': len(cols),
            }))

        conn.close()
    except Exception as e:
        log.error(f"  MySQL连接失败: {e}")
        return

    # 过滤已处理
    todo = [(i, d, m) for i, d, m in all_docs if i not in existing_ids]
    log.info(f"  待处理: {len(todo)}, 已有: {len(all_docs)-len(todo)}")
    stats['skipped'] += len(all_docs) - len(todo)

    if not todo:
        log.info("  所有DDL已是最新，跳过")
        return

    # 分批embedding入库
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i+BATCH_SIZE]
        ids = [x[0] for x in batch]
        docs = [x[1][:MAX_DOC_CHARS] for x in batch]
        metas = [x[2] for x in batch]

        try:
            embeddings = embed_texts(model, docs)
            col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
            stats['success'] += len(ids)
            log.info(f"  ✅ [{i+len(ids)}/{len(todo)}] 批次入库 {len(ids)} 条")
        except Exception as e:
            log.error(f"  FAIL 批次: {e}\n{traceback.format_exc()}")
            stats['failed'] += len(ids)

        if SLEEP_BETWEEN > 0:
            time.sleep(SLEEP_BETWEEN)

    log.info(f"Part 2 完成: {col.count()} 条")


# ========== 主入口 ==========
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    # mode: all | notes | ddl

    log.info("=" * 60)
    log.info(f"向量化流水线启动 mode={mode}")
    log.info(f"日志: {log_file}")

    # 加载BGE-M3
    log.info("加载 BGE-M3 模型...")
    model = SentenceTransformer(BGE_MODEL_PATH)
    log.info(f"模型维度: {model.get_sentence_embedding_dimension()}")

    # ChromaDB
    client = chromadb.PersistentClient(CHROMA_DIR)

    col_notes = client.get_or_create_collection(
        COLLECTION_NOTES,
        metadata={"hnsw:space": "cosine"}
    )
    col_ddl = client.get_or_create_collection(
        COLLECTION_DDL,
        metadata={"hnsw:space": "cosine"}
    )

    if mode in ('all', 'notes'):
        run_notes_pipeline(model, col_notes)

    if mode in ('all', 'ddl'):
        run_ddl_pipeline(model, col_ddl)

    # 最终统计
    elapsed = time.time() - stats['start']
    log.info("=" * 60)
    log.info(f"流水线完成 耗时={elapsed/60:.1f}分钟")
    log.info(f"  成功: {stats['success']}")
    log.info(f"  跳过: {stats['skipped']}")
    log.info(f"  失败: {stats['failed']}")
    log.info(f"  笔记库总量: {col_notes.count()}")
    log.info(f"  DDL库总量: {col_ddl.count()}")
    log.info(f"日志已保存: {log_file}")


if __name__ == '__main__':
    main()
