# 交接文档
更新时间: 2026-05-05 22:30

## 本轮共识

1. **M5 本机 RAG 不传文件出机**：数据安全红线，SG 只能通过 HTTP API 调 RAG 结果，不传源文件
2. **仓库化到 GitHub**：代码和文档公开，关键数据（模型/向量/索引/日志）不入库
3. **按 P1 铁律执行**：备份→改→测试→提交，每步验证全量测试

## 本轮完成

- [x] **RAG 现状盘点**：完整 Markdown 报告 `M5-RAG现状盘点-OpenAI-API评估报告.md`
- [x] **OpenAI 兼容 API `2f256ce`**：`/v1/chat/completions` + `/v1/models`，双模型(loki-rag/loki-search)，streaming SSE
- [x] **补齐 tool `2f256ce`**：server_http.py 注册 search_ddl + search_by_fields
- [x] **CORS + 默认端口 `2f256ce`**：监听 0.0.0.0:8000，CORS 全开
- [x] **单元测试 `2f256ce`**：test_openai_api.py 13 tests（模型列表/对话/流式/多轮/错误处理）
- [x] **仓库化 `85c3644`**：GitHub wcy8822/knowledge-rag，排除模型/向量/索引/日志/状态文件
- [x] **README 更新 `c2a9f98`**：架构图 + MCP/OpenAI API 说明 + 快速启动
- [x] **安装 fastapi `mlx-env`**：uvicorn 已有，补装 fastapi 0.136.1
- [x] 单测 256 → **269**（+13），全绿

## 待办

- [ ] **SSH 反向隧道**：`ssh -R 18000:localhost:8000 user@154.193.243.169 -N` 建 M5→SG 隧道
- [ ] **launchd 常驻**：写 `com.local.loki-http.plist`，server_http.py 保持运行
- [ ] **Open WebUI 配置**：SG 上配 OpenAI API → `http://localhost:18000/v1`
- [ ] **MLX LLM 链路确认**：检查 ollama-adapter 是否正常，MLX 服务是否需启动
- [ ] **chroma 按 path 去重 GC**（上次遗留）：v3 fp 切换后旧 mtime_fp id 残留
- [ ] **质量反馈闭环**（上次遗留）：cold files 自动清退 / hot files 加权

## 难点与风险

- **MLX LLM 链路**：当前 MLX 推理服务 (:3003) 未运行，LLM 问答可能失败。需确认 ollama-adapter 兼容性
- **BGE-M3 加载慢**：server_http.py startup 已预加载，但首次请求仍有 5-10s 延迟
- **ChromaDB 嵌入式**：不支持并发请求，多实例会锁冲突
- **无公网 IP**：M5 只有内网 IP (10.10.10.103)，SG 可达性依赖 SSH 隧道
- **内容外发**：用户明确禁止从本机传输文件，API 只返回检索结果和 LLM 答案

## 快速恢复指引

```bash
# 1. 启动 OpenAI 兼容 API
~/mlx-env/bin/python code/rag-mcp-server/server_http.py --host 0.0.0.0 --port 8000

# 2. 验证 API（M5 本机）
curl http://localhost:8000/health
curl http://localhost:8000/v1/models
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"loki-rag","messages":[{"role":"user","content":"PE监管要点"}]}'

# 3. 全套测试（269 应全绿）
~/mlx-env/bin/python -m pytest code/scripts/tests/ -q

# 4. SSH 隧道（从 M5）
ssh -R 18000:localhost:8000 user@154.193.243.169 -N

# 5. GitHub
git remote -v  # → origin git@github.com:wcy8822/knowledge-rag.git
```

## 关键文件位置（本会话新增）

```
# OpenAI 兼容 API
code/rag-mcp-server/server_http.py         # 主文件，含 /v1/chat/completions + /v1/models
code/scripts/tests/test_openai_api.py      # 13 个 OpenAI 格式测试

# 文档
M5-RAG现状盘点-OpenAI-API评估报告.md        # 完整盘点报告
HANDOFF-m5pro-llm-integration.md           # MLX 推理栈交接

# 备份
code/rag-mcp-server/server_http.py.bak.*   # 改造前备份
```

## 累积数据快照（截止 2026-05-05）

- chroma summaries: ~10,955
- chroma chunks: 37,956
- chroma ddl: 502
- state.docs: 7,617
- 单测: **269 全绿**
- benchmark Recall@5: **57.5%**
- GitHub: **wcy8822/knowledge-rag** (public, 46 commits, 265 files)
