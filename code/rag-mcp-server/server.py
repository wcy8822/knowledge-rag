#!/usr/bin/env python3
"""统一智能数据层 MCP Server
功能: 知识库搜索/问答 + MySQL 查询 + 笔记读取 + 工作日志
启动: python3 server.py
MCP 协议: stdio 模式
"""

import json
import sys
import os
import re
import pickle
import urllib.request
from pathlib import Path

# 路径配置
HOME = Path.home()
CHROMA_PATH = str(HOME / "Work/data/vectors/data/chroma-doc-knowledge-bge")
MODEL_PATH = str(HOME / "Work/data/models/bge-m3-backup/bge-m3/BAAI/bge-m3")
OLLAMA_API = "http://localhost:11434/api/generate"
LLM_MODEL = "qwen2.5:7b"
BM25_INDEX_PATH = str(HOME / "Work/projects/knowledge-rag-知识库/code/scripts/logs/bm25_index.pkl")
USERDICT_PATH = str(HOME / "Work/projects/knowledge-rag-知识库/code/scripts/loki_userdict.txt")
COLLECTIONS = {
    'summaries': ('doc_knowledge_bge_m3', 0.5),
    'chunks':    ('doc_knowledge_chunks', 0.3),
    'ddl':       ('ddl_schema_bge_m3', 0.5),
}

# 延迟加载
_model = None
_client = None
_bm25_index = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_PATH)
    return _model

def get_client():
    global _client
    if _client is None:
        import chromadb
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client

def get_bm25_index():
    global _bm25_index
    if _bm25_index is None:
        try:
            with open(BM25_INDEX_PATH, 'rb') as f:
                _bm25_index = pickle.load(f)
        except Exception as e:
            sys.stderr.write(f"BM25 索引加载失败: {e}\n")
            _bm25_index = {}
    return _bm25_index

# BM25 搜索所需的分词
_jieba_loaded = False
STOPWORDS = set("的 了 是 在 和 有 就 不 也 人 都 一 个 上 我 中 到 大 为 这 与 他 它 要 会 可以 没有 对 对于".split())

def _tokenize(text: str) -> list:
    global _jieba_loaded
    import jieba
    if not _jieba_loaded:
        jieba.load_userdict(USERDICT_PATH)
        _jieba_loaded = True
    return [w.lower().strip() for w in jieba.cut(text) if w.strip() and w.strip() not in STOPWORDS]

def _search_bm25(query: str, top_k: int = 20) -> list:
    """BM25 关键词搜索"""
    index = get_bm25_index()
    if not index or 'bm25' not in index:
        return []
    tokens = _tokenize(query)
    if not tokens:
        return []
    scores = index['bm25'].get_scores(tokens)
    doc_meta = index['doc_meta']
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    seen = set()
    results = []
    for idx in top_indices:
        if scores[idx] <= 0:
            break
        meta = doc_meta[idx]
        file_key = meta['file']
        if file_key in seen:
            continue
        seen.add(file_key)
        results.append({
            'file': file_key,
            'bm25_score': float(scores[idx]),
            'source': meta['source'],
            'heading': meta.get('heading', ''),
            'topic': meta.get('topic', ''),
            'domain': meta.get('domain', ''),
            'doc_preview': meta.get('doc_preview', ''),
        })
        if len(results) >= top_k:
            break
    return results

def _rrf_merge(vector_hits: list, bm25_hits: list, k: int = 60, top_n: int = 5) -> list:
    """Reciprocal Rank Fusion 融合两路结果"""
    scores = {}   # file_key -> rrf_score
    source_map = {}  # file_key -> 'vector'|'bm25'|'both'
    meta_map = {}    # file_key -> best hit data

    for rank, hit in enumerate(vector_hits):
        key = hit['path']
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
        source_map[key] = 'vector'
        meta_map[key] = hit

    for rank, hit in enumerate(bm25_hits):
        key = hit['file']
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
        if key in source_map:
            source_map[key] = 'both'
        else:
            source_map[key] = 'bm25'
            # BM25 独占结果，用 bm25 的 meta 构造返回
            meta_map[key] = {
                'text': hit['doc_preview'][:400],
                'path': key,
                'source': hit['source'],
                'heading': hit.get('heading', ''),
                'topic': hit.get('topic', ''),
                'domain': hit.get('domain', ''),
                'similarity': 0,
                'weighted_score': 0,
                'weight': 0,
            }

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

    results = []
    for file_key, rrf_score in ranked:
        hit = meta_map[file_key].copy()
        hit['rrf_score'] = round(rrf_score, 5)
        hit['match_type'] = source_map[file_key]  # vector/bm25/both
        results.append(hit)

    return results

def _normalize(distance):
    """ChromaDB cosine distance [0,2] -> score [0,1]"""
    return 1.0 - distance / 2.0

def _extract_preview(doc, source, meta):
    """从 document 字段提取人类可读的预览文本"""
    raw = doc.strip()
    # chunks: "文件:xxx\n块:x/x\n摘要:xxx\n---\n原文"
    summary = ''
    body = raw
    if '摘要:' in raw:
        after = raw.split('摘要:', 1)[1]
        for sep in ['\n---', '\n\n']:
            if sep in after:
                summary = after.split(sep, 1)[0].strip()
                break
        else:
            summary = after[:200].strip()
        if '关键术语' in summary:
            summary = summary.split('关键术语')[0].strip().rstrip('。')
    if '\n---\n' in raw:
        body = raw.split('\n---\n', 1)[1]
    # DDL
    if source == 'ddl':
        table = meta.get('table', '')
        db = meta.get('db', '')
        desc = meta.get('description', meta.get('comment', ''))
        summary = f"表 {db}.{table}" + (f" — {desc}" if desc else '')
    return summary if summary else body[:200]

def _vector_search(query: str, n: int = 20) -> list:
    """向量语义搜索（内部方法，返回 top n 去重结果）"""
    client = get_client()
    model = get_model()
    q_embed = model.encode([query], normalize_embeddings=True).tolist()

    all_results = []
    for key, (col_name, weight) in COLLECTIONS.items():
        try:
            col = client.get_collection(col_name)
            if col.count() == 0:
                continue
            results = col.query(query_embeddings=q_embed, n_results=n,
                                include=['documents', 'metadatas', 'distances'])
        except Exception:
            continue

        for i in range(len(results['ids'][0])):
            doc = results['documents'][0][i]
            meta = results['metadatas'][0][i]
            dist = results['distances'][0][i]
            raw_score = _normalize(dist)
            score = raw_score * weight

            file_key = meta.get('source_file', meta.get('path', meta.get('table', results['ids'][0][i])))
            preview = _extract_preview(doc, key, meta)

            all_results.append({
                'text': preview,
                'path': file_key,
                'source': key,
                'heading': meta.get('heading', ''),
                'topic': meta.get('topic', meta.get('table', '')),
                'domain': meta.get('domain', key),
                'similarity': round(raw_score, 3),
                'weighted_score': round(score, 3),
                'weight': weight,
            })

    # 排序 + 去重（同文件只保留最高分）
    all_results.sort(key=lambda x: x['weighted_score'], reverse=True)
    seen = set()
    deduped = []
    for r in all_results:
        if r['path'] not in seen:
            seen.add(r['path'])
            deduped.append(r)
    return deduped[:n]


def search_knowledge(query: str, n: int = 5) -> list:
    """Hybrid Search: 向量 + BM25 + RRF 融合"""
    # 两路并行搜索
    vector_hits = _vector_search(query, n=20)
    bm25_hits = _search_bm25(query, top_k=20)

    # 如果 BM25 索引不可用，降级为纯向量搜索
    if not bm25_hits:
        return vector_hits[:n]

    # RRF 融合
    return _rrf_merge(vector_hits, bm25_hits, k=60, top_n=n)

def ask_knowledge(question: str) -> str:
    """RAG + LLM 问答"""
    docs = search_knowledge(question, n=5)

    context_parts = []
    for i, doc in enumerate(docs):
        src = doc['source']
        heading = f" > {doc['heading']}" if doc.get('heading') else ''
        context_parts.append(f"[文档{i+1}] [{src}] {doc['path']}{heading}\n{doc['text']}")

    prompt = (
        f"你是企业知识库助手。基于检索到的文档回答问题。直接回答，引用文件路径作来源。中文简洁专业。\n\n"
        f"=== 文档 ===\n" + "\n\n".join(context_parts) +
        f"\n\n=== 问题 ===\n{question}\n\n=== 回答 ===\n"
    )

    data = json.dumps({
        "model": LLM_MODEL, "prompt": prompt, "stream": False,
        "options": {"num_predict": 1024, "temperature": 0.3}
    }).encode()

    try:
        req = urllib.request.Request(OLLAMA_API, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=180)
        result = json.loads(resp.read())
        answer = result.get("response", "").strip()
    except Exception as e:
        answer = f"LLM 调用失败: {e}\n\n检索到的相关文档:\n" + "\n".join(
            f"- [{d['similarity']}] {d['topic']} ({d['path']})" for d in docs
        )

    sources = [d['path'] for d in docs[:3]]
    return f"{answer}\n\n来源: {', '.join(sources)}"

def get_stats() -> dict:
    """知识库统计"""
    client = get_client()
    stats = {
        "embedding_model": "BGE-M3 (1024维)",
        "llm_model": LLM_MODEL,
        "storage": CHROMA_PATH,
    }
    for key, (col_name, weight) in COLLECTIONS.items():
        try:
            col = client.get_collection(col_name)
            stats[f"{key}_count"] = col.count()
            stats[f"{key}_weight"] = weight
        except Exception:
            stats[f"{key}_count"] = "NOT FOUND"
    return stats

# ============================================================
# MySQL 查询
# ============================================================

def _get_mysql_password():
    """读取 MySQL 密码：优先环境变量，其次 ~/.secrets.env"""
    val = os.environ.get('MYSQL_ROOT_PASSWORD')
    if val:
        return val
    secrets_file = HOME / ".secrets.env"
    if secrets_file.exists():
        for line in secrets_file.read_text().splitlines():
            if line.startswith("export MYSQL_ROOT_PASSWORD="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

## 表→库 权威映射（用于自动修正 LLM 输出）
TABLE_TO_DB = {
    # data_manager_db
    "v_merchant_profile_latest_di": "data_manager_db",
    "v_merchant_profile_latest_di_0212": "data_manager_db",
    "merchant_profile_analysis": "data_manager_db",
    "merchant_profile_latest": "data_manager_db",
    "tag_coverage_by_store": "data_manager_db",
    "station_tag_merge_staging": "data_manager_db",
    "merchant_visit_analysis": "data_manager_db",
    "tag_master": "data_manager_db",
    "tag_enum": "data_manager_db",
    "tag_catalog": "data_manager_db",
    "tag_spec": "data_manager_db",
    "mvc_pop_visit_di": "data_manager_db",
    "mvc_pop_segment_di": "data_manager_db",
    "mvc_pop_tag_detail_di": "data_manager_db",
    "station_tag_coverage": "data_manager_db",
    "is_ka_direct": "data_manager_db",
    "orange_report_store": "data_manager_db",
    "combined_merchant_profile": "data_manager_db",
    "dim_gas_store_info_extend": "data_manager_db",
    # gas_dw
    "dim_gas_merch_merge_store": "gas_dw",
    "dwm_gas_trd_profit_store_di": "gas_dw",
    "dwm_gas_trd_indicators_di": "gas_dw",
    "dm_merchant_profile_hexagon_wide_table_final": "gas_dw",
    "dm_merchant_profile_hexagon_wide_table": "gas_dw",
    "dm_store_competition_5km": "gas_dw",
    "dm_store_orange_rate": "gas_dw",
    "dm_store_poi_mapping": "gas_dw",
    "dm_store_poi_mapping_unique": "gas_dw",
    "dm_store_business_area_type": "gas_dw",
    "dm_brand_store_stats": "gas_dw",
    "dm_gas_merch_store_di": "gas_dw",
    # am_bi_dev
    "gas_merch_operation_tags_di": "am_bi_dev",
    "ads_visit_store_daily_summary": "am_bi_dev",
}

# 不存在的数据库名修正
DB_ALIASES = {
    "data_warehouse": "data_manager_db",
    "data_manager": "data_manager_db",
    "gas_data": "gas_dw",
    "gas_warehouse": "gas_dw",
}


## 常见字段幻觉→正确字段映射
FIELD_FIXES = [
    # (错误字段, 正确字段) — 注意顺序：长的先匹配，避免部分替换
    ("poi_store_name", "store_name"),
    # wash_car_service 只在它不是 service_carwash_available 的一部分时替换
    # convenience_store 同理 — 用 word boundary 在 fix 函数里处理
]

# 需要 word-boundary 替换的字段（避免 wash_car_service → service_carwash_available 又匹配到 convenience_store_available）
FIELD_REGEX_FIXES = [
    (r'\bwash_car_service\b', 'service_carwash_available'),
    (r'\bconvenience_store\b(?!_available)', 'convenience_store_available'),
]

## 不存在的表→正确表映射
TABLE_FIXES = {
    "station_tag_merge_staging": "tag_enum",
}


def fix_nl2sql_output(sql: str, db: str) -> tuple:
    """自动修正 LLM 生成的 SQL 和数据库名"""
    # 1. 修正数据库名
    if db in DB_ALIASES:
        db = DB_ALIASES[db]

    # 2. 从 SQL 中提取表名，检查是否需要修正数据库
    # 匹配 FROM/JOIN 后面的表名
    table_refs = re.findall(r'(?:FROM|JOIN)\s+(?:\w+\.)?(\w+)', sql, re.I)
    for table in table_refs:
        if table in TABLE_TO_DB:
            correct_db = TABLE_TO_DB[table]
            if db != correct_db:
                db = correct_db  # 以第一个找到的表为准

    # 3. 修正 SQL 中的跨库引用（如 gas_dw.v_merchant_profile_latest_di → data_manager_db.v_merchant_profile_latest_di）
    for table, correct_db in TABLE_TO_DB.items():
        # 替换错误的 db.table 引用
        sql = re.sub(
            rf'\b(?:data_warehouse|data_manager|gas_dw|am_bi_dev|data_manager_db)\.{table}\b',
            f'{correct_db}.{table}',
            sql
        )

    # 4. MySQL 语法修正
    sql = re.sub(r'DATE_SUB\(CURRENT_DATE,\s*(\d+)\)', r'DATE_SUB(CURDATE(), INTERVAL \1 DAY)', sql)
    sql = sql.replace('GETDATE()', 'CURDATE()')

    # 5. 字段幻觉修正
    for wrong_field, correct_field in FIELD_FIXES:
        if wrong_field in sql:
            sql = sql.replace(wrong_field, correct_field)
    for pattern, replacement in FIELD_REGEX_FIXES:
        sql = re.sub(pattern, replacement, sql)

    # 6. 表名修正
    for wrong_table, correct_table in TABLE_FIXES.items():
        if wrong_table in sql:
            sql = sql.replace(wrong_table, correct_table)

    # 7. 跨库自动全限定：给未带库名前缀的表加上正确的 db.table
    # 检测是否有多库表引用
    table_dbs = set()
    for table in table_refs:
        if table in TABLE_TO_DB:
            table_dbs.add(TABLE_TO_DB[table])
    if len(table_dbs) > 1:
        # 跨库查询：给每个表加全限定名
        for table in table_refs:
            if table in TABLE_TO_DB:
                correct = TABLE_TO_DB[table]
                # 替换 FROM/JOIN 后面的裸表名（不带 db. 前缀的）
                sql = re.sub(
                    rf'(FROM|JOIN)\s+(?![\w]+\.){table}\b',
                    rf'\1 {correct}.{table}',
                    sql, flags=re.I
                )

    return sql, db


def _get_table_columns_for_retry(sql: str, db: str) -> str:
    """从 SQL 中提取表名，查询实际字段列表，用于重试提示"""
    import pymysql
    pw = _get_mysql_password()
    tables = re.findall(r'(?:FROM|JOIN)\s+(?:\w+\.)?(\w+)', sql, re.I)
    info_parts = []
    for table in set(tables):
        actual_db = TABLE_TO_DB.get(table, db)
        try:
            conn = pymysql.connect(host='localhost', user='root', password=pw, database=actual_db, charset='utf8mb4')
            cur = conn.cursor()
            cur.execute(f"SHOW COLUMNS FROM `{table}`")
            cols = [r[0] for r in cur.fetchall()]
            conn.close()
            info_parts.append(f"【{actual_db}.{table} 的实际字段】: {', '.join(cols)}")
        except:
            info_parts.append(f"【{table}】: 表不存在于 {actual_db}")
    return "\n".join(info_parts) if info_parts else "无法获取表字段信息"


def nl2sql(question: str) -> str:
    """自然语言转 SQL 并执行"""
    context_file = HOME / ".allin_ai_safe/nl2sql-context.md"
    if not context_file.exists():
        return "NL2SQL context 文件不存在"

    context = context_file.read_text(errors='ignore')
    prompt = f"{context}\n\n## 用户问题\n{question}\n\n请生成 SQL，返回 JSON: {{\"sql\": \"...\", \"database\": \"...\"}}"

    data = json.dumps({"model": LLM_MODEL, "prompt": prompt, "stream": False, "options": {"num_predict": 512, "temperature": 0.1}}).encode()
    try:
        req = urllib.request.Request(OLLAMA_API, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=180)
        result = json.loads(resp.read()).get("response", "").strip()
        match = re.search(r'\{[^}]+\}', result, re.DOTALL)
        if match:
            sql_info = json.loads(match.group())
            sql = sql_info.get("sql", "").replace("-- 库: ", "").strip()
            # 清理注释行
            sql = "\n".join(l for l in sql.split("\n") if not l.strip().startswith("--"))
            db = sql_info.get("database", "data_manager_db")

            # 自动修正
            sql, db = fix_nl2sql_output(sql, db)

            # 执行（带智能重试）
            exec_result = query_mysql(sql, db)
            if exec_result.startswith("错误：") or "Error" in exec_result[:50]:
                # 获取实际表的字段列表用于重试
                table_columns_info = _get_table_columns_for_retry(sql, db)
                retry_prompt = f"""上一次生成的 SQL 执行失败。
错误信息: {exec_result[:200]}
原SQL: {sql}
数据库: {db}

{table_columns_info}

请基于上面的【实际字段列表】修正 SQL，只使用列表中存在的字段。
返回 JSON: {{"sql": "...", "database": "..."}}"""
                retry_data = json.dumps({"model": LLM_MODEL, "prompt": retry_prompt, "stream": False, "options": {"num_predict": 512, "temperature": 0.1}}).encode()
                try:
                    retry_req = urllib.request.Request(OLLAMA_API, data=retry_data, headers={"Content-Type": "application/json"})
                    retry_resp = urllib.request.urlopen(retry_req, timeout=180)
                    retry_result = json.loads(retry_resp.read()).get("response", "").strip()
                    retry_match = re.search(r'\{[^}]+\}', retry_result, re.DOTALL)
                    if retry_match:
                        retry_info = json.loads(retry_match.group())
                        sql2 = retry_info.get("sql", "").strip()
                        sql2 = "\n".join(l for l in sql2.split("\n") if not l.strip().startswith("--"))
                        db2 = retry_info.get("database", db)
                        sql2, db2 = fix_nl2sql_output(sql2, db2)
                        exec_result2 = query_mysql(sql2, db2)
                        if not exec_result2.startswith("错误：") and "Error" not in exec_result2[:50]:
                            return f"问题: {question}\n生成SQL: {sql2}\n数据库: {db2}\n(重试修正成功)\n\n{exec_result2}"
                except:
                    pass
            return f"问题: {question}\n生成SQL: {sql}\n数据库: {db}\n\n{exec_result}"
        return f"LLM 未能生成有效 SQL。原始输出:\n{result[:500]}"
    except Exception as e:
        return f"NL2SQL 错误: {e}"

def query_mysql(query: str, database: str = "data_manager_db") -> str:
    """执行只读 SQL 查询（安全限制：仅 SELECT）"""
    import pymysql

    # 安全检查
    query_upper = query.strip().upper()
    if not query_upper.startswith("SELECT") and not query_upper.startswith("SHOW") and not query_upper.startswith("DESCRIBE"):
        return "错误：只允许 SELECT / SHOW / DESCRIBE 查询，禁止修改数据"

    dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT"]
    for kw in dangerous:
        if kw in query_upper.split("--")[0].split("/*")[0]:
            return f"错误：检测到 {kw} 关键字，禁止执行"

    pw = _get_mysql_password()
    try:
        conn = pymysql.connect(host='localhost', user='root', password=pw, database=database, charset='utf8mb4')
        cur = conn.cursor()
        cur.execute(query)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchmany(100)  # 最多返回 100 行
        total = cur.rowcount
        conn.close()

        if not rows:
            return f"查询成功但无结果 (数据库: {database})"

        # 格式化输出
        result = f"数据库: {database} | 返回 {len(rows)}/{total} 行 | {len(columns)} 列\n\n"
        result += " | ".join(columns) + "\n"
        result += "-" * 60 + "\n"
        for row in rows[:20]:
            result += " | ".join(str(v)[:30] if v is not None else "NULL" for v in row) + "\n"
        if len(rows) > 20:
            result += f"... 还有 {len(rows)-20} 行\n"

        return result

    except Exception as e:
        return f"MySQL 查询错误: {e}"

def list_mysql_tables(database: str = "data_manager_db") -> str:
    """列出数据库的所有表和行数"""
    import pymysql
    pw = _get_mysql_password()
    try:
        conn = pymysql.connect(host='localhost', user='root', password=pw, charset='utf8mb4')
        cur = conn.cursor()
        cur.execute(f"""
            SELECT table_name, table_rows, ROUND((data_length+index_length)/1024/1024,1) AS mb
            FROM information_schema.tables
            WHERE table_schema='{database}'
            ORDER BY table_rows DESC
        """)
        rows = cur.fetchall()
        conn.close()

        result = f"数据库 {database} 共 {len(rows)} 张表:\n\n"
        result += "表名 | 行数 | 大小MB\n"
        result += "-" * 50 + "\n"
        for name, row_count, mb in rows:
            result += f"{name} | {row_count:,} | {mb}\n"
        return result
    except Exception as e:
        return f"错误: {e}"

def search_by_fields(fields: list, min_match: int = 3) -> str:
    """用字段名反查 information_schema，定位包含这些字段的表"""
    import pymysql
    pw = _get_mysql_password()
    try:
        conn = pymysql.connect(host='localhost', user='root', password=pw, charset='utf8mb4')
        cur = conn.cursor()
        placeholders = ','.join(['%s'] * len(fields))
        cur.execute(f"""
            SELECT TABLE_SCHEMA, TABLE_NAME,
                   GROUP_CONCAT(COLUMN_NAME ORDER BY COLUMN_NAME) as matched_cols,
                   COUNT(*) as match_count
            FROM information_schema.COLUMNS
            WHERE COLUMN_NAME IN ({placeholders})
              AND TABLE_SCHEMA NOT IN ('information_schema','mysql','performance_schema','sys')
            GROUP BY TABLE_SCHEMA, TABLE_NAME
            HAVING COUNT(*) >= %s
            ORDER BY match_count DESC, TABLE_SCHEMA, TABLE_NAME
            LIMIT 30
        """, fields + [min_match])
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return f"未找到包含 >={min_match} 个指定字段的表\n查询字段: {', '.join(fields)}"

        result = f"包含指定字段的表（按匹配数降序，最少{min_match}个）:\n"
        result += f"查询字段: {', '.join(fields)}\n\n"
        for db, table, cols, cnt in rows:
            result += f"[{cnt}/{len(fields)}] {db}.{table}\n"
            result += f"  匹配: {cols}\n\n"
        return result
    except Exception as e:
        return f"错误: {e}"

# ============================================================
# Obsidian 笔记读取
# ============================================================

OB_ROOT = HOME / "Work/docs/obsidian-vault/obsidian"

def read_notes(path: str = None, tag: str = None, project: str = None) -> str:
    """读取 Obsidian 笔记"""
    results = []

    if path:
        # 直接读指定路径
        full_path = OB_ROOT / path
        if full_path.exists() and full_path.suffix == '.md':
            content = full_path.read_text(errors='ignore')[:2000]
            return f"📝 {path}\n\n{content}"

    # 按项目搜索
    search_dir = OB_ROOT
    if project:
        search_dir = OB_ROOT / "1-Projects" / project
        if not search_dir.exists():
            # 模糊匹配
            for d in (OB_ROOT / "1-Projects").iterdir():
                if project.lower() in d.name.lower():
                    search_dir = d
                    break

    # 收集笔记
    notes = []
    for f in search_dir.rglob("*.md"):
        if '.obsidian' in str(f):
            continue
        try:
            content = f.read_text(errors='ignore')
            # 按 tag 过滤
            if tag and tag.lower() not in content.lower():
                continue
            # 取前 200 字
            preview = content[:200].replace('\n', ' ')
            rel = str(f.relative_to(OB_ROOT))
            notes.append((rel, preview))
        except:
            continue

    if not notes:
        return f"未找到匹配的笔记 (project={project}, tag={tag})"

    result = f"找到 {len(notes)} 个笔记:\n\n"
    for rel, preview in notes[:15]:
        result += f"📝 {rel}\n   {preview[:100]}...\n\n"
    if len(notes) > 15:
        result += f"... 还有 {len(notes)-15} 个\n"

    return result

# ============================================================
# 工作日志
# ============================================================

def read_worklog(project: str = None) -> str:
    """读取项目工作日志"""
    if project:
        # 搜索项目
        projects_dir = HOME / "Work/projects"
        for d in projects_dir.iterdir():
            if project.lower() in d.name.lower():
                log_file = d / "WORK-LOG.md"
                if log_file.exists():
                    content = log_file.read_text(errors='ignore')
                    return f"📋 {d.name}/WORK-LOG.md\n\n{content[-3000:]}"
        return f"未找到项目 '{project}' 的工作日志"
    else:
        # 全局日志
        global_log = HOME / ".allin_ai_safe/WORK-LOG.md"
        if global_log.exists():
            content = global_log.read_text(errors='ignore')
            return f"📋 全局工作日志\n\n{content[-3000:]}"
        return "全局工作日志不存在"

def add_worklog(project: str, entry: str) -> str:
    """添加工作日志条目"""
    from datetime import datetime
    projects_dir = HOME / "Work/projects"
    for d in projects_dir.iterdir():
        if project.lower() in d.name.lower():
            log_file = d / "WORK-LOG.md"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            log_entry = f"\n### {timestamp}\n{entry}\n"
            with open(log_file, 'a') as f:
                f.write(log_entry)
            return f"✅ 已写入 {d.name}/WORK-LOG.md"
    return f"未找到项目 '{project}'"

# ============================================================
# MCP Protocol Handler (stdio)
# ============================================================

def send_response(id, result):
    response = {"jsonrpc": "2.0", "id": id, "result": result}
    msg = json.dumps(response)
    sys.stdout.write(f"Content-Length: {len(msg.encode())}\r\n\r\n{msg}")
    sys.stdout.flush()

def send_error(id, code, message):
    response = {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}
    msg = json.dumps(response)
    sys.stdout.write(f"Content-Length: {len(msg.encode())}\r\n\r\n{msg}")
    sys.stdout.flush()

def handle_request(request):
    method = request.get("method")
    id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        send_response(id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "knowledge-rag", "version": "1.0.0"},
            "capabilities": {"tools": {}}
        })

    elif method == "notifications/initialized":
        pass  # no response needed

    elif method == "tools/list":
        send_response(id, {
            "tools": [
                {
                    "name": "search_knowledge",
                    "description": "在本地知识库中多集合语义搜索（文档摘要+段落chunks+DDL表结构），merge ranking 返回最相关结果。用于查找项目文档、技术方案、业务逻辑、SQL脚本、数据库表定义等。知识库包含商户画像、油价预测、标签清洗、AI基础设施等项目的文档。核心经营表: gas_dw.dwm_gas_merch_tag_store_df（DWM层油站标签宽表，包含全部15个标签字段）。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索关键词或问题，中文"},
                            "n": {"type": "integer", "description": "返回结果数量，默认5", "default": 5}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "ask_knowledge",
                    "description": "向本地知识库提问并获得AI总结的回答。先语义搜索相关文档，再用本地LLM基于文档生成回答。适合需要理解性回答的复杂问题。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "你的问题，中文"}
                        },
                        "required": ["question"]
                    }
                },
                {
                    "name": "knowledge_stats",
                    "description": "查看知识库的统计信息：文档数量、模型、存储路径等",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "nl2sql",
                    "description": "用自然语言查询 MySQL 数据库。自动将中文问题转为SQL并执行。例如：'KA站点有多少' '各省区重叠站数量' '油站利润排名前10'",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "自然语言问题，中文"}
                        },
                        "required": ["question"]
                    }
                },
                {
                    "name": "query_mysql",
                    "description": "在本地 MySQL 数据库执行只读查询。可查商户画像(data_manager_db)、油价(priceDB)、数仓(gas_dw)等11个库461张表。只允许 SELECT/SHOW/DESCRIBE。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "SQL 查询语句（仅 SELECT）"},
                            "database": {"type": "string", "description": "数据库名，默认 data_manager_db", "default": "data_manager_db"}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "list_mysql_tables",
                    "description": "列出指定 MySQL 数据库的所有表及行数。用于了解数据库结构。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "database": {"type": "string", "description": "数据库名，默认 data_manager_db", "default": "data_manager_db"}
                        }
                    }
                },
                {
                    "name": "search_by_fields",
                    "description": "用字段名反查数据库，找出包含这些字段的所有表（按匹配字段数降序）。用于精确定位业务概念对应的源头表。例如：传入['brand_level','open_24h','parking_available']可定位商户画像标签的核心表。配合search_knowledge使用：先语义搜索获取字段名，再用此工具反查源头表。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "fields": {"type": "array", "items": {"type": "string"}, "description": "字段名列表"},
                            "min_match": {"type": "integer", "description": "最少匹配字段数，默认3", "default": 3}
                        },
                        "required": ["fields"]
                    }
                },
                {
                    "name": "read_notes",
                    "description": "读取 Obsidian 笔记本中的笔记。可按项目名或标签搜索。笔记本包含商户画像、AI基础设施、非油品等项目笔记。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "笔记相对路径（如 1-Projects/商户画像/xxx.md）"},
                            "project": {"type": "string", "description": "项目名关键词（如 商户画像、AI基础设施）"},
                            "tag": {"type": "string", "description": "标签关键词过滤"}
                        }
                    }
                },
                {
                    "name": "read_worklog",
                    "description": "读取项目工作日志。包含每次交互的核心决策和操作记录。不传 project 则返回全局日志。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "description": "项目名关键词（如 商户画像、油价预测），不传则返回全局日志"}
                        }
                    }
                },
                {
                    "name": "add_worklog",
                    "description": "向项目工作日志添加一条记录。用于记录核心决策和操作。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "description": "项目名关键词"},
                            "entry": {"type": "string", "description": "日志内容"}
                        },
                        "required": ["project", "entry"]
                    }
                }
            ]
        })

    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})

        try:
            if tool_name == "search_knowledge":
                results = search_knowledge(args["query"], args.get("n", 5))
                text = f"找到 {len(results)} 个相关文档:\n\n"
                for i, doc in enumerate(results):
                    src_label = {'summaries': '摘要', 'chunks': '段落', 'ddl': '表结构'}.get(doc['source'], doc['source'])
                    match_type = doc.get('match_type', 'vector')
                    match_label = {'vector': '向量', 'bm25': 'BM25', 'both': '双路'}.get(match_type, match_type)
                    heading = f" > {doc['heading']}" if doc.get('heading') else ''
                    rrf = doc.get('rrf_score', '')
                    score_info = f"RRF:{rrf}" if rrf else f"相关度:{doc['similarity']} (加权:{doc['weighted_score']})"
                    text += f"#{i+1} [{src_label}] [{match_label}] {score_info}\n"
                    text += f"   来源: {doc['path']}{heading}\n"
                    text += f"   内容: {doc['text'][:400]}\n\n"
                send_response(id, {"content": [{"type": "text", "text": text}]})

            elif tool_name == "ask_knowledge":
                answer = ask_knowledge(args["question"])
                send_response(id, {"content": [{"type": "text", "text": answer}]})

            elif tool_name == "knowledge_stats":
                stats = get_stats()
                text = "\n".join(f"{k}: {v}" for k, v in stats.items())
                send_response(id, {"content": [{"type": "text", "text": text}]})

            elif tool_name == "nl2sql":
                result = nl2sql(args["question"])
                send_response(id, {"content": [{"type": "text", "text": result}]})

            elif tool_name == "query_mysql":
                result = query_mysql(args["query"], args.get("database", "data_manager_db"))
                send_response(id, {"content": [{"type": "text", "text": result}]})

            elif tool_name == "list_mysql_tables":
                result = list_mysql_tables(args.get("database", "data_manager_db"))
                send_response(id, {"content": [{"type": "text", "text": result}]})

            elif tool_name == "search_by_fields":
                result = search_by_fields(args["fields"], args.get("min_match", 3))
                send_response(id, {"content": [{"type": "text", "text": result}]})

            elif tool_name == "read_notes":
                result = read_notes(args.get("path"), args.get("tag"), args.get("project"))
                send_response(id, {"content": [{"type": "text", "text": result}]})

            elif tool_name == "read_worklog":
                result = read_worklog(args.get("project"))
                send_response(id, {"content": [{"type": "text", "text": result}]})

            elif tool_name == "add_worklog":
                result = add_worklog(args["project"], args["entry"])
                send_response(id, {"content": [{"type": "text", "text": result}]})

            else:
                send_error(id, -32601, f"Unknown tool: {tool_name}")

        except Exception as e:
            send_response(id, {"content": [{"type": "text", "text": f"错误: {str(e)}"}], "isError": True})

    elif method == "ping":
        send_response(id, {})

    else:
        if id is not None:
            send_error(id, -32601, f"Unknown method: {method}")

def read_message():
    """读取一条 MCP 消息（Content-Length 分帧）"""
    # 读 header
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.decode().strip()
        if not line:
            break  # 空行 = header 结束
        if ":" in line:
            key, val = line.split(":", 1)
            headers[key.strip()] = val.strip()

    content_length = int(headers.get("Content-Length", 0))
    if content_length == 0:
        return None

    body = sys.stdin.buffer.read(content_length)
    return json.loads(body.decode())

def main():
    """MCP stdio server main loop"""
    while True:
        try:
            request = read_message()
            if request is None:
                break
            handle_request(request)
        except KeyboardInterrupt:
            break
        except Exception as e:
            sys.stderr.write(f"Error: {e}\n")
            sys.stderr.flush()

if __name__ == "__main__":
    main()
