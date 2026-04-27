# 交接文档
更新时间: 2026-04-27 09:32

## 本轮共识

跨多轮一次大治理 — Loki ↔ Claude 反馈闭环 MVP 上线，顺势打穿 fingerprint 单调增长 / chroma 脏数据 / DDL 噪音 / 代码截断 / BM25 188min 黑洞 / MCP 权重六个老问题。**最大单点收益：MCP Recall@5 +23pp（34.2% → 57.5%）**。

## 本轮完成（8 commit + 4 OB 诊断）

- [x] **β Phase 1**：MCP 三 tool 埋点 → `logs/queries.jsonl`（641eccd）
- [x] **β Phase 2**：周报 analyzer + launchd 周日 09:00（102a373）
- [x] python-docx 装入 ~/mlx-env，docx 解析回归
- [x] fingerprint 差额追溯（OB 202604261735）
- [x] **state cleanup**：152K → 63.6K（d220865）
- [x] **state v2**：set[fp] → dict[path→fp] 治本 + 自动迁移（e14a073）
- [x] **chroma GC**：清掉 1,537 条早期 doc_X/oil-algo/ddl_<table>（1bf091a）
- [x] **DDL 过滤**：is_excluded_table 入库前拦截 + 一次性清理 109 条（282d4d3）
- [x] **代码智能截断**：head 70% + tail 30%，保留 imports/main（eb6532f）
- [x] **BM25 计时点**修正暴露真实分布（36e0635）
- [x] **BM25 tokens 缓存**：稳态 188min → 秒级（bb9e949）
- [x] **MCP 权重重评估**：DDL 0.5 → 0.2，Recall +23pp（204507f）
- [x] 单测 49 → 194（+145，4 个新模块全覆盖）

## 待办

- [ ] **重启 Claude Desktop** 让 MCP server.py 加载新权重（生效门槛）
- [ ] 等 launchd 02:00 跑后看 BM25 cache 命中率 + 各阶段真实耗时
- [ ] 一周后看首份真实周报，决定反馈闭环是否做闭环回写
- [ ] 代码 chunk 完整方案（让 .py 进 chunks 集合）
- [ ] 商户标签 15 个中文名从 tag_catalog 确认
- [ ] Hybrid 模式 RRF k 调优（30 / 60 / 100 对比）
- [ ] DDL 单独 tool 剥离（search_ddl vs search_knowledge）让 LLM 显式选
- [ ] 16min DDL 黑洞（4/25 异常追溯遗留）：下次手动跑 pipeline 加 process trace 验证

## 难点与风险

- **新权重生效需重启 Claude Desktop**，否则 MCP 还是用老 server 实例
- **BM25 首跑无 cache（旧 pickle 无 doc_text_sigs 字段，安全降级为空）**，今晚 02:00 仍要 4 小时；从第二跑起命中
- **代码智能截断**仅对新增/改动文件生效（fingerprint 不变就不重处理），存量代码渐进迭代
- **chroma 中已删 1,525 条 doc_X**：下次 pipeline 跑会把对应文件按新 fp 重新入库，一次性增量大
- **mysql nl2sql 上下文**仍走老 nl2sql-context.md，未受本次治理影响
- 5 / 16 / 240 分钟异常的根因未百分百定位（mlx GC / 内存换出 / pymysql conn.close timeout 都可能）

## 快速恢复指引

```bash
# 1. 验证全栈
~/mlx-env/bin/python -m pytest /Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/tests/ -q

# 2. 看 query 日志（重启 Claude Desktop 后才有数据）
cat /Users/didi/Work/projects/knowledge-rag-知识库/logs/queries.jsonl | tail

# 3. 手动跑 analyzer 周报 (dry-run 不写)
~/mlx-env/bin/python /Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/loki_query_analyzer.py --dry-run --no-cold

# 4. 跑 benchmark 对比权重
~/mlx-env/bin/python /Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/loki_benchmark.py --phase2
~/mlx-env/bin/python /Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/loki_benchmark.py --phase2 --weights 'summaries=0.5,chunks=0.5,ddl=0.5'

# 5. 状态自检
launchctl list | grep -E "loki|gemma|ollama"
~/mlx-env/bin/python -c "
import chromadb, json
c = chromadb.PersistentClient(path='/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge')
for n in ['doc_knowledge_bge_m3','doc_knowledge_chunks','ddl_schema_bge_m3']:
    print(n, c.get_collection(n).count())
print('state ddl:', len(json.loads(open('/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs/loki_state.json').read())['ddl']))
"
```

关键文件位置：

```
# 反馈闭环
code/rag-mcp-server/{server.py,query_logger.py}    # Phase 1 埋点
code/scripts/loki_query_analyzer.py                # Phase 2 周报
code/scripts/launchd/com.local.loki-query-analyzer.plist
~/Library/LaunchAgents/com.local.loki-query-analyzer.plist  # 系统加载位

# state 治理
code/scripts/loki_state.py                # StateV2 dataclass
code/scripts/loki_state_cleanup.py        # 一次性清洗
code/scripts/loki_chroma_gc.py            # 早期 id 体系 GC
code/scripts/loki_ddl_filter.py           # 入库前过滤
code/scripts/loki_ddl_cleanup.py          # 备份表清洗

# 性能 + 质量
code/scripts/bm25_tokens_cache.py         # 增量缓存
code/scripts/loki_text_extract.py         # 代码智能截断
code/scripts/loki_pipeline.py             # 主流程已接入全部 ↑

# 数据驱动
code/scripts/loki_benchmark.py            # CLI --weights
logs/queries.jsonl                         # MCP 真实 query
logs/loki_state.json                       # v2 dict[path→fp]

# 备份
logs/loki_state.json.bak.20260426203700        # 治理前 v1 List
logs/loki_chroma_gc.{summaries,ddl}.<ts>.jsonl # GC 备份
logs/loki_ddl_cleanup.<ts>.jsonl                # DDL 清洗备份
```

## 累积数据快照（截止 2026-04-27 09:32）

- chroma summaries: **61,593**（治理前 63,118）
- chroma chunks: **38,035**（不动）
- chroma ddl: **484**（治理前 605）
- state.json v2: docs=**58,332**, ddl=**484**
- 单测: **194 全绿**
- benchmark Recall@5: **57.5%**（治理前 34.2%）
