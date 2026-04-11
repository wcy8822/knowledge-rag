# 交接文档
更新时间: 2026-04-11 11:35

## 本轮共识
- Phase 3 Hybrid Search 方案确定并落地：BM25(rank_bm25) + BGE-M3 向量 + RRF(k=60) 融合
- BM25 精确匹配私有术语（橙化率、搁浅、S1S2 等），向量搜索捕获语义，RRF 融合两路
- Benchmark Chunk Hit Rate +10%（40%→50%），私有术语召回显著改善
- 项目已 git 初始化，7 个 commit 干净历史

## 本轮完成
- [x] Git 初始化（.gitignore + 235 文件首次提交）
- [x] Phase 3a: jieba 自定义词典 `code/scripts/loki_userdict.txt`（60+ 术语）
- [x] Phase 3a: BM25 索引构建 `code/scripts/loki_bm25_index.py`（45893 条，1.9s 构建，184MB pickle）
- [x] Phase 3b: MCP server hybrid search `code/rag-mcp-server/server.py`（向量+BM25+RRF）
- [x] Phase 3b: loki_search CLI 三模式 `code/scripts/loki_search.py`（hybrid/vector/bm25）
- [x] Phase 3c: benchmark hybrid 对比 `code/scripts/loki_benchmark.py`
- [x] BM25 rebuild 集成到 loki_pipeline.py 自动流程
- [x] MySQL 密码硬编码 → 环境变量
- [x] Benchmark QA 评测模式（--qa），QA Pass Rate 80%（16/20）
- [x] `ollama stop qwen2.5:7b` 释放内存
- [x] `launchctl load` 恢复 loki pipeline（PID 46371 运行中）

## 待办
- [ ] 重启 MCP server 让 Claude Code 实际用上 hybrid search（重启 claude code 即可）
- [ ] MCP server 权重重新评估：当前 summaries 0.5/chunks 0.3/ddl 0.5，hybrid 上线后可能需要调整
- [ ] QA benchmark 4 个 FAIL case 优化（橙化率公式缺失、ALPHA、1388、LLM幻觉 8192）
- [ ] 15个商户画像标签中文名从 tag_catalog 确认
- [ ] v_merchant_profile_latest_di miss 分析
- [ ] mysql-mcp-server P1: 敏感表脱敏、NL2SQL 上下文自动从 DDL 向量库拉取
- [ ] mysql-mcp-server P2: HTTP SSE 模式

## 难点与风险
- BM25 索引 184MB pickle，启动加载约 2s，MCP server 首次搜索会有延迟
- pipeline 新增文档后 BM25 索引需 rebuild，目前未自动化
- benchmark 的 recall 指标仍然基于文件名模糊匹配，不能真实反映搜索质量

## 快速恢复指引
读这个文件 + 以下文件即可接手：
- `code/rag-mcp-server/server.py` — Hybrid Search 实现（_vector_search + _search_bm25 + _rrf_merge）
- `code/scripts/loki_bm25_index.py` — BM25 索引构建器
- `code/scripts/loki_userdict.txt` — jieba 自定义词典
- `code/scripts/loki_search.py` — CLI 搜索工具（三模式）
- `code/scripts/loki_benchmark.py` — Benchmark（三路对比）
- `code/scripts/logs/bm25_index.pkl` — BM25 索引（184MB，不入 git）
- `code/scripts/DESIGN_phase3_hybrid_search.md` — Phase 3 设计方案
