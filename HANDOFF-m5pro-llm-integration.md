# 交接文档
更新时间: 2026-04-26 17:03

## 当前架构（已稳定运行 5 天）

```
Obsidian / 项目文档 / DDL
        ↓ (凌晨 02:00 launchd 触发)
loki_pipeline.py
   扫描 → BGE-M3 embed → Qwen3-14B 摘要 → ChromaDB 入库
        ↓
ChromaDB（62,998 文档摘要 + 38,035 chunks + 605 DDL = 101,638 向量）
        ↓
Claude Desktop（按需调）
   MCP loki-rag （11 个 tool）
        ↓
ollama-adapter (:11434) → mlx_lm.server (:3003) → Qwen3-14B
   按需唤醒（冷启 6.4s）+ 闲置 20 分钟自动卸载（释放 10GB）
```

## 模型选型定论（M5 Pro 24GB）

| 用途 | 模型 | 大小 | 命令 |
|---|---|---|---|
| Loki 中文 RAG / 摘要 主力 | **Qwen3-14B 4bit** | 8GB | `llm-switch qwen3-14b`（当前 active） |
| 轻量 / 兜底 | Qwen3-8B 4bit | 5GB | `llm-switch qwen3-8b` |
| 视觉（未来 OCR） | Gemma 4 E4B 4bit | 4.9GB | `llm-switch e4b` |
| ~~Gemma 4 26B A4B~~ | 已删除 | — | 中文不达标，需要重下：`llm-download mlx-community/gemma-4-26b-a4b-it-4bit --name 26b` |

## 已完成（按里程碑）

- [x] MLX 推理栈：mlx 0.31.2 + venv `~/mlx-env`，软链 `~/models/active` + 登记册 `~/.models/registry.json` + 切换工具 `~/bin/llm-{health,switch,download}`
- [x] launchd 自启 `com.local.gemma-mlx`（按需 `RunAtLoad=false`），GPU wired 永久 20480MB（LaunchDaemon `com.local.gpu-wired-limit`）
- [x] HF 镜像 `HF_ENDPOINT=https://hf-mirror.com`（避 429）+ ASCII 软链 `~/Work/projects/loki-kb` 防 Electron 中文路径问题
- [x] Ollama 协议适配器 `~/bin/ollama-adapter.py`：监听 11434 → 转发 3003 OpenAI；按需唤醒（kickstart）+ 闲置 20 分钟 SIGTERM 卸载；伪造 `/api/tags` 通过 loki_health
- [x] Loki 接入：全套依赖装到 `~/mlx-env`（chromadb / sentence-transformers / modelscope / pymysql / jieba / rank_bm25 / openpyxl）；BGE-M3 走 modelscope 下到 `~/models/bge-m3`；ChromaDB 三库 10 万+ 向量
- [x] MCP server `loki-rag` 注册到 `~/Library/Application Support/Claude/claude_desktop_config.json`（Desktop 配置位，**不是 `~/.claude.json`**），暴露 11 个 tool
- [x] launchd `com.didi.loki` 每日 02:00 触发 `loki_pipeline`（增量稳态 < 1 分钟，44KB 日志）
- [x] launchd `com.local.loki-healthcheck` 每日 09:00 巡检（语义判据：日志含 `Loki 完成`），异常发 macOS 桌面通知
- [x] 2026-04-23 事故修复：`brew uninstall ollama` 彻底清掉会复活的 brew ollama
- [x] 2026-04-24 巡检脚本 bug 修复：①阈值改语义标志 ②glob 不写死秒数 ③装 openpyxl
- [x] 2026-04-26 搜索链路 bug 修复：`loki_search.py` + `rag-mcp-server/server.py` 的 `meta` / `doc` `NoneType` 防御

## 待办（核心遗留）

- [ ] **β：Loki ↔ Claude 反馈闭环**（用户已选但未做，下一会话首要任务）
  - **Phase 1**（2 小时）：MCP server 加 query 日志 → `~/Work/projects/knowledge-rag-知识库/logs/queries.jsonl`，字段 `ts/tool/query/n_requested/n_returned/top_files/latency_ms`
  - **Phase 2**（1 小时）：写 `loki_query_analyzer.py`，每周日 09:00 launchd 跑，输出报告到 OB 笔记（高频 query / 0 结果 / 慢查询 / 高命中文件 / 30 天零命中文件）
- [ ] 4/25 异常追溯：51 文件耗时 280 分钟，其中 4 小时不知道在干什么（DDL Part 2 卡 16 分钟，BM25 之后到尾部丢失），需要看 BM25 后日志
- [ ] docx 解析依赖：`~/mlx-env/bin/pip install python-docx`（4/23 日志显示 `No module named 'docx'`）
- [ ] fingerprint 152K vs 库容 63K 差额追溯（理论应一致，实际差 ~9 万，可能是中断遗留）

## 风险

1. **架构是开环**：Loki 不知道 Claude 实际怎么用它的结果（β 待办的根本原因）
2. **24GB 内存极限**：Qwen3-14B 占 10GB，加用户工作 App 紧张但稳；不要再加大模型
3. **brew ollama 不能再装**：会自动复活占 11434
4. **MCP 配置位置**：Claude **Desktop** 读 `~/Library/Application Support/Claude/claude_desktop_config.json`，**不是** `~/.claude.json`（CLI 用的）

## 快速恢复指引

```bash
# 1. 状态自检
llm-health                          # MLX 服务（按需架构下平时 stopped 是正常的）
launchctl list | grep -E "loki|gemma|ollama"

# 2. 触发一次 Loki 检索（验证全链路）
~/mlx-env/bin/python ~/Work/projects/knowledge-rag-知识库/code/scripts/loki_search.py "测试关键词" --top 3

# 3. 手动跑 pipeline（白天跑也可以，会拿写锁）
~/mlx-env/bin/python ~/Work/projects/knowledge-rag-知识库/code/scripts/loki_pipeline.py

# 4. 看最近巡检结果
cat /tmp/loki-healthcheck.out.log
```

关键文件位置（拷贝即用）：

```
~/Library/LaunchAgents/com.local.gemma-mlx.plist           # MLX 服务（按需）
~/Library/LaunchAgents/com.local.ollama-adapter.plist      # 11434→3003 适配（守护）
~/Library/LaunchAgents/com.didi.loki.plist                 # 凌晨 02:00 pipeline
~/Library/LaunchAgents/com.local.loki-healthcheck.plist    # 每日 09:00 巡检
/Library/LaunchDaemons/com.local.gpu-wired-limit.plist     # 开机 sysctl 20480
~/.models/registry.json                                    # 模型登记册
~/models/active                                            # 软链 → qwen3-14b
~/Library/Application Support/Claude/claude_desktop_config.json  # Claude Desktop MCP
~/bin/{llm-health,llm-switch,llm-download,loki-daily-health.py,ollama-adapter.py}
~/Work/projects/knowledge-rag-知识库/                       # Loki 项目
~/Work/projects/loki-kb/                                   # 上面的 ASCII 软链
~/mlx-env/                                                 # Python 3.12 venv (本机 AI 唯一)
```
