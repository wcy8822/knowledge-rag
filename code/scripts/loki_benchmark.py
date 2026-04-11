#!/usr/bin/env python3
"""
Loki Search Benchmark -- 搜索质量对比测试
用法: python3 loki_benchmark.py              # 跑全部 query
      python3 loki_benchmark.py --phase1     # 只测 Phase 1 (summaries)
      python3 loki_benchmark.py --phase2     # 只测 Phase 1+2 (merge ranking)

每个 query 有人工标注的 ground truth (预期命中文件)。
对比 Phase 1 only vs Phase 1+2 的 recall@5。
"""

import sys, json, argparse, time, pickle
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

BGE_PATH   = "/Users/didi/Work/projects/knowledge-rag-知识库/bge-m3-model/bge-m3/BAAI/bge-m3"
CHROMA_DIR = "/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge"
BM25_INDEX = "/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs/bm25_index.pkl"
USERDICT   = "/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/loki_userdict.txt"
LOG_DIR    = Path("/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs")

STOPWORDS = set("的 了 是 在 和 有 就 不 也 人 都 一 个 上 我 中 到 大 为 这 与 他 它 要 会 可以 没有 对 对于".split())

# ========== Ground Truth: 20 个 query + 预期命中 ==========
# 每个 query 标注 1-3 个预期命中文件（部分匹配即可）
BENCHMARK_QUERIES = [
    {
        "query": "橙化率计算公式",
        "expected_files": ["FGW项目知识图谱", "l4_gravity_model_v3", "橙化率"],
        "expected_chunk": "分子 = (日均汽油订单",
        "qa_question": "橙化率的计算公式是什么？分子和分母分别是什么？",
        "qa_facts": ["汽油消费量", "全国"],
    },
    {
        "query": "L4引力模型城市权重参数 ALPHA",
        "expected_files": ["l4_gravity_model", "FGW项目知识图谱"],
        "expected_chunk": "vehicle:0.45",
        "qa_question": "L4引力模型中城市权重参数 ALPHA 的值是多少？vehicle 系数是多少？",
        "qa_facts": ["0.45"],
    },
    {
        "query": "变化率 V6 去重取平均",
        "expected_files": ["change_rate_calculator_v6", "CHANGE_RATE_CALCULATION"],
        "expected_chunk": "去重取平均",
        "qa_question": "变化率 V6 版本中去重取平均的逻辑是怎样的？",
        "qa_facts": ["去重", "平均"],
    },
    {
        "query": "发改委搁浅规则 50元每吨",
        "expected_files": ["FGW项目知识图谱", "FGW_PRICE_CALCULATION", "run_fgw"],
        "expected_chunk": "50 元/吨",
        "qa_question": "发改委油价调整中搁浅规则的阈值是多少？",
        "qa_facts": ["50"],
    },
    {
        "query": "92号汽油吨价到升价转换系数",
        "expected_files": ["FGW项目知识图谱", "FGW_PRICE_CALCULATION"],
        "expected_chunk": "1388",
        "qa_question": "92号汽油从吨价转换到升价的系数是多少？",
        "qa_facts": ["1388"],
    },
    {
        "query": "商户画像宽表字段映射关系",
        "expected_files": ["字段映射关系", "商户画像宽表", "JOIN逻辑"],
        "expected_chunk": "字段映射",
        "qa_question": "商户画像宽表有哪些关键字段？字段映射是怎么做的？",
        "qa_facts": ["字段映射", "宽表"],
    },
    {
        "query": "非油品随手购BRD核心功能模块",
        "expected_files": ["非油品线上化项目_BRD", "非油品", "随手购"],
        "expected_chunk": "BRD",
        "qa_question": "非油品随手购BRD中有哪些核心功能模块？",
        "qa_facts": ["随手购"],
    },
    {
        "query": "标签ETL parking S1 S2 落地",
        "expected_files": ["parking_S1S2", "标签", "ETL"],
        "expected_chunk": "parking",
        "qa_question": "parking 标签 S1/S2 的 ETL 落地逻辑是什么？",
        "qa_facts": ["parking", "S1", "S2"],
    },
    {
        "query": "ChromaDB HNSW index 修复方法",
        "expected_files": ["index_metadata", "ChromaDB", "HNSW"],
        "expected_chunk": "pickle",
        "qa_question": "ChromaDB HNSW index 出问题时怎么修复？",
        "qa_facts": ["HNSW"],
    },
    {
        "query": "BGE-M3 模型下载路径和维度",
        "expected_files": ["BGE_M3_DOWNLOAD", "bge-m3"],
        "expected_chunk": "1024",
        "qa_question": "BGE-M3 模型的 embedding 维度是多少？",
        "qa_facts": ["1024"],
    },
    {
        "query": "flock 互斥锁 ChromaDB 并发写保护",
        "expected_files": ["loki_pipeline", "loki_reindex", "loki_chunk"],
        "expected_chunk": "flock",
        "qa_question": "Loki 如何防止 ChromaDB 并发写冲突？",
        "qa_facts": ["flock", "锁"],
    },
    {
        "query": "WTI Brent Dubai 原油权重比例",
        "expected_files": ["FGW项目知识图谱", "change_rate", "原油"],
        "expected_chunk": "25:50:25",
        "qa_question": "WTI、Brent、Dubai 三种原油的权重比例是多少？",
        "qa_facts": ["25", "50"],
    },
    {
        "query": "MCP server search_knowledge 搜索接口",
        "expected_files": ["server", "mcp", "search"],
        "expected_chunk": "search_knowledge",
        "qa_question": "MCP server 的 search_knowledge 接口做什么？",
        "qa_facts": ["search_knowledge", "搜索"],
    },
    {
        "query": "tag_enum 兜底值治理方案",
        "expected_files": ["tag_enum", "兜底", "enum"],
        "expected_chunk": "兜底",
        "qa_question": "tag_enum 表的兜底值治理方案是什么？",
        "qa_facts": ["兜底"],
    },
    {
        "query": "2025Q4 双轮驱动战略目标",
        "expected_files": ["双轮驱动", "2025Q4", "战略"],
        "expected_chunk": "双轮驱动",
        "qa_question": "2025Q4双轮驱动的战略目标是什么？",
        "qa_facts": ["双轮驱动"],
    },
    {
        "query": "Ollama qwen2.5 subprocess 硬超时",
        "expected_files": ["loki_reindex", "ollama", "qwen"],
        "expected_chunk": "OLLAMA_HARD_TIMEOUT",
        "qa_question": "Loki 中 Ollama qwen2.5 的硬超时机制是怎样的？",
        "qa_facts": ["超时", "timeout"],
    },
    {
        "query": "站点吸引力 attractiveness 品牌系数",
        "expected_files": ["l4_gravity_model", "FGW项目知识图谱"],
        "expected_chunk": "brand",
        "qa_question": "引力模型中站点吸引力的品牌系数是怎么计算的？",
        "qa_facts": ["brand", "品牌"],
    },
    {
        "query": "merchant_profile_analysis 表结构",
        "expected_files": ["merchant_profile", "analysis"],
        "expected_chunk": "merchant_profile",
        "qa_question": "merchant_profile_analysis 表有哪些关键字段？",
        "qa_facts": ["merchant_profile"],
    },
    {
        "query": "Loki watchdog 卡死检测 stall timeout",
        "expected_files": ["watchdog", "loki_reindex_watchdog"],
        "expected_chunk": "STALL_TIMEOUT",
        "qa_question": "Loki watchdog 如何检测卡死？stall timeout 是多少？",
        "qa_facts": ["stall", "timeout"],
    },
    {
        "query": "加油站 OCR 识别 PaddleOCR",
        "expected_files": ["ocr", "gas_station", "PaddleOCR"],
        "expected_chunk": "OCR",
        "qa_question": "加油站图片 OCR 识别用的什么技术方案？",
        "qa_facts": ["OCR"],
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


def _tokenize(text: str) -> list:
    import jieba
    jieba.load_userdict(USERDICT)
    return [w.lower().strip() for w in jieba.cut(text) if w.strip() and w.strip() not in STOPWORDS]


def search_hybrid(client, model, query: str, top_k: int = 5, bm25_index=None):
    """Hybrid: 向量 top20 + BM25 top20 → RRF"""
    # 向量搜索
    vector_hits = search_phase2(client, model, query, top_k=20)

    # BM25 搜索
    bm25_hits = []
    if bm25_index and 'bm25' in bm25_index:
        tokens = _tokenize(query)
        if tokens:
            scores = bm25_index['bm25'].get_scores(tokens)
            doc_meta = bm25_index['doc_meta']
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            seen = set()
            for idx in top_indices:
                if scores[idx] <= 0:
                    break
                meta = doc_meta[idx]
                fk = meta['file']
                if fk in seen:
                    continue
                seen.add(fk)
                bm25_hits.append({'file': fk, 'doc': meta.get('doc_preview', '')})
                if len(bm25_hits) >= 20:
                    break

    if not bm25_hits:
        return vector_hits[:top_k]

    # RRF
    k = 60
    rrf_scores = {}
    meta_map = {}
    for rank, hit in enumerate(vector_hits):
        key = hit['file']
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
        meta_map[key] = hit
    for rank, hit in enumerate(bm25_hits):
        key = hit['file']
        rrf_scores[key] = rrf_scores.get(key, 0) + 1.0 / (k + rank + 1)
        if key not in meta_map:
            meta_map[key] = {'file': key, 'doc': hit['doc'], 'score': 0}

    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    results = []
    for fk, score in ranked:
        hit = meta_map[fk].copy()
        hit['rrf_score'] = score
        results.append(hit)
    return results


OLLAMA_API = "http://localhost:11434/api/generate"
QA_MODEL   = "qwen2.5:7b"

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


def qa_evaluate(hits: list, question: str, facts: list) -> tuple:
    """QA 评测：把搜索结果喂给 LLM，判断回答是否包含关键事实
    返回 (pass_bool, answer_str)
    """
    import urllib.request

    # 拼 context
    context_parts = []
    for i, h in enumerate(hits[:5]):
        context_parts.append(f"[文档{i+1}] {h['file']}\n{h['doc'][:600]}")

    prompt = (
        "你是企业知识库助手。基于以下检索到的文档回答问题。直接回答，简洁专业，中文。\n\n"
        "=== 文档 ===\n" + "\n\n".join(context_parts) +
        f"\n\n=== 问题 ===\n{question}\n\n=== 回答 ===\n"
    )

    data = json.dumps({
        "model": QA_MODEL, "prompt": prompt, "stream": False,
        "options": {"num_predict": 512, "temperature": 0.1}
    }).encode()

    try:
        req = urllib.request.Request(OLLAMA_API, data=data,
                                     headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=120)
        answer = json.loads(resp.read()).get("response", "").strip()
    except Exception as e:
        return False, f"LLM调用失败: {e}"

    # 判断：答案中是否包含所有关键事实
    answer_lower = answer.lower()
    hits_count = sum(1 for f in facts if f.lower() in answer_lower)
    passed = hits_count >= len(facts) * 0.5  # 至少命中一半事实即通过

    return passed, answer[:200]


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

    # 加载 BM25 索引
    bm25_index = None
    if mode in ('both', 'hybrid', 'qa'):
        try:
            with open(BM25_INDEX, 'rb') as f:
                bm25_index = pickle.load(f)
            print(f"  BM25 索引: {bm25_index['doc_count']} docs")
        except Exception as e:
            print(f"  BM25 索引: 加载失败 ({e})")

    results_p1 = []
    results_p2 = []
    results_hybrid = []
    results_qa = []

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

        if mode in ('both', 'hybrid', 'qa') and bm25_index:
            hits_h = search_hybrid(client, model, query, top_k=5, bm25_index=bm25_index)
            recall_h, chunk_h = evaluate(hits_h, expected, exp_chunk)
            results_hybrid.append({'recall': recall_h, 'chunk_hit': chunk_h})
            h_files = [h['file'][-40:] for h in hits_h[:3]]
            print(f"  Hybrid:  recall={recall_h:.0%} chunk={'Y' if chunk_h else 'N'} | {h_files}")

            # QA 评测
            if mode in ('qa',) and bq.get('qa_question') and bq.get('qa_facts'):
                passed, answer = qa_evaluate(hits_h, bq['qa_question'], bq['qa_facts'])
                results_qa.append({'passed': passed, 'answer': answer})
                print(f"  QA:      {'✅ PASS' if passed else '❌ FAIL'} | {answer[:80]}")

    # 汇总
    print(f"\n{'='*80}")
    print(f"BENCHMARK SUMMARY")
    print(f"{'='*80}")

    summary = {}

    if results_p1:
        avg_recall_p1 = sum(r['recall'] for r in results_p1) / len(results_p1)
        chunk_rate_p1 = sum(1 for r in results_p1 if r['chunk_hit']) / len(results_p1)
        print(f"Phase 1 (summaries only):")
        print(f"  Avg Recall@5:    {avg_recall_p1:.1%}")
        print(f"  Chunk Hit Rate:  {chunk_rate_p1:.1%}")
        summary['phase1'] = {'avg_recall': avg_recall_p1, 'chunk_hit_rate': chunk_rate_p1}

    if results_p2:
        avg_recall_p2 = sum(r['recall'] for r in results_p2) / len(results_p2)
        chunk_rate_p2 = sum(1 for r in results_p2 if r['chunk_hit']) / len(results_p2)
        print(f"Phase 1+2 (merge ranking):")
        print(f"  Avg Recall@5:    {avg_recall_p2:.1%}")
        print(f"  Chunk Hit Rate:  {chunk_rate_p2:.1%}")
        summary['phase2'] = {'avg_recall': avg_recall_p2, 'chunk_hit_rate': chunk_rate_p2}

    if results_hybrid:
        avg_recall_h = sum(r['recall'] for r in results_hybrid) / len(results_hybrid)
        chunk_rate_h = sum(1 for r in results_hybrid if r['chunk_hit']) / len(results_hybrid)
        print(f"Phase 3 Hybrid (vector + BM25 + RRF):")
        print(f"  Avg Recall@5:    {avg_recall_h:.1%}")
        print(f"  Chunk Hit Rate:  {chunk_rate_h:.1%}")
        summary['hybrid'] = {'avg_recall': avg_recall_h, 'chunk_hit_rate': chunk_rate_h}

    if results_qa:
        qa_pass_rate = sum(1 for r in results_qa if r['passed']) / len(results_qa)
        print(f"QA Evaluation (LLM judge):")
        print(f"  Pass Rate:       {qa_pass_rate:.1%} ({sum(1 for r in results_qa if r['passed'])}/{len(results_qa)})")
        summary['qa'] = {'pass_rate': qa_pass_rate, 'total': len(results_qa)}

    if results_p2 and results_hybrid:
        delta_recall = avg_recall_h - avg_recall_p2
        delta_chunk = chunk_rate_h - chunk_rate_p2
        print(f"\nDelta (Hybrid vs Phase 2):")
        print(f"  Recall:     {delta_recall:+.1%}")
        print(f"  Chunk Hit:  {delta_chunk:+.1%}")

    # 保存结果
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'queries': len(BENCHMARK_QUERIES),
        **summary,
    }
    report_file = LOG_DIR / f"benchmark_{time.strftime('%Y%m%d_%H%M%S')}.json"
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\n结果已保存: {report_file}")


def main():
    parser = argparse.ArgumentParser(description='Loki Search Benchmark')
    parser.add_argument('--phase1', action='store_true', help='只测 Phase 1')
    parser.add_argument('--phase2', action='store_true', help='只测 Phase 1+2')
    parser.add_argument('--hybrid', action='store_true', help='只测 Hybrid')
    parser.add_argument('--qa', action='store_true', help='QA 评测（Hybrid + LLM judge）')
    args = parser.parse_args()

    if args.phase1:
        mode = 'phase1'
    elif args.phase2:
        mode = 'phase2'
    elif args.hybrid:
        mode = 'hybrid'
    elif args.qa:
        mode = 'qa'
    else:
        mode = 'both'

    run_benchmark(mode)


if __name__ == '__main__':
    main()
