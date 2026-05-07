# 交接文档
更新时间: 2026-05-07 11:00

## 本轮共识

1. **API 误用比逻辑 bug 更阴险**：`pool.imap()` 在编辑器没 lint 错，单测又没真实跑过并行管道（被 mock 掉），5-7 00:54 commit 当夜过 5 小时直接生产事故 — 回归测试必须有"源码静态扫描"防御
2. **一次性事件用一次性方案，长期问题用长期方案**：chunks 9496 全量 backfill 是历史欠债（手动跑一次），daily 增量 50-200 是稳态（max-files 限流），不混在一起跑就不会撞 wrapper 90 分钟上限
3. **fact-forcing gate 是好护栏**：每次 Edit/Write 前必须列引用方/影响符号/数据 schema/用户原话 4 项事实

## 本轮完成

5-7 凌晨 02:00 launchd 整夜 crash 定位 + 双修复 + chunks 限流 + 一次性 backfill。详见 [[202605071100+会话纪要-Loki并行IO修复+chunks限流防超时]]

- ✅ **修 ThreadPool API 误用** [`0806124`](https://github.com/wcy8822/knowledge-rag/commit/0806124)：`pool.imap` → `pool.map` 两处 + 3 回归单测（已 push）
- ✅ **chunks 限流** [`b7d47c9`](https://github.com/wcy8822/knowledge-rag/commit/b7d47c9)：`run_chunks` 加 `max_files` 参数 + 3 回归单测（已 push）
- ✅ **一次性 backfill 后台跑**：chunk 库 37956 → 77172（截止 10:55，预计 11:30 跑完到 ~85000）
- ✅ **全量 pytest 269 → 292 全绿**

## 待办

- [ ] **明早查 logs/loki_20260508_*.log** 确认今晚 02:00 launchd 第一次跑新代码稳定
- [ ] **SSH 反向隧道**：`ssh -R 18000:localhost:8000 user@154.193.243.169 -N`
- [ ] **launchd 常驻 server_http**：写 `com.local.loki-http.plist`
- [ ] **Open WebUI 配置**：SG 上配 OpenAI API → `http://localhost:18000/v1`
- [ ] **MLX LLM 链路确认**：检查 ollama-adapter 是否正常
- [ ] **chroma 按 path 去重 GC**（5-5 遗留）
- [ ] **质量反馈闭环**（5-5 遗留）：cold files 自动清退 / hot files 加权

## 难点与风险

- **backfill 进程未结束**：PID 51309 后台跑（截止 10:55 已 1h20min），如果 11:30 前 chunk 库不再涨 → `kill -TERM 51309` 软停，已入库不丢
- **今晚 02:00 launchd 验证窗口**：明早第一件事查 wrapper log 确认无 crash
- **MLX 推理服务 (:3003) 仍未确认运行状态**（5-5 遗留）

## 快速恢复指引

```bash
# 1. 看 backfill 进度
tail -3 code/scripts/logs/loki_20260507_093543.log
ps -o pid,etime,rss,%cpu -p 51309 2>/dev/null

# 2. 启动 OpenAI 兼容 API
~/mlx-env/bin/python code/rag-mcp-server/server_http.py --host 0.0.0.0 --port 8000

# 3. 全量测试（292 应全绿）
~/mlx-env/bin/python -m pytest code/scripts/tests/ -q

# 4. 健康检查
~/mlx-env/bin/python code/scripts/loki_health.py

# 5. 应急三档（盯 backfill 用）
kill -TERM 51309    # 软停（推荐）
kill -9 51309       # 硬停（软停不响应）
ls vectors/data/chroma-*/chroma.lock 2>/dev/null  # 检查残留锁
```

## 关键文件位置（本会话新增）

```
# 修复点
code/scripts/loki_pipeline.py:232,459       # 并行 I/O pool.map (修 imap 误用)
code/scripts/loki_pipeline.py:436           # run_chunks(..., max_files=None)
code/scripts/loki_pipeline.py:472           # chunks max-files 截断

# 回归单测
code/scripts/tests/test_pipeline.py:248-321 # TestParallelIOPipeline + TestChunksMaxFilesLimit (6)

# OB 纪要
Inbox/202605071100+会话纪要-Loki并行IO修复+chunks限流防超时.md
```

## 累积数据快照（截止 2026-05-07 11:00）

- chroma summaries: ~11,030
- chroma chunks: **跑后预计 ~85,000**（5-5 是 37,956，本会话 backfill 全量补完）
- chroma ddl: 511
- state.docs: 7,656
- 单测: **292 全绿**（5-5 是 269）
- GitHub: [wcy8822/knowledge-rag](https://github.com/wcy8822/knowledge-rag) 48 commits（5-5 是 46）
- launchd: `com.didi.loki` 每天 02:00 跑 `wrapper.sh all --max-files 1500`，wrapper 18GB RSS + 90 分钟 CPU 上限
