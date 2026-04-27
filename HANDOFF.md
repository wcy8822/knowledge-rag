# 交接文档
更新时间: 2026-04-27 10:30

## 本轮共识

第一性原理大重构 — 高质量向量化知识库还差三件，本会话治本前两件：

1. **准入闸**（白名单+强黑名单）→ 拦住 site-packages / .venv / 第三方库
2. **fingerprint v3**（content hash 替代 mtime hash）→ 内容不变不重 embed
3. ~~质量反馈~~ → 留下次（已埋点 queries.jsonl，等数据）

最大收益：清退 53,087 条噪音 + DDL 剥离独立 tool，**Recall@5 维持 57.5%**
（在 chroma 从 62K 缩到 9.3K 的清洁状态下）。pipeline 速度 50× 提升。

## 本轮完成（3 治本 commit + 1 收工）

- [x] **准入闸 e8932ab**：site-packages/.venv/python-sdk 等强黑名单
- [x] **53K 噪声清退**：summaries 62,317→9,309；chunks 38,035→37,956；state.docs 59,054→6,067
- [x] **DDL 剥离 9fd6eed**：search_ddl 独立 tool；search_knowledge 不再含 DDL；Recall@5 27.5%→57.5%
- [x] **fingerprint v3 6a22b52**：content_fingerprint(path, content) + StateV2.is_doc_done(*fps) 兼容判定
- [x] pipeline 跑补漏（M 进行中，预计 30 分钟完成）：1.6 文件/秒，2,883 待补
- [x] 单测 218 → **233**（+15：is_doc_done multi-fp + content_fingerprint）
- [x] OB 笔记 [[202604271030+会话纪要-Loki第一性原理大重构]]

## 待办

- [ ] **重启 Claude Desktop** 让 search_ddl 新 tool 注册生效（已加 tools/list）
- [ ] **chroma 按 path 去重 GC 工具**：v3 切换后旧 mtime_fp id 与新 content_fp id 共存，需要保留最新 content_fp
- [ ] 等今天 launchd 02:00 跑完看 BM25 cache 命中率（v3 后 fp 不同会缺命中，需要 sigs 也按 content）
- [ ] 质量反馈第三件：cold files 自动清退 / hot files 加权 / zero-hit 提示补文档
- [ ] 商户标签 15 个中文名从 tag_catalog 确认
- [ ] 检查 server_http.py 是否需要同步 KNOWLEDGE_COLLECTIONS / DDL_COLLECTIONS

## 难点与风险

- **fingerprint v3 副作用**：旧 chroma 中 mtime_fp 的 id 与新 content_fp id 不同，按 path 会出现新旧两份。state.docs 端会自然只保留新值（dict 覆盖），但 chroma 端需要 GC 工具按 path 去重。
- **search_knowledge 现在不含 DDL**：如果 LLM 不主动调 search_ddl，DDL 召回为零。需要观察 queries.jsonl 看 LLM 是否会用 search_ddl。
- **BM25 索引仍含 DDL**：BM25 重建后 cache hit 率会因 fp 变化大幅下降（首次跑后恢复）
- **launchd 凌晨 02:00**：今晚跑会触发 v3 二次判定，但旧 chroma id 仍残留，召回结果可能短期混乱
- **content_fingerprint 读所有文件 IO**：相比 mtime_fp 多读所有文件，但准入闸后只剩 10K 文件，IO 开销可控

## 快速恢复指引

```bash
# 1. 全套测试（233 应全绿）
~/mlx-env/bin/python -m pytest /Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/tests/ -q

# 2. 验证 DDL 剥离效果
~/mlx-env/bin/python /Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/loki_benchmark.py --phase2 --weights 'summaries=0.5,chunks=0.4,ddl=0.0'
# 预期 Recall@5 = 57.5%

# 3. dry-run 准入清退（应显示 0 待清，因为已清完）
~/mlx-env/bin/python /Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/loki_scan_cleanup.py --dry-run

# 4. 状态自检
launchctl list | grep -E "loki|gemma|ollama"
~/mlx-env/bin/python -c "
import chromadb, json
c = chromadb.PersistentClient(path='/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge')
for n in ['doc_knowledge_bge_m3','doc_knowledge_chunks','ddl_schema_bge_m3']:
    print(n, c.get_collection(n).count())
s = json.loads(open('/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs/loki_state.json').read())
print(f'state docs={len(s[\"docs\"])} ddl={len(s[\"ddl\"])}')
"

# 5. 看 query 日志（重启后真实数据）
cat /Users/didi/Work/projects/knowledge-rag-知识库/logs/queries.jsonl | tail
```

关键文件位置（本会话新增）：

```
# 准入闸
code/scripts/loki_scan_filter.py        # is_excluded_path 强黑名单
code/scripts/loki_scan_cleanup.py       # 一次性清退 chroma 脏数据
code/scripts/tests/test_scan_filter.py  # 24 单测

# DDL 剥离
code/rag-mcp-server/server.py           # KNOWLEDGE_COLLECTIONS / DDL_COLLECTIONS
                                          # search_ddl tool 注册

# fingerprint v3
code/scripts/loki_pipeline.py           # content_fingerprint + 二阶段判定
code/scripts/loki_state.py              # is_doc_done(*fps) 多 fp 兼容
code/scripts/tests/test_pipeline.py     # +8 content_fingerprint 测试
code/scripts/tests/test_loki_state.py   # +7 multi-fp 测试

# 备份产物
logs/loki_scan_cleanup.summaries.20260427100327.jsonl  # 53,008 条
logs/loki_scan_cleanup.chunks.20260427100327.jsonl     # 79 条
```

## 累积数据快照（截止 2026-04-27 10:30）

- chroma summaries: **9,309**（治理前 62,317）
- chroma chunks: **37,956**（治理前 38,035）
- chroma ddl: **484**
- state.docs: **6,067** + 当前 pipeline 跑完后 → 约 **10,000**
- 单测: **233 全绿**
- benchmark Recall@5: **57.5%**
