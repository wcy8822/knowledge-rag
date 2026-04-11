#!/usr/bin/env python3
"""
Loki — 本地知识向量化流水线 v2
覆盖: Obsidian MD / PDF / Office(docx/xlsx/pptx) / MySQL DDL
特性: 断点续跑 · 自动跳过已处理 · 单文件错误不中断 · 结构化日志
"""

import os, sys, time, json, hashlib, logging, traceback, fcntl
from datetime import datetime
from pathlib import Path

import pymysql
import chromadb
from sentence_transformers import SentenceTransformer

# ========== 路径配置 ==========
BGE_PATH     = "/Users/didi/Work/projects/knowledge-rag-知识库/bge-m3-model/bge-m3/BAAI/bge-m3"
CHROMA_DIR   = "/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge"
LOG_DIR      = Path("/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs")
STATE_FILE   = LOG_DIR / "loki_state.json"  # 已处理文件的fingerprint

SCAN_DIRS = [
    "/Users/didi/Work/docs/obsidian-vault/obsidian",   # Obsidian笔记
    "/Users/didi/Work/docs",                            # 其他文档
    "/Users/didi/Work/projects",                        # 项目文档
    "/Users/didi/.allin_ai_safe/docs",                  # 知识库算法文档
]
EXCLUDE_DIRS = {'.obsidian', 'Templates', 'node_modules', '__pycache__',
                '.git', 'venv', 'env', 'bge-m3-model', 'archives', 'chroma',
                '人事-简历', '.pytest_cache', 'logs'}
SUPPORTED_EXT = {'.md', '.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.sql',
                  '.py', '.sh', '.yaml', '.yml'}

COLLECTION_DOCS = "doc_knowledge_bge_m3"
COLLECTION_DDL  = "ddl_schema_bge_m3"
LOCK_FILE = Path("/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge/.loki_write.lock")

DB_CONFIG = dict(host='localhost', user='root',
                 password=os.environ.get('MYSQL_ROOT_PASSWORD', ''),
                 charset='utf8mb4', connect_timeout=5)

BATCH_SIZE    = 8
MAX_CHARS     = 2000
SLEEP_BATCH   = 0.3

# ========== 日志 ==========
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"loki_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger('loki')

# ========== 状态持久化 ==========
def load_state() -> set:
    """加载已处理的fingerprint集合"""
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()))
        except Exception:
            pass
    return set()

def save_state(done: set):
    STATE_FILE.write_text(json.dumps(list(done)))

def fingerprint(path: str, mtime: float) -> str:
    # 用完整路径+mtime的sha256前32位，避免同名文件碰撞
    return hashlib.sha256(f"{path}:{mtime:.3f}".encode()).hexdigest()[:32]

# ========== 文档解析 ==========
def read_file(path: Path) -> str:
    """读取文件内容，支持多格式"""
    ext = path.suffix.lower()
    try:
        if ext in ('.md', '.txt', '.sql', '.py', '.sh', '.yaml', '.yml'):
            return path.read_text(encoding='utf-8', errors='ignore')

        elif ext == '.pdf':
            from pdfminer.high_level import extract_text
            text = extract_text(str(path))
            return text or ''

        elif ext == '.docx':
            import docx
            doc = docx.Document(str(path))
            return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())

        elif ext == '.xlsx':
            import openpyxl
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            lines = []
            for ws in wb.worksheets:
                lines.append(f"Sheet: {ws.title}")
                for row in ws.iter_rows(max_row=200, values_only=True):
                    row_text = ' | '.join(str(c) for c in row if c is not None)
                    if row_text.strip():
                        lines.append(row_text)
            return '\n'.join(lines)

        elif ext == '.pptx':
            from pptx import Presentation
            prs = Presentation(str(path))
            lines = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, 'text') and shape.text.strip():
                        lines.append(shape.text)
            return '\n'.join(lines)

    except Exception as e:
        raise RuntimeError(f"解析失败({ext}): {e}")
    return ''

# ========== 扫描文件 ==========
def scan_files() -> list:
    """扫描所有支持的文件，返回 (path, mtime) 列表"""
    files = []
    for base in SCAN_DIRS:
        base_path = Path(base)
        if not base_path.exists():
            continue
        for f in base_path.rglob('*'):
            try:
                if f.suffix.lower() not in SUPPORTED_EXT:
                    continue
                if any(ex in f.parts for ex in EXCLUDE_DIRS):
                    continue
                if '.bak.' in f.name:
                    continue
                st = f.stat()
                if st.st_size < 50:
                    continue
                files.append((f, st.st_mtime))
            except (FileNotFoundError, PermissionError, OSError):
                pass  # 跳过失效symlink/无权限
    return files

# ========== Part 1: 文档向量化 ==========
def run_docs(model, col, done: set) -> set:
    log.info("=" * 60)
    log.info("Loki Part 1: 文档向量化 (MD/PDF/Office/SQL)")

    all_files = scan_files()
    log.info(f"  扫描到文件: {len(all_files)}")

    todo = [(f, mt) for f, mt in all_files
            if fingerprint(str(f), mt) not in done]

    skipped = len(all_files) - len(todo)
    log.info(f"  待处理: {len(todo)} | 跳过已有: {skipped}")

    success = failed = 0
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i+BATCH_SIZE]
        ids, docs, metas = [], [], []

        for f, mt in batch:
            fp = fingerprint(str(f), mt)
            try:
                text = read_file(f).strip()
                if len(text) < 30:
                    log.info(f"  SKIP(空) {f.name}")
                    done.add(fp)
                    continue

                embed_text = f"文件:{f.name}\n{text}"[:MAX_CHARS]
                ids.append(fp)
                docs.append(embed_text)
                metas.append({
                    'path': str(f),
                    'name': f.name,
                    'ext': f.suffix.lower(),
                    'mtime': mt,
                    'source': 'loki_docs',
                })
                log.info(f"  [{i+len(ids)}/{len(todo)}] {f.suffix} {f.name}")
            except Exception as e:
                log.error(f"  FAIL {f.name}: {e}")
                failed += 1
                done.add(fp)  # 失败也记录，避免反复卡住

        if not ids:
            continue
        try:
            # 批内去重（防止同名文件fingerprint碰撞）
            seen, u_ids, u_docs, u_metas = set(), [], [], []
            for id_, doc_, meta_ in zip(ids, docs, metas):
                if id_ not in seen:
                    seen.add(id_); u_ids.append(id_); u_docs.append(doc_); u_metas.append(meta_)
            ids, docs, metas = u_ids, u_docs, u_metas

            embeddings = model.encode(docs, normalize_embeddings=True,
                                      show_progress_bar=False).tolist()
            col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
            for fp_item in ids:
                done.add(fp_item)
            success += len(ids)
            save_state(done)  # 每批持久化
            log.info(f"  ✅ 批次入库 {len(ids)} 条 (总计 {col.count()})")
        except Exception as e:
            log.error(f"  FAIL 入库: {e}")
            failed += len(ids)

        if SLEEP_BATCH > 0:
            time.sleep(SLEEP_BATCH)

    log.info(f"Part 1 完成: 成功={success} 失败={failed} 库总量={col.count()}")
    return done

# ========== Part 2: DDL向量化 ==========
def run_ddl(model, col, done: set) -> set:
    log.info("=" * 60)
    log.info("Loki Part 2: MySQL DDL 向量化")

    try:
        conn = pymysql.connect(**DB_CONFIG, database='information_schema')
        cur = conn.cursor()
        cur.execute("""
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_COMMENT
            FROM TABLES
            WHERE TABLE_SCHEMA NOT IN
              ('information_schema','performance_schema','mysql','sys')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """)
        tables = cur.fetchall()
        log.info(f"  发现 {len(tables)} 张表")
    except Exception as e:
        log.error(f"  MySQL连接失败: {e}")
        return done

    todo = []
    for db, tbl, tcomment in tables:
        ddl_id = hashlib.md5(f"ddl:{db}.{tbl}".encode()).hexdigest()
        if ddl_id not in done:
            todo.append((db, tbl, tcomment, ddl_id))

    log.info(f"  待处理: {len(todo)} | 跳过已有: {len(tables)-len(todo)}")

    success = failed = 0
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i+BATCH_SIZE]
        ids, docs, metas = [], [], []

        for db, tbl, tcomment, ddl_id in batch:
            try:
                cur.execute(f"""
                    SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
                           COLUMN_DEFAULT, COLUMN_COMMENT
                    FROM COLUMNS
                    WHERE TABLE_SCHEMA='{db}' AND TABLE_NAME='{tbl}'
                    ORDER BY ORDINAL_POSITION
                """)
                cols = cur.fetchall()
                lines = [f"数据库:{db}", f"表:{tbl}"]
                if tcomment:
                    lines.append(f"说明:{tcomment}")
                lines.append("字段:")
                for cname, ctype, nullable, default, ccomment in cols:
                    line = f"  {cname} {ctype}"
                    if ccomment:
                        line += f" -- {ccomment}"
                    lines.append(line)

                ids.append(ddl_id)
                docs.append('\n'.join(lines)[:MAX_CHARS])
                metas.append({'db': db, 'table': tbl, 'comment': tcomment or '',
                               'col_count': len(cols), 'source': 'ddl'})
                log.info(f"  [{i+len(ids)}/{len(todo)}] {db}.{tbl} ({len(cols)}字段)")
            except Exception as e:
                log.error(f"  FAIL {db}.{tbl}: {e}")
                failed += 1

        if not ids:
            continue
        try:
            embeddings = model.encode(docs, normalize_embeddings=True,
                                      show_progress_bar=False).tolist()
            col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
            for ddl_id in ids:
                done.add(ddl_id)
            success += len(ids)
            save_state(done)
            log.info(f"  ✅ 批次入库 {len(ids)} 条 (DDL总量={col.count()})")
        except Exception as e:
            log.error(f"  FAIL 入库: {e}")
            failed += len(ids)

        if SLEEP_BATCH > 0:
            time.sleep(SLEEP_BATCH)

    conn.close()
    log.info(f"Part 2 完成: 成功={success} 失败={failed} DDL总量={col.count()}")
    return done

# ========== BM25 索引 rebuild ==========
BM25_INDEX_PATH = LOG_DIR / "bm25_index.pkl"
USERDICT_PATH   = Path(__file__).parent / "loki_userdict.txt"

def rebuild_bm25(client):
    """从 ChromaDB 全量 rebuild BM25 索引"""
    import pickle, jieba
    from rank_bm25 import BM25Okapi

    log.info("=" * 60)
    log.info("Loki Phase 3: BM25 索引 rebuild")

    jieba.load_userdict(str(USERDICT_PATH))
    stopwords = set("的 了 是 在 和 有 就 不 也 人 都 一 个 上 我 中 到 大 为 这 与 他 它 要 会 可以 没有 对 对于".split())

    def tokenize(text):
        return [w.lower().strip() for w in jieba.cut(text) if w.strip() and w.strip() not in stopwords]

    collections_map = {
        'summaries': 'doc_knowledge_bge_m3',
        'chunks':    'doc_knowledge_chunks',
        'ddl':       'ddl_schema_bge_m3',
    }

    corpus_tokens = []
    doc_ids = []
    doc_meta = []

    for source_key, col_name in collections_map.items():
        try:
            col = client.get_collection(col_name)
            count = col.count()
            if count == 0:
                continue
        except Exception:
            continue

        offset = 0
        batch_size = 5000
        loaded = 0
        while offset < count:
            results = col.get(limit=batch_size, offset=offset, include=['documents', 'metadatas'])
            if not results['ids']:
                break
            for i, doc_id in enumerate(results['ids']):
                doc_text = results['documents'][i] or ''
                meta = results['metadatas'][i] or {}
                searchable = doc_text
                for field in ['source_file', 'name', 'path', 'heading', 'topic', 'domain', 'table', 'db', 'description']:
                    if field in meta and meta[field]:
                        searchable += ' ' + str(meta[field])
                tokens = tokenize(searchable)
                if not tokens:
                    continue
                corpus_tokens.append(tokens)
                doc_ids.append(doc_id)
                file_key = meta.get('source_file', meta.get('path', meta.get('name', meta.get('table', doc_id))))
                doc_meta.append({
                    'source': source_key, 'file': file_key,
                    'heading': meta.get('heading', ''), 'topic': meta.get('topic', meta.get('table', '')),
                    'domain': meta.get('domain', source_key), 'doc_preview': doc_text[:500],
                })
                loaded += 1
            offset += batch_size
        log.info(f"  {col_name}: {loaded} 条")

    if not corpus_tokens:
        log.warning("  无文档，跳过 BM25 rebuild")
        return

    t1 = time.time()
    bm25 = BM25Okapi(corpus_tokens)
    index_data = {
        'bm25': bm25, 'doc_ids': doc_ids, 'doc_meta': doc_meta,
        'corpus_tokens': corpus_tokens,
        'build_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'doc_count': len(doc_ids),
    }
    with open(BM25_INDEX_PATH, 'wb') as f:
        pickle.dump(index_data, f)

    size_mb = BM25_INDEX_PATH.stat().st_size / 1024 / 1024
    log.info(f"  BM25 索引 rebuild 完成: {len(doc_ids)} 条, {time.time()-t1:.1f}s, {size_mb:.1f}MB")


# ========== 主流程 ==========
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    log.info("=" * 60)
    log.info(f"Loki 启动 mode={mode}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 先加载模型（无副作用，不需要锁）
    log.info("加载 BGE-M3...")
    model = SentenceTransformer(BGE_PATH)
    log.info(f"  维度: {model.get_sentence_embedding_dimension()}")

    # 2. 获取互斥锁（拿不到就干净退出，不会泄漏资源）
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fp = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fp.write(f"pipeline:{os.getpid()}\n"); lock_fp.flush()
        log.info("🔒 已获取ChromaDB写锁")
    except (IOError, OSError):
        log.error("❌ 无法获取写锁，reindex/chunk可能正在运行。退出。")
        lock_fp.close()
        sys.exit(1)

    # 3. 在锁保护下初始化ChromaDB + 做工作，finally保证释放
    try:
        client = chromadb.PersistentClient(CHROMA_DIR)
        col_docs = client.get_or_create_collection(COLLECTION_DOCS,
                       metadata={"hnsw:space": "cosine"})
        col_ddl  = client.get_or_create_collection(COLLECTION_DDL,
                       metadata={"hnsw:space": "cosine"})

        done = load_state()
        log.info(f"  已处理fingerprint: {len(done)}")

        t0 = time.time()
        if mode in ('all', 'docs'):
            done = run_docs(model, col_docs, done)
        if mode in ('all', 'ddl'):
            done = run_ddl(model, col_ddl, done)

        save_state(done)

        # Phase 3: BM25 索引 rebuild（每轮都更新，<10s）
        rebuild_bm25(client)

        elapsed = (time.time() - t0) / 60
        log.info("=" * 60)
        log.info(f"Loki 完成 耗时={elapsed:.1f}分钟")
        log.info(f"  文档库: {col_docs.count()} 条")
        log.info(f"  DDL库:  {col_ddl.count()} 条")
        log.info(f"  日志:   {log_file}")
    finally:
        fcntl.flock(lock_fp, fcntl.LOCK_UN); lock_fp.close()
        log.info("🔓 已释放ChromaDB写锁")

if __name__ == '__main__':
    main()
