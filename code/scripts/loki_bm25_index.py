#!/usr/bin/env python3
"""
Loki BM25 索引构建器
从 ChromaDB 读取全部文档，jieba 分词，构建 BM25 索引并 pickle 持久化。

用法:
  python3 loki_bm25_index.py          # 构建索引
  python3 loki_bm25_index.py --test   # 构建 + 测试搜索
"""

import sys, time, pickle, argparse, re
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi
import chromadb

CHROMA_DIR = "/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge"
SCRIPT_DIR = Path(__file__).parent
USERDICT   = str(SCRIPT_DIR / "loki_userdict.txt")
INDEX_PATH = str(SCRIPT_DIR / "logs" / "bm25_index.pkl")

COLLECTIONS = {
    'summaries': 'doc_knowledge_bge_m3',
    'chunks':    'doc_knowledge_chunks',
    'ddl':       'ddl_schema_bge_m3',
}

# 停用词（高频无意义词）
STOPWORDS = set("的 了 是 在 和 有 就 不 也 人 都 一 个 上 我 中 到 大 为 这 与 他 它 要 会 可以 没有 对 对于".split())


def tokenize(text: str) -> list:
    """jieba 分词 + 停用词过滤 + 小写"""
    words = jieba.cut(text)
    return [w.lower().strip() for w in words if w.strip() and len(w.strip()) > 0 and w.strip() not in STOPWORDS]


def load_all_docs(client) -> tuple:
    """从 ChromaDB 加载全部文档，返回 (corpus_tokens, doc_ids, doc_meta)"""
    corpus_tokens = []
    doc_ids = []
    doc_meta = []

    for source_key, col_name in COLLECTIONS.items():
        try:
            col = client.get_collection(col_name)
            count = col.count()
            if count == 0:
                continue
        except Exception:
            print(f"  ⚠ {col_name}: 不存在，跳过")
            continue

        print(f"  加载 {col_name}: {count} 条...")

        # ChromaDB get() 分批拉取
        batch_size = 5000
        offset = 0
        loaded = 0
        while offset < count:
            results = col.get(
                limit=batch_size,
                offset=offset,
                include=['documents', 'metadatas']
            )
            if not results['ids']:
                break

            for i, doc_id in enumerate(results['ids']):
                doc_text = results['documents'][i] or ''
                meta = results['metadatas'][i] or {}

                # 构建用于 BM25 的文本：文档内容 + 元数据关键字段
                searchable = doc_text
                for field in ['source_file', 'name', 'path', 'heading', 'topic', 'domain', 'table', 'db', 'description']:
                    if field in meta and meta[field]:
                        searchable += ' ' + str(meta[field])

                tokens = tokenize(searchable)
                if not tokens:
                    continue

                corpus_tokens.append(tokens)
                doc_ids.append(doc_id)

                # 提取统一的 file_key 用于去重
                file_key = meta.get('source_file', meta.get('path', meta.get('name', meta.get('table', doc_id))))
                doc_meta.append({
                    'source': source_key,
                    'file': file_key,
                    'heading': meta.get('heading', ''),
                    'topic': meta.get('topic', meta.get('table', '')),
                    'domain': meta.get('domain', source_key),
                    'doc_preview': doc_text[:500],
                })
                loaded += 1

            offset += batch_size

        print(f"    → {loaded} 条有效文档")

    return corpus_tokens, doc_ids, doc_meta


def build_index():
    """构建 BM25 索引并持久化"""
    print("加载 jieba 自定义词典...")
    jieba.load_userdict(USERDICT)

    print("连接 ChromaDB...")
    client = chromadb.PersistentClient(CHROMA_DIR)

    t0 = time.time()
    corpus_tokens, doc_ids, doc_meta = load_all_docs(client)
    t_load = time.time() - t0
    print(f"\n加载完成: {len(corpus_tokens)} 条文档，耗时 {t_load:.1f}s")

    if not corpus_tokens:
        print("错误: 无文档可索引")
        sys.exit(1)

    print("构建 BM25 索引...")
    t1 = time.time()
    bm25 = BM25Okapi(corpus_tokens)
    t_build = time.time() - t1
    print(f"索引构建完成，耗时 {t_build:.1f}s")

    # 持久化
    index_data = {
        'bm25': bm25,
        'doc_ids': doc_ids,
        'doc_meta': doc_meta,
        'corpus_tokens': corpus_tokens,  # 保留用于调试
        'build_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'doc_count': len(doc_ids),
    }

    Path(INDEX_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, 'wb') as f:
        pickle.dump(index_data, f)

    size_mb = Path(INDEX_PATH).stat().st_size / 1024 / 1024
    print(f"索引已保存: {INDEX_PATH} ({size_mb:.1f}MB)")

    return index_data


def search_bm25(index_data: dict, query: str, top_k: int = 20) -> list:
    """BM25 搜索，返回 top_k 结果（去重）"""
    bm25 = index_data['bm25']
    doc_meta = index_data['doc_meta']

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    scores = bm25.get_scores(query_tokens)

    # 取 top indices
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    # 去重（同文件只保留最高分）
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
            'heading': meta['heading'],
            'topic': meta['topic'],
            'domain': meta['domain'],
            'doc_preview': meta['doc_preview'],
        })
        if len(results) >= top_k:
            break

    return results


def test_search(index_data: dict):
    """测试搜索"""
    test_queries = [
        "橙化率计算公式",
        "发改委搁浅规则",
        "S1S2标签ETL",
        "商户画像宽表字段映射",
        "BGE-M3模型下载",
        "tag_enum兜底值",
        "WTI Brent Dubai 原油权重",
    ]

    print(f"\n{'='*60}")
    print("BM25 搜索测试")
    print(f"{'='*60}")

    for q in test_queries:
        results = search_bm25(index_data, q, top_k=3)
        print(f"\n  Q: {q}")
        if not results:
            print("    (无结果)")
            continue
        for i, r in enumerate(results):
            src = {'summaries': '摘要', 'chunks': '段落', 'ddl': 'DDL'}.get(r['source'], r['source'])
            print(f"    #{i+1} [{src}] score={r['bm25_score']:.2f} | {r['file'][-50:]}")


def main():
    parser = argparse.ArgumentParser(description='Loki BM25 索引构建器')
    parser.add_argument('--test', action='store_true', help='构建后测试搜索')
    args = parser.parse_args()

    index_data = build_index()

    if args.test:
        test_search(index_data)


if __name__ == '__main__':
    main()
