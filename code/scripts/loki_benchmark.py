#!/usr/bin/env python3
"""
Loki Search Benchmark -- 搜索质量对比测试
用法: python3 loki_benchmark.py              # 跑全部 query
      python3 loki_benchmark.py --phase1     # 只测 Phase 1 (summaries)
      python3 loki_benchmark.py --phase2     # 只测 Phase 1+2 (merge ranking)

每个 query 有人工标注的 ground truth (预期命中文件)。
对比 Phase 1 only vs Phase 1+2 的 recall@5。
"""

import sys, json, argparse, time
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

BGE_PATH   = "/Users/didi/Work/projects/knowledge-rag-知识库/bge-m3-model/bge-m3/BAAI/bge-m3"
CHROMA_DIR = "/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge"
LOG_DIR    = Path("/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs")

# ========== Ground Truth: 20 个 query + 预期命中 ==========
# 每个 query 标注 1-3 个预期命中文件（部分匹配即可）
BENCHMARK_QUERIES = [
    {
        "query": "橙化率计算公式",
        "expected_files": ["FGW项目知识图谱", "l4_gravity_model_v3", "橙化率"],
        "expected_chunk": "分子 = (日均汽油订单",  # Phase 2 应该找到的具体内容
    },
    {
        "query": "L4引力模型城市权重参数 ALPHA",
        "expected_files": ["l4_gravity_model", "FGW项目知识图谱"],
        "expected_chunk": "vehicle:0.45",
    },
    {
        "query": "变化率 V6 去重取平均",
        "expected_files": ["change_rate_calculator_v6", "CHANGE_RATE_CALCULATION"],
        "expected_chunk": "去重取平均",
    },
    {
        "query": "发改委搁浅规则 50元每吨",
        "expected_files": ["FGW项目知识图谱", "FGW_PRICE_CALCULATION", "run_fgw"],
        "expected_chunk": "50 元/吨",
    },
    {
        "query": "92号汽油吨价到升价转换系数",
        "expected_files": ["FGW项目知识图谱", "FGW_PRICE_CALCULATION"],
        "expected_chunk": "1388",
    },
    {
        "query": "商户画像宽表字段映射关系",
        "expected_files": ["字段映射关系", "商户画像宽表", "JOIN逻辑"],
        "expected_chunk": "字段映射",
    },
    {
        "query": "非油品随手购BRD核心功能模块",
        "expected_files": ["非油品线上化项目_BRD", "非油品", "随手购"],
        "expected_chunk": "BRD",
    },
    {
        "query": "标签ETL parking S1 S2 落地",
        "expected_files": ["parking_S1S2", "标签", "ETL"],
        "expected_chunk": "parking",
    },
    {
        "query": "ChromaDB HNSW index 修复方法",
        "expected_files": ["index_metadata", "ChromaDB", "HNSW"],
        "expected_chunk": "pickle",
    },
    {
        "query": "BGE-M3 模型下载路径和维度",
        "expected_files": ["BGE_M3_DOWNLOAD", "bge-m3"],
        "expected_chunk": "1024",
    },
    {
        "query": "flock 互斥锁 ChromaDB 并发写保护",
        "expected_files": ["loki_pipeline", "loki_reindex", "loki_chunk"],
        "expected_chunk": "flock",
    },
    {
        "query": "WTI Brent Dubai 原油权重比例",
        "expected_files": ["FGW项目知识图谱", "change_rate", "原油"],
        "expected_chunk": "25:50:25",
    },
    {
        "query": "MCP server search_knowledge 搜索接口",
        "expected_files": ["server", "mcp", "search"],
        "expected_chunk": "search_knowledge",
    },
    {
        "query": "tag_enum 兜底值治理方案",
        "expected_files": ["tag_enum", "兜底", "enum"],
        "expected_chunk": "兜底",
    },
    {
        "query": "2025Q4 双轮驱动战略目标",
        "expected_files": ["双轮驱动", "2025Q4", "战略"],
        "expected_chunk": "双轮驱动",
    },
    {
        "query": "Ollama qwen2.5 subprocess 硬超时",
        "expected_files": ["loki_reindex", "ollama", "qwen"],
        "expected_chunk": "OLLAMA_HARD_TIMEOUT",
    },
    {
        "query": "站点吸引力 attractiveness 品牌系数",
        "expected_files": ["l4_gravity_model", "FGW项目知识图谱"],
        "expected_chunk": "brand",
    },
    {
        "query": "merchant_profile_analysis 表结构",
        "expected_files": ["merchant_profile", "analysis"],
        "expected_chunk": "merchant_profile",
    },
    {
        "query": "Loki watchdog 卡死检测 stall timeout",
        "expected_files": ["watchdog", "loki_reindex_watchdog"],
        "expected_chunk": "STALL_TIMEOUT",
    },
    {
        "query": "加油站 OCR 识别 PaddleOCR",
        "expected_files": ["ocr", "gas_station", "PaddleOCR"],
        "expected_chunk": "OCR",
    },
]


def normalize_score(distance: float) -> float:
    return 1.0 - distance / 2.0


def search_phase1(client, model, query: str, top_k: int = 5):
    """Phase 1 only: 只搜 summaries"""
    col = client.get_collection('doc_knowledge_bge_m3')
    q_embed = model.encode([query], normalize_embeddings=True).tolist()
    results = col.query(query_embeddings=q_embed, n_results=top_k,
                        include=['documents', 'metadatas', 'distances'])
    hits = []
    for i in range(len(results['ids'][0])):
        meta = results['metadatas'][0][i]
        hits.append({
            'file': meta.get('name', meta.get('source_file', results['ids'][0][i])),
            'doc': results['documents'][0][i],
            'score': normalize_score(results['distances'][0][i]),
        })
    return hits


def search_phase2(client, model, query: str, top_k: int = 5):
    """Phase 1+2: merge ranking across summaries + chunks + ddl"""
    q_embed = model.encode([query], normalize_embeddings=True).tolist()

    collections = {
        'doc_knowledge_bge_m3': 0.5,
        'doc_knowledge_chunks': 0.3,
        'ddl_schema_bge_m3': 0.5,
    }

    all_hits = []
    for col_name, weight in collections.items():
        try:
            col = client.get_collection(col_name)
            if col.count() == 0:
                continue
        except Exception:
            continue

        results = col.query(query_embeddings=q_embed, n_results=top_k,
                            include=['documents', 'metadatas', 'distances'])

        for i in range(len(results['ids'][0])):
            meta = results['metadatas'][0][i]
            file_key = meta.get('source_file', meta.get('name', meta.get('path', '')))
            all_hits.append({
                'file': file_key,
                'doc': results['documents'][0][i],
                'score': normalize_score(results['distances'][0][i]) * weight,
                'raw_score': normalize_score(results['distances'][0][i]),
                'source': col_name.split('_')[-1],  # bge_m3 / chunks / bge_m3
            })

    # 按 score 排序 + 去重
    all_hits.sort(key=lambda x: x['score'], reverse=True)
    seen = set()
    deduped = []
    for h in all_hits:
        if h['file'] not in seen:
            seen.add(h['file'])
            deduped.append(h)
    return deduped[:top_k]


def evaluate(hits: list, expected_files: list, expected_chunk: str = None):
    """评估搜索结果"""
    # Recall@5: 预期文件中有多少被找到
    found_files = 0
    for exp in expected_files:
        exp_lower = exp.lower()
        for h in hits:
            if exp_lower in h['file'].lower():
                found_files += 1
                break

    recall = found_files / len(expected_files) if expected_files else 0

    # Chunk hit: 是否找到了预期的具体内容
    chunk_hit = False
    if expected_chunk:
        for h in hits:
            if expected_chunk.lower() in h['doc'].lower():
                chunk_hit = True
                break

    return recall, chunk_hit


def run_benchmark(mode='both'):
    print(f"加载 BGE-M3...")
    model = SentenceTransformer(BGE_PATH)
    client = chromadb.PersistentClient(CHROMA_DIR)

    # 检查 collection 状态
    for name in ['doc_knowledge_bge_m3', 'doc_knowledge_chunks', 'ddl_schema_bge_m3']:
        try:
            col = client.get_collection(name)
            print(f"  {name}: {col.count()} records")
        except Exception:
            print(f"  {name}: NOT FOUND")

    results_p1 = []
    results_p2 = []

    print(f"\n{'='*80}")
    print(f"Loki Search Benchmark - {len(BENCHMARK_QUERIES)} queries")
    print(f"{'='*80}")

    for qi, bq in enumerate(BENCHMARK_QUERIES):
        query = bq['query']
        expected = bq['expected_files']
        exp_chunk = bq.get('expected_chunk', '')

        print(f"\n[{qi+1}/{len(BENCHMARK_QUERIES)}] \"{query}\"")

        if mode in ('both', 'phase1'):
            hits_p1 = search_phase1(client, model, query)
            recall_p1, chunk_p1 = evaluate(hits_p1, expected, exp_chunk)
            results_p1.append({'recall': recall_p1, 'chunk_hit': chunk_p1})
            p1_files = [h['file'][-40:] for h in hits_p1[:3]]
            print(f"  Phase 1: recall={recall_p1:.0%} chunk={'Y' if chunk_p1 else 'N'} | {p1_files}")

        if mode in ('both', 'phase2'):
            hits_p2 = search_phase2(client, model, query)
            recall_p2, chunk_p2 = evaluate(hits_p2, expected, exp_chunk)
            results_p2.append({'recall': recall_p2, 'chunk_hit': chunk_p2})
            p2_files = [f"{h['file'][-30:]}({h.get('source','')})" for h in hits_p2[:3]]
            print(f"  Phase 2: recall={recall_p2:.0%} chunk={'Y' if chunk_p2 else 'N'} | {p2_files}")

    # 汇总
    print(f"\n{'='*80}")
    print(f"BENCHMARK SUMMARY")
    print(f"{'='*80}")

    if results_p1:
        avg_recall_p1 = sum(r['recall'] for r in results_p1) / len(results_p1)
        chunk_rate_p1 = sum(1 for r in results_p1 if r['chunk_hit']) / len(results_p1)
        print(f"Phase 1 (summaries only):")
        print(f"  Avg Recall@5:    {avg_recall_p1:.1%}")
        print(f"  Chunk Hit Rate:  {chunk_rate_p1:.1%}")

    if results_p2:
        avg_recall_p2 = sum(r['recall'] for r in results_p2) / len(results_p2)
        chunk_rate_p2 = sum(1 for r in results_p2 if r['chunk_hit']) / len(results_p2)
        print(f"Phase 1+2 (merge ranking):")
        print(f"  Avg Recall@5:    {avg_recall_p2:.1%}")
        print(f"  Chunk Hit Rate:  {chunk_rate_p2:.1%}")

    if results_p1 and results_p2:
        delta_recall = avg_recall_p2 - avg_recall_p1
        delta_chunk = chunk_rate_p2 - chunk_rate_p1
        print(f"\nDelta (Phase 2 improvement):")
        print(f"  Recall:     {delta_recall:+.1%}")
        print(f"  Chunk Hit:  {delta_chunk:+.1%}")

    # 保存结果
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'queries': len(BENCHMARK_QUERIES),
        'phase1': {'avg_recall': avg_recall_p1, 'chunk_hit_rate': chunk_rate_p1} if results_p1 else None,
        'phase2': {'avg_recall': avg_recall_p2, 'chunk_hit_rate': chunk_rate_p2} if results_p2 else None,
    }
    report_file = LOG_DIR / f"benchmark_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n结果已保存: {report_file}")


def main():
    parser = argparse.ArgumentParser(description='Loki Search Benchmark')
    parser.add_argument('--phase1', action='store_true', help='只测 Phase 1')
    parser.add_argument('--phase2', action='store_true', help='只测 Phase 1+2')
    args = parser.parse_args()

    if args.phase1:
        mode = 'phase1'
    elif args.phase2:
        mode = 'phase2'
    else:
        mode = 'both'

    run_benchmark(mode)


if __name__ == '__main__':
    main()
