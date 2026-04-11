# Phase 3: Hybrid Search 设计方案

## 问题

BGE-M3 向量搜索对私有术语（橙化率、搁浅、S1/S2）无向量表示，语义搜索天然 miss。
权重调整无法解决根因——向量空间里根本没有这些词的语义锚点。

## 方案

**BM25 关键词搜索 + BGE-M3 向量搜索 + RRF 融合排序**

BM25 精确匹配关键词（包括私有术语），向量搜索捕获语义相似，RRF 融合两路结果。

## 架构

```
query
  ├─→ BGE-M3 encode → ChromaDB cosine search → vector_hits
  ├─→ jieba 分词 → BM25 index search → bm25_hits
  └─→ RRF(vector_hits, bm25_hits, k=60) → final_ranked
```

## 关键设计

### 1. BM25 索引

- **库**: `rank_bm25` (pip install rank_bm25)
- **分词**: `jieba`（中文分词，停用词过滤）
- **索引范围**: 3 个 collection 的全部文档（summaries + chunks + ddl）
- **数据结构**: 
  - `corpus`: list[str] — 每条文档的原始文本
  - `doc_ids`: list[str] — 对应的 doc_id
  - `doc_meta`: list[dict] — 对应的 metadata（source_file, collection 来源等）
  - `bm25`: BM25Okapi 实例
- **持久化**: pickle 序列化到 `logs/bm25_index.pkl`
- **启动加载**: MCP server 启动时 load pickle（预计 1-2s）
- **增量更新**: pipeline 跑完后触发 rebuild（全量重建，38k 条 < 10s）

### 2. RRF 融合

```python
def rrf_merge(vector_hits, bm25_hits, k=60, top_n=5):
    """Reciprocal Rank Fusion"""
    scores = {}  # file_key -> rrf_score
    
    for rank, hit in enumerate(vector_hits):
        key = hit['file']
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
    
    for rank, hit in enumerate(bm25_hits):
        key = hit['file']
        scores[key] = scores.get(key, 0) + 1.0 / (k + rank + 1)
    
    # 按 rrf_score 降序，取 top_n
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_n]
```

- k=60 是 RRF 的标准参数，压制排名靠后的长尾
- 两路各取 top 20 做融合，最终返回 top 5

### 3. MCP server 改造

`search_knowledge()` 函数改造：
1. 原有向量搜索逻辑不变，取 top 20
2. 新增 BM25 搜索，取 top 20
3. RRF 融合，取 top n
4. 用融合后的 file_key 回查原始 doc/meta 填充返回结构

### 4. BM25 索引构建脚本

新文件: `code/scripts/loki_bm25_index.py`
- 从 ChromaDB 读取 3 个 collection 的全部文档
- jieba 分词 + 停用词过滤
- 构建 BM25Okapi 索引
- pickle 持久化
- 可独立运行，也可被 pipeline 调用

## 不做的事

- **不做 Elasticsearch/MeiliSearch** — 杀鸡不用牛刀，rank_bm25 内存索引够用
- **不做分词模型微调** — jieba 默认词典 + 用户自定义词典覆盖私有术语
- **不做向量模型微调** — 成本太高，BM25 补位即可
- **不做实时索引更新** — 全量 rebuild 足够快（<10s）

## 自定义词典

`code/scripts/loki_userdict.txt`（jieba 自定义词典格式）：
```
橙化率 5 n
搁浅 5 n
双轮驱动 5 n
随手购 5 n
S1S2 5 n
兜底值 5 n
宽表 5 n
```
确保这些私有术语不被 jieba 切碎。

## 小需求拆分

| # | 需求 | 输入 | 输出 | 可独立测试 |
|---|------|------|------|-----------|
| 1 | 创建 jieba 自定义词典 | 业务术语列表 | `loki_userdict.txt` | jieba 分词验证 |
| 2 | BM25 索引构建脚本 | ChromaDB 3 collections | `bm25_index.pkl` | 加载+搜索"橙化率"命中 |
| 3 | MCP server 集成 BM25+RRF | server.py | hybrid search 生效 | loki_search.py 验证 |
| 4 | loki_search.py 适配 hybrid | search CLI | 显示 BM25/向量/融合来源 | CLI 搜索验证 |
| 5 | benchmark 跑 hybrid 对比 | benchmark.py | 对比报告 | recall 对比 Phase 2 |

每个需求独立提交。
