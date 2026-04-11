#!/usr/bin/env python3
"""
Loki Search CLI -- 命令行搜索预览工具
用法: python3 loki_search.py "橙化率计算公式"
      python3 loki_search.py "L4模型参数" --top 10
      python3 loki_search.py "橙化率" --collection chunks
"""

import sys, argparse
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

BGE_PATH   = "/Users/didi/Work/projects/knowledge-rag-知识库/bge-m3-model/bge-m3/BAAI/bge-m3"
CHROMA_DIR = "/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge"

COLLECTIONS = {
    'summaries': ('doc_knowledge_bge_m3', 0.3),
    'chunks':    ('doc_knowledge_chunks', 0.7),
    'ddl':       ('ddl_schema_bge_m3', 0.5),
}


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

    # 去重: 同文件只保留最高分
    seen_files = set()
    deduped = []
    for r in all_results:
        if r['file'] not in seen_files:
            seen_files.add(r['file'])
            deduped.append(r)

    return deduped[:top_k]


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
        score_pct = int(r['raw_score'] * 100)

        print(f"\n  #{i+1}  {source_label}  相关度:{score_pct}%  {name}")
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
    args = parser.parse_args()

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

    print(f"\n搜索: \"{args.query}\" (top={args.top})")
    print("=" * 60)

    results = search_merge(client, model, args.query, args.top, args.collection)
    print_results(results, args.verbose)

    print(f"\n共 {len(results)} 条结果")


if __name__ == '__main__':
    main()
