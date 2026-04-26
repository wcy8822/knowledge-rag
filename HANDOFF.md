# 交接文档
更新时间: 2026-04-26 17:40

## 本轮共识
- β：Loki ↔ Claude 反馈闭环 Phase 1+2 全量落地
- MCP 调用全埋点（search_knowledge / ask_knowledge / nl2sql），写 logs/queries.jsonl
- 周日 09:00 launchd 自动跑 analyzer，输出周报到 OB Inbox
- python-docx 装入 ~/mlx-env，docx 解析回归
- fingerprint 152K vs 库容 63K 差额追溯完成（94K 残留 + 4.3K 持久化漏写）

## 本轮完成
- [x] Phase 1: query_logger.py + server.py 三分支埋点 + 15 个单测
- [x] Phase 2: loki_query_analyzer.py + 20 个单测 + launchd plist 安装并加载
- [x] 端到端验证：周报已写入 OB Inbox（202604261725+Loki周报-反馈闭环.md）
- [x] python-docx 装入 ~/mlx-env，4/23 日志的 docx 解析失败问题闭环
- [x] fingerprint 差额根因诊断（OB: 202604261735+Loki-fingerprint差额追溯.md）
- [x] 提交 2 个原子 commit：641eccd (Phase 1) / 102a373 (Phase 2)

## 待办
- [ ] **重启 Claude Desktop** 让新 server.py 生效，开始积累真实 query 数据
- [ ] 一周后看首份真实周报，决定是否做闭环回写（零结果 → 自动重 embed）
- [ ] Loki state.json 治理（中优先级）：
  - 一次性清洗：剔除 94K 残留 + 补 4,269 条已入库未登记
  - 长期：state 从 set[fingerprint] 改为 dict[path → {mtime, fingerprint}]
  - 修复 loki_pipeline.py:215 持久化漏写
- [ ] 4/25 异常追溯（51 文件 280 分钟，BM25 之后日志缺失）
- [ ] 历史遗留：DDL 权重过高 / 备份表过滤 / 代码文件 chunk 截断 / 商户标签中文名

## 难点与风险
- 反馈闭环 MVP 是**只采集不回写**：周报供人决策，不要让 analyzer 自动改 ChromaDB
- query_logger 写入失败已吞噬，不会阻塞 MCP；但 logs/queries.jsonl 单调增长，未来要加滚动
- launchd 周日 09:00 触发依赖 ~/mlx-env，若 venv 损坏需手动 reload
- fingerprint 治理涉及多文件改动，按 P1 拆分谨慎做

## 快速恢复指引
```bash
# 验证 Phase 1+2
~/mlx-env/bin/python -m pytest /Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/tests/ -q

# 查看 query 日志（待 Claude Desktop 重启后才会有数据）
cat /Users/didi/Work/projects/knowledge-rag-知识库/logs/queries.jsonl | tail

# 手动跑一次 analyzer（dry-run 不写文件）
~/mlx-env/bin/python /Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/loki_query_analyzer.py --dry-run --no-cold

# 查看 launchd 状态
launchctl list | grep -E "loki|gemma|ollama"
```

关键文件位置：
- `code/rag-mcp-server/{server.py,query_logger.py}` — Phase 1 埋点
- `code/scripts/loki_query_analyzer.py` — Phase 2 周报
- `code/scripts/launchd/com.local.loki-query-analyzer.plist` — 版本化副本
- `~/Library/LaunchAgents/com.local.loki-query-analyzer.plist` — 系统加载位
- `code/scripts/tests/{test_query_logger.py,test_query_analyzer.py}` — 35 个单测
- `logs/queries.jsonl` — Phase 1 写入目标（待 Claude Desktop 重启后开始有数据）

延续上轮的 Hybrid Search / MySQL / 单测体系不变，详见 git log 与 CLAUDE.md。
