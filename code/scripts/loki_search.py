#!/usr/bin/env python3
"""
Loki Search CLI -- 命令行搜索预览工具（Hybrid: 向量+BM25+RRF）
用法: python3 loki_search.py "橙化率计算公式"
      python3 loki_search.py "L4模型参数" --top 10
      python3 loki_search.py "橙化率" --collection chunks
      python3 loki_search.py "橙化率" --vector-only   # 仅向量搜索
      python3 loki_search.py "橙化率" --bm25-only     # 仅BM25搜索
"""

import sys, argparse, pickle
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

BGE_PATH   = "/Users/didi/Work/projects/knowledge-rag-知识库/bge-m3-model/bge-m3/BAAI/bge-m3"
CHROMA_DIR = "/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge"
BM25_INDEX = "/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs/bm25_index.pkl"
USERDICT   = "/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/loki_userdict.txt"

COLLECTIONS = {
    'summaries': ('doc_knowledge_bge_m3', 0.3),
    'chunks':    ('doc_knowledge_chunks', 0.7),
    'ddl':       ('ddl_schema_bge_m3', 0.5),
}

STOPWORDS = set("的 了 是 在 和 有 就 不 也 人 都 一 个 上 我 中 到 大 为 这 与 他 它 要 会 可以 没有 对 对于".split())

def _dedup_key(path: str) -> str:
    import os
    base = os.path.basename(path)
    name, _ = os.path.splitext(base)
    return name.lower()


def normalize_score(distance: float) -> float:
    """ChromaDB cosine distance [0,2] -> score [0,1]"""
    return 1.0 - distance / 2.0


def search_single(col, model, query: str, top_k: int = 5):
    """搜索单个 collection"""
    q_embed = model.encode([query], normalize_embeddings=True).tolist()
    results = col.query(query_embeddings=q_embed, n_results=top_k,
                        include=['documents', 'metadatas', 'distances'])
    return results


def search_merge(client, model, query: str, top_k: int = 5, collection: str = None):
    """搜索全部 collection 并 merge ranking"""
    all_results = []

    targets = {collection: COLLECTIONS[collection]} if collection else COLLECTIONS

    for key, (col_name, weight) in targets.items():
        try:
            col = client.get_collection(col_name)
            if col.count() == 0:
                continue
        except Exception:
            continue

        try:
            results = search_single(col, model, query, top_k)
        except Exception as e:
            print(f"  ⚠ {key} 查询跳过: {e}", file=sys.stderr)
            continue

        for i in range(len(results['ids'][0])):
            doc_id = results['ids'][0][i]
            distance = results['distances'][0][i]
            meta = results['metadatas'][0][i]
            doc = results['documents'][0][i]

            score = normalize_score(distance) * weight

            # 提取文件标识用于去重
            file_key = meta.get('source_file', meta.get('path', meta.get('name', doc_id)))

            all_results.append({
                'id': doc_id,
                'score': score,
                'raw_score': normalize_score(distance),
                'weight': weight,
                'source': key,
                'file': file_key,
                'meta': meta,
                'doc': doc[:500],
            })

    # 按 score 排序
    all_results.sort(key=lambda x: x['score'], reverse=True)

    # 去重: 同 basename 只保留最高分
    seen_files = set()
    deduped = []
    for r in all_results:
        dk = _dedup_key(r['file'])
        if dk not in seen_files:
            seen_files.add(dk)
            deduped.append(r)

    return deduped[:top_k]


def _tokenize(text: str) -> list:
    import jieba
    jieba.load_userdict(USERDICT)
    return [w.lower().strip() for w in jieba.cut(text) if w.strip() and w.strip() not in STOPWORDS]


def search_bm25_only(query: str, top_k: int = 5) -> list:
    """纯 BM25 搜索"""
    try:
        with open(BM25_INDEX, 'rb') as f:
            index = pickle.load(f)
    except Exception as e:
        print(f"  ⚠ BM25 索引加载失败: {e}", file=sys.stderr)
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
            'id': file_key,
            'score': scores[idx],
            'raw_score': scores[idx],
            'weight': 1.0,
            'source': meta['source'],
            'file': file_key,
            'meta': meta,
            'doc': meta.get('doc_preview', '')[:500],
            'match_type': 'bm25',
        })
        if len(results) >= top_k:
            break
    return results


def search_hybrid(client, model, query: str, top_k: int = 5) -> list:
    """Hybrid Search: 向量 top20 + BM25 top20 → RRF 融合"""
    vector_hits = search_merge(client, model, query, top_k=20)
    bm25_hits = search_bm25_only(query, top_k=20)

    if not bm25_hits:
        for r in vector_hits[:top_k]:
            r['match_type'] = 'vector'
        return vector_hits[:top_k]

    # RRF 融合
    k = 60
    scores = {}
    source_map = {}
    meta_map = {}

    for rank, hit in enumerate(vector_hits):
        key = _dedup_key(hit['file'])
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
        source_map[key] = 'vector'
        if key not in meta_map:
            meta_map[key] = hit

    for rank, hit in enumerate(bm25_hits):
        key = _dedup_key(hit['file'])
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
        if key in source_map:
            source_map[key] = 'both'
        else:
            source_map[key] = 'bm25'
            if key not in meta_map:
                meta_map[key] = hit

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    results = []
    for file_key, rrf_score in ranked:
        hit = meta_map[file_key].copy()
        hit['rrf_score'] = rrf_score
        hit['match_type'] = source_map[file_key]
        results.append(hit)
    return results


def print_results(results, verbose=False):
    if not results:
        print("  (无结果)")
        return

    for i, r in enumerate(results):
        meta = r['meta']

        # 标题行：来源 + 文件名/表名
        if 'source_file' in meta:
            name = Path(meta['source_file']).stem
            location = meta['source_file']
        elif 'path' in meta:
            name = meta.get('name', Path(meta['path']).stem)
            location = meta['path']
        elif 'table' in meta:
            name = f"{meta.get('db', '')}.{meta['table']}"
            location = name
        else:
            name = r['id'][:30]
            location = ''

        heading = meta.get('heading', '')
        source_label = {'summaries': '📄摘要', 'chunks': '📌段落', 'ddl': '🗃️表结构'}.get(r['source'], r['source'])
        match_type = r.get('match_type', '')
        match_label = {'vector': '🔵向量', 'bm25': '🟠BM25', 'both': '🟢双路'}.get(match_type, '')

        rrf = r.get('rrf_score')
        if rrf:
            score_str = f"RRF:{rrf:.5f}"
        else:
            score_pct = int(r['raw_score'] * 100)
            score_str = f"相关度:{score_pct}%"

        print(f"\n  #{i+1}  {source_label}  {match_label}  {score_str}  {name}")
        if heading:
            print(f"      章节: {heading}")
        if location and verbose:
            print(f"      路径: {location}")

        # 内容预览
        raw = r['doc'].strip()

        # 提取摘要和原文
        summary = ''
        body = raw
        if '摘要:' in raw:
            after = raw.split('摘要:', 1)[1]
            # 摘要到 \n--- 或 \n\n 截止
            for sep in ['\n---', '\n\n']:
                if sep in after:
                    summary = after.split(sep, 1)[0].strip()
                    break
            else:
                summary = after[:200].strip()
            # 去掉 "关键术语：xxx" 噪音
            if '关键术语' in summary:
                summary = summary.split('关键术语')[0].strip().rstrip('。')
        if '\n---\n' in raw:
            body = raw.split('\n---\n', 1)[1]

        # DDL/表结构：提取表说明
        if r['source'] == 'ddl':
            table_name = meta.get('table', '')
            db_name = meta.get('db', '')
            desc = meta.get('description', meta.get('comment', ''))
            cols = raw[:300] if not desc else ''
            summary = f"表 {db_name}.{table_name}" + (f" — {desc}" if desc else '')
            body = raw

        # 默认显示摘要；-v 显示原文
        if summary:
            print(f"      {summary}")
        if verbose and body != summary:
            # 清理原文预览
            body_clean = body.strip().replace('\n', ' ')
            while '  ' in body_clean:
                body_clean = body_clean.replace('  ', ' ')
            preview = body_clean[:400]
            if len(body_clean) > 400:
                preview += '...'
            print(f"      原文: {preview}")


def main():
    parser = argparse.ArgumentParser(description='Loki Search CLI')
    parser.add_argument('query', help='搜索关键词')
    parser.add_argument('--top', type=int, default=5, help='返回条数 (default: 5)')
    parser.add_argument('--collection', '-c', choices=['summaries', 'chunks', 'ddl'],
                        help='只搜索指定 collection')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示文档预览')
    parser.add_argument('--vector-only', action='store_true', help='仅向量搜索')
    parser.add_argument('--bm25-only', action='store_true', help='仅BM25搜索')
    args = parser.parse_args()

    mode = 'hybrid'
    if args.vector_only:
        mode = 'vector'
    elif args.bm25_only:
        mode = 'bm25'

    if mode != 'bm25':
        print(f"加载 BGE-M3...")
        model = SentenceTransformer(BGE_PATH)
        client = chromadb.PersistentClient(CHROMA_DIR)

        # 显示 collection 状态
        print(f"Collections:")
        for key, (name, w) in COLLECTIONS.items():
            try:
                col = client.get_collection(name)
                print(f"  {key}: {col.count()} records (weight={w})")
            except Exception:
                print(f"  {key}: NOT FOUND")
    else:
        model = None
        client = None

    print(f"\n搜索: \"{args.query}\" (top={args.top}, mode={mode})")
    print("=" * 60)

    if mode == 'bm25':
        results = search_bm25_only(args.query, args.top)
    elif mode == 'vector':
        results = search_merge(client, model, args.query, args.top, args.collection)
        for r in results:
            r['match_type'] = 'vector'
    else:
        results = search_hybrid(client, model, args.query, args.top)

    print_results(results, args.verbose)

    print(f"\n共 {len(results)} 条结果")


if __name__ == '__main__':
    main()
