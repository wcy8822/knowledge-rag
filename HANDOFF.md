# 交接文档
更新时间: 2026-04-11 09:27

## 本轮共识
- Loki 搜索结果给 AI 消费，不给人直接看
- Benchmark 应测"AI 能否答对问题"（QA评测），而非召回文件名（检索评测）
- 权重调整（summaries/chunks）对内部术语失效无效，根本问题是向量搜索天然不支持私有词汇
- 长期方案：Hybrid Search = BGE-M3 向量 + BM25 关键词，RRF 融合，这才是解决"橙化率"类内部黑话召回的正道

## 本轮完成
- Loki Phase 2 **全部完成**：649/649 文件，38035 chunks，耗时 555 分钟，零失败（2026-04-11 01:14）
- 跑 Benchmark（summaries 0.3/chunks 0.7）：Phase1 38.3% vs Phase1+2 34.2%，-4.2%
- 调整权重（summaries 0.5/chunks 0.3）重跑：Phase1+2 回升至 37.5%，-0.8%
- 发现 Benchmark 评测方式本身有问题（测文件召回而非问题回答），决策：改回 0.3/0.7 并搁置当前 benchmark
- 诊断"橙化率"搜索 miss 根因：不是覆盖率/权重问题，是 BGE-M3 对私有术语无向量表示
- 设计 Phase 3 Hybrid Search 方案（BM25 + 向量 + RRF）

## 待办
- [ ] `ollama stop qwen2.5:7b` 释放 800MB（chunk 已完成，qwen 不再需要）
- [ ] `launchctl load ~/Library/LaunchAgents/com.didi.loki.plist` 恢复 pipeline
- [ ] **Phase 3a**：构建 BM25 索引（rank_bm25，对 38035 chunks 建倒排，持久化）
- [ ] **Phase 3b**：MCP server search_knowledge 升级为 Hybrid Search（向量 + BM25 + RRF）
- [ ] **Phase 3c**：Benchmark 改造为 QA 评测（给 AI 返回结果，问 AI 能否答对）
- [ ] MCP server 权重确认：当前已改为 summaries 0.5 / chunks 0.3，待 Hybrid 上线后重新评估
- [ ] 15个商户画像标签中文名从 tag_catalog 确认
- [ ] v_merchant_profile_latest_di miss 分析
- [ ] mysql-mcp-server P1: 敏感表脱敏、NL2SQL 上下文自动从 DDL 向量库拉取
- [ ] mysql-mcp-server P2: HTTP SSE 模式

## 难点与风险
- BM25 索引 38035 条，启动加载约 1-2s，可接受；但每次 pipeline 新增文档需增量更新索引
- Benchmark QA 评测需要调 qwen/claude 判断答案，成本高，设计测试集要精简
- MCP server 当前权重 summaries 0.5/chunks 0.3，与 Hybrid 上线前可能不是最优解

## 快速恢复指引
读这个文件 + 以下文件即可接手：
- `code/rag-mcp-server/server.py` — 当前权重 summaries 0.5 / chunks 0.3 / ddl 0.5
- `code/scripts/loki_benchmark.py` — 当前权重同上，待 Phase 3 后改造为 QA 评测
- `code/scripts/logs/benchmark_20260411_091959.json` — 最新 benchmark 结果
- Phase 3 设计：BM25（rank_bm25）+ BGE-M3 + RRF(k=60)，在 search_knowledge 里并联
