# 交接文档
更新时间: 2026-04-15 00:10

## 本轮共识
- Phase 3 Hybrid Search 全量落地：BM25 + BGE-M3 向量 + RRF(k=60) 融合
- 代码文件(.py/.sh/.yaml/.yml)纳入 Loki 索引，覆盖范围从文档扩展到代码
- Benchmark 从文件名匹配升级为 QA 评测（LLM judge），QA Pass Rate 100%
- 去重策略升级为 basename 去重，消除同文件跨 collection 重复占 slot
- P1 铁律强化：每个变更必须有对应单元测试，先测试后提交

## 本轮完成
- [x] Git 初始化（.gitignore + 235 文件首次提交）
- [x] Phase 3 Hybrid Search 全 5 步（词典/BM25索引/MCP集成/CLI/Benchmark）
- [x] BM25 rebuild 集成到 pipeline 自动流程
- [x] Benchmark QA 评测模式（--qa），QA Pass Rate 100%
- [x] 代码文件入库（+1874 个 .py/.sh/.yaml），文档库 7309→10463
- [x] Benchmark ground truth 修正适配实际索引
- [x] RRF 去重改用 basename，top5 信息密度提升
- [x] Loki 守护进程修复（Python 路径 + MySQL 密码 fallback）
- [x] Loki 每轮 macOS 通知（文档数/DDL数/入库批次）
- [x] MySQL 密码硬编码 → 环境变量 + ~/.secrets.env fallback
- [x] CLAUDE.md MySQL 连接指引
- [x] 单元测试 49 个全绿（BM25/MCP server/pipeline/benchmark）

## 待办
- [ ] 重启 Claude Code 让 MCP server 实际用上 hybrid search
- [ ] DDL 权重过高 / 备份表过滤 — 搜索结果被 _backup_ 表污染
- [ ] 代码文件 chunk — 大 .py 文件截断 2000 字，关键逻辑丢失
- [ ] MCP server 权重重新评估（当前 summaries 0.5/chunks 0.3/ddl 0.5）
- [ ] 15个商户画像标签中文名从 tag_catalog 确认
- [ ] v_merchant_profile_latest_di miss 分析
- [ ] mysql-mcp-server P1: 敏感表脱敏、NL2SQL 上下文自动从 DDL 向量库拉取
- [ ] mysql-mcp-server P2: HTTP SSE 模式

## 难点与风险
- BM25 索引 193MB pickle，MCP server 首次搜索延迟 ~2s
- basename 去重可能误合并同名但不同内容的文件（概率低）
- QA 评测依赖 ollama qwen2.5:7b，跑 benchmark 前需手动拉起

## 快速恢复指引
读这个文件 + CLAUDE.md（MySQL 连接）+ 以下文件即可接手：
- `code/rag-mcp-server/server.py` — Hybrid Search 实现
- `code/scripts/loki_bm25_index.py` — BM25 索引构建器
- `code/scripts/loki_userdict.txt` — jieba 自定义词典
- `code/scripts/loki_pipeline.py` — 流水线（含 BM25 auto rebuild）
- `code/scripts/loki_watchdog.sh` — 守护进程（含 macOS 通知）
- `code/scripts/loki_search.py` — CLI 搜索（hybrid/vector/bm25）
- `code/scripts/loki_benchmark.py` — Benchmark（三路对比 + QA 评测）
- `code/scripts/tests/` — 49 个单元测试
- `code/scripts/DESIGN_phase3_hybrid_search.md` — Phase 3 设计方案
