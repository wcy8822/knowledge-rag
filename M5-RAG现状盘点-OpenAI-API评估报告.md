# M5 本机 RAG 系统现状盘点 & OpenAI Compatible API 可行性评估

> 生成时间: 2026-05-04 | 目标: 让 SG (154.193.243.169:8080) 的 Open WebUI 通过 HTTP 调用本机 RAG

---

## 1. RAG 框架

- **框架名**: **Loki（自研）** — 未使用 LlamaIndex / LangChain / Haystack，纯 Python + ChromaDB + sentence-transformers
- **当前版本**: 无正式版本号，迭代到 Phase 3（Hybrid Search: BGE-M3 向量 + BM25 + RRF 融合）
- **入口脚本**:

  | 组件 | 路径 | 用途 |
  |------|------|------|
  | MCP Server (主用) | `code/rag-mcp-server/server.py` (1074行) | 11 tool MCP stdio server，核心搜索/问答/MySQL/笔记/工作日志 |
  | MCP HTTP 变体 | `code/rag-mcp-server/server_http.py` (235行) | FastAPI 版 MCP over HTTP (已有!) |
  | Pipeline | `code/scripts/loki_pipeline.py` (601行) | 全量扫描→embed→入库→BM25 重建 |
  | 分块 | `code/scripts/loki_chunk.py` (625行) | 长文档语义分块 |
  | CLI 搜索 | `code/scripts/loki_search.py` (337行) | 命令行调试搜索 (hybrid/vector/bm25) |
  | 旧 FastAPI 系统 | `code/local-rag-system/` | 独立子系统，当前未在用 |

- **Python 虚拟环境**: `/Users/didi/mlx-env/bin/python` (Python 3.12.13)
- **定时运行**: launchd `com.didi.loki` 每天凌晨 02:00 跑 pipeline

### 核心依赖版本

```
chromadb                1.5.8
sentence-transformers   5.4.1
torch                   2.11.0
transformers            5.5.4
pydantic                2.13.3
PyMySQL                 1.1.2
rank-bm25               0.2.2
jieba                   0.42.1
fastapi                 (server_http.py 依赖)
uvicorn                 (server_http.py 依赖)
```

---

## 2. 向量库

- **类型**: ChromaDB（嵌入式 PersistentClient，同进程，非 C/S 模式）
- **数据存储路径**: `/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge/`
- **占用大小**: ~902 MB（整个 vectors/ 目录）
- **BM25 索引**: `/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs/bm25_index.pkl` (211 MB)

```bash
$ du -sh /Users/didi/Work/data/vectors/
902M    /Users/didi/Work/data/vectors/

$ ls -lh /Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs/bm25_index.pkl
-rw-r--r--  211M  bm25_index.pkl
```

### Collection 详情

| Collection | 文档数 | 向量维度 | 说明 |
|------------|--------|----------|------|
| `doc_knowledge_bge_m3` | **10,955** | 1024 | 文档摘要向量 (Phase 1) |
| `doc_knowledge_chunks` | **37,956** | 1024 | 长文档分块向量 (Phase 2) |
| `ddl_schema_bge_m3` | **502** | 1024 | DDL 表结构向量 |
| `doc_knowledge` | 0 | — | 旧 collection，已清空 |
| **合计** | **~49,413** | — | |

```bash
$ /Users/didi/mlx-env/bin/python -c "
import chromadb
c = chromadb.PersistentClient(path='/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge')
for col in c.list_collections():
    print(f'{col.name}: {col.count()} docs')
"
doc_knowledge: 0 docs
doc_knowledge_bge_m3: 10955 docs
doc_knowledge_chunks: 37956 docs
ddl_schema_bge_m3: 502 docs
```

- **是否常驻进程**: **否**。ChromaDB 嵌入 Python 进程内，server.py 被调用时才加载。无端口监听。
- **状态文件**: `state.json` 追踪 7,617 个文件 + 502 DDL

---

## 3. Embedding 模型

- **模型**: **BGE-M3** (BAAI)
- **来源**: ModelScope 下载，本地路径 `/Users/didi/models/bge-m3/BAAI/bge-m3`
- **模型大小**: 4.3 GB
- **运行方式**: sentence-transformers（本地），MPS (Apple Silicon GPU) 加速
- **向量维度**: **1024**
- **上下文长度**: **8192 tokens** (BGE-M3 标准)
- **特性**: 支持 Dense + Sparse (Lexical) + ColBERT 三种检索，当前仅用 Dense embedding

```bash
$ du -sh /Users/didi/models/bge-m3
4.3G    /Users/didi/models/bge-m3

$ /Users/didi/mlx-env/bin/python -c "
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('/Users/didi/models/bge-m3/BAAI/bge-m3')
e = m.encode(['test'], normalize_embeddings=True)
print(f'dimension: {e.shape[1]}')
"
dimension: 1024
```

---

## 4. 文档源 & Chunk 策略

### 索引源目录

```python
SCAN_DIRS = [
    "/Users/didi/Work/docs/obsidian-vault/obsidian",   # Obsidian 笔记
    "/Users/didi/Work/docs",                            # 其他文档
    "/Users/didi/Work/projects",                        # 项目文档
    "/Users/didi/.allin_ai_safe/docs",                  # 知识库算法文档
]
```

### 支持的文件类型

`.md`, `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.txt`, `.sql`, `.py`, `.sh`, `.yaml`, `.yml`

### 排除目录

`.obsidian`, `Templates`, `node_modules`, `__pycache__`, `.git`, `venv`, `env`, `bge-m3-model`, `archives`, `chroma`, `人事-简历`, `_大文件归档`, `site-packages`, `.venv`, `python-sdk`

### Chunk 策略（双轨制）

| 文件大小 | 策略 | 参数 |
|----------|------|------|
| < 3KB | **不分块**，仅 Phase 1 摘要 | head 2,000 字符 |
| 3KB ~ 5MB | **语义分块**，按标题/段落边界切 | chunk_target=1000 字, overlap=150 字 |
| > 5MB | **跳过** | 防止噪声 |

```python
# 分块参数 (loki_chunk.py)
CHUNK_MIN       = 200       # 块最小字数（太短合并到上一块）
CHUNK_TARGET    = 1000      # 目标字数
CHUNK_MAX       = 2000      # 块最大字数（超过强制切）
OVERLAP         = 150       # 重叠窗口字数
MIN_FILE_SIZE   = 3000      # <3KB 不分块（Phase 1 已覆盖）
SKIP_SIZE       = 5_000_000  # 5MB+ 跳过
```

### 增量更新机制

- **定时任务**: macOS launchd 每天凌晨 02:00 跑 `loki_pipeline.py --all --max-files 1500`
- **断点续跑**: fingerprint v3（content hash）跳过已处理文件
- **无文件监听**: 不支持实时更新，依赖定时全量+增量扫描
- **BM25 索引**: Pipeline 跑完自动重建

```bash
$ cat /Users/didi/Library/LaunchAgents/com.didi.loki.plist
# StartCalendarInterval Hour=2 Minute=0
# WorkingDirectory: code/scripts
# Python: /Users/didi/mlx-env/bin/python loki_pipeline.py all --max-files 1500
```

---

## 5. 调用方式

### 当前调用方式

**方式一：MCP stdio 协议（主用）**

Claude Desktop / OpenClaw 通过 MCP 协议直接调用 `server.py`：

```
MCP initialize → tools/list → search_knowledge / ask_knowledge / nl2sql / ...
```

这是**当前唯一的生产调用路径**。

**方式二：CLI 调试搜索**

```bash
$ /Users/didi/mlx-env/bin/python code/scripts/loki_search.py "橙化率计算公式"
$ /Users/didi/mlx-env/bin/python code/scripts/loki_search.py "POP 重叠" --bm25-only
```

**方式三：已有 HTTP MCP 变体（未常驻运行）**

`code/rag-mcp-server/server_http.py` 已实现了 FastAPI HTTP 传输，但**当前未常驻运行**：

```bash
# 启动（手动）
/Users/didi/mlx-env/bin/python code/rag-mcp-server/server_http.py --host 0.0.0.0 --port 8765
```

### 核心函数签名

```python
# 文件: code/rag-mcp-server/server.py

def search_knowledge(query: str, n: int = 5) -> list:
    """Hybrid Search: 向量(summaries+chunks) + BM25 + RRF 融合"""
    
def ask_knowledge(question: str) -> str:
    """RAG + LLM 问答"""
    docs = search_knowledge(question, n=5)
    # → 构建 prompt → qwen2.5:7b (localhost:11434) → 返回答案

def get_stats() -> dict:
    """知识库统计"""

def search_ddl(query: str, n: int = 5) -> list:
    """专搜 DDL 表结构"""

# LLM 调用
OLLAMA_API = "http://localhost:11434/api/generate"
LLM_MODEL = "qwen2.5:7b"
```

### Query 输入输出示例

**输入**:
```
"我去年关于 PE 监管的笔记说了什么"
```

**输出**（经 ask_knowledge 流程）:
```
[... RAG 检索到的文档拼接为 context ...]
→ qwen2.5:7b 根据 context 生成中文答案
→ 追加来源文件列表

来源: /Users/didi/Work/docs/obsidian-vault/obsidian/notes/PE监管要点.md, /Users/didi/...
```

---

## 6. 暴露成 OpenAI 兼容 API 的可行性评估

### 目标格式

```python
# POST http://m5.local:8000/v1/chat/completions
{
  "model": "my-rag",
  "messages": [{"role": "user", "content": "我去年关于 PE 监管的笔记说了什么"}]
}
# →
{
  "choices": [{
    "message": {"role": "assistant", "content": "<RAG 检索 + LLM 整合后的答案>"}
  }]
}
```

### 方案分析

**方案 A：扩展现有 `server_http.py`（推荐，最快）**

现有 `server_http.py` 已具备：
- FastAPI app + uvicorn 启动
- 模型预加载（startup event）
- 所有 MCP tool 函数复用 `server.py`
- `/health` 健康端点
- `/api/search` 搜索端点

需要新增：
```
POST /v1/chat/completions  # OpenAI 兼容端点
```

改造点：
1. 新增 OpenAI 格式路由，解析 `messages` → 提取 user content
2. 调用现有 `ask_knowledge(question)` → 拿结果
3. 封装为 OpenAI response 格式
4. (可选) 支持 streaming SSE

### 预估工作量

| 改造项 | 代码行数 | 说明 |
|--------|----------|------|
| `/v1/chat/completions` 端点 | ~40 行 | 解析 OpenAI request → 调 ask_knowledge → 封装 response |
| `/v1/models` 端点 | ~15 行 | 返回可用模型列表 |
| `/v1/chat/completions` streaming | ~30 行 | SSE 流式输出（可选） |
| 绑定 `0.0.0.0:8000` | 改 1 行 | 默认 127.0.0.1 改 0.0.0.0 |
| **合计** | **~85 行** | |

**评估**: 现有 `ask_knowledge()` 函数可以直接复用，无需拆改。整个改造约 **1 小时**。

### 方案 B：重写独立 FastAPI 服务

若不需要 MCP 兼容性，可写精简版，只暴露 OpenAI 格式。效率与方案 A 相当但功能更单一。

---

## 7. 网络连通性（M5 ↔ SG）

### 实测数据

```bash
$ hostname
MacBook-Pro.local

$ ifconfig | grep "inet " | grep -v 127.0.0.1
    inet 10.10.10.103 netmask 0xffffff00 broadcast 10.10.10.255
    inet 198.18.0.1 --> 198.18.0.1 netmask 0xfffffffc

$ curl -s ifconfig.me
154.193.243.169
```

- **M5 本机 IP**: `10.10.10.103`（内网）
- **虚拟接口**: `198.18.0.1`（疑似 Clash/VPN 代理隧道）
- **公网出口 IP**: `154.193.243.169` — 与 SG 服务器相同，说明 M5 通过同一网关/tunnel 出站
- **SG 服务器**: `154.193.243.169:8080`（Open WebUI）
- **端口 8000**: 未被占用
- **端口 3003**: MLX 推理服务**当前未运行**（说明 LLM 走的是 Ollama 本地，而非 MLX）

### 连通性判断

| 方向 | 状态 | 说明 |
|------|------|------|
| M5 → SG | ✅ 通 | Chrome 有活跃连接 `198.18.0.1:63603→154.193.243.169:8080` |
| SG → M5 | ❌ 不通 | M5 只有内网 IP 10.10.10.103，无公网可达地址 |

### 可用方案对比

| 方案 | 难度 | 延迟 | 稳定性 | 条件 |
|------|------|------|--------|------|
| **SSH 反向隧道** ⭐ | 低 | +5ms | 高 | M5 能 SSH 到 SG |
| Tailscale | 低 | +3ms | 高 | 两端装 tailscale |
| frp | 中 | +5ms | 高 | SG 端跑 frps |
| ngrok | 低 | +20ms | 中 | 注册 ngrok 账号 |
| Cloudflare Tunnel | 中 | +15ms | 高 | 有域名 |

**当前已具备的条件**:
- ✅ M5 能访问 SG（IP 154.193.243.169，有活跃 TCP 连接）
- ❌ 未安装 Tailscale / ngrok / frp
- ❌ M5 无公网 IP
- ❓ 未知能否 SSH 到 SG

### 推荐方案：SSH 反向隧道

```bash
# M5 上执行（需能 SSH 到 SG）
ssh -R 18000:localhost:8000 user@154.193.243.169 -N -f
# SG 上 Open WebUI 配 OpenAI API: http://localhost:18000/v1
```

---

## 8. 关键依赖 & 已知坑

### 核心依赖 Top 5

| 依赖 | 版本 | 作用 |
|------|------|------|
| `chromadb` | 1.5.8 | 向量存储 + 检索 |
| `sentence-transformers` | 5.4.1 | BGE-M3 embedding 推理 |
| `torch` | 2.11.0 | 底层计算框架 (Apple MPS) |
| `transformers` | 5.5.4 | HuggingFace 模型加载 |
| `fastapi` + `uvicorn` | — | HTTP 服务 (已有 server_http.py) |

### 已知性能瓶颈

1. **MPS 内存泄漏**（PyTorch issue #154329）: 长时间 embed 会累积 GPU 缓存
   - 已用 `torch.mps.empty_cache()` + 每 50 批重建 model 缓解
   - laiunchd wrapper 设 12GB RSS 硬限兜底
2. **首次加载慢**: BGE-M3 模型加载需 5-10 秒（server_http.py 已做 startup 预加载）
3. **Ollama 适配器**: LLM 调用走 `localhost:11434`，但实际被 `ollama-adapter.py` 转发到 MLX (`:3003`)。当前 MLX 服务未运行，LLM 链可能不通
4. **Recall@5 = 57.5%**: Hybrid Search 基准为 57.5%，还有提升空间
5. **ChromaDB 嵌入式**: 不支持并发请求，多实例会锁冲突（`.loki_write.lock` 文件锁）

### 上次 query 耗时参考

从 `logs/queries.jsonl` 最新 3 条:
- `7172ms` — 冷启动首次查询
- `73ms` — 后续热查询
- `11553ms` — 冷启动慢查询

---

## 9. 最终结论

### 接入 SG Open WebUI 的最短路径

```
1. 写 ~85 行代码，在 server_http.py 加 OpenAI 兼容层
2. 绑定 0.0.0.0:8000，launchd 设为常驻
3. SSH 反向隧道连 SG: ssh -R 18000:localhost:8000 SG
4. Open WebUI 配 OpenAI API → http://localhost:18000/v1
```

### 预估工时：**2 小时**

- 代码改造: 1 小时（~85 行 Python）
- 隧道搭建 + 测试: 0.5 小时
- 调试验证: 0.5 小时

### 最理想方案（如可长期维护）

```
1. M5 和 SG 都装 Tailscale（5 分钟）
2. server_http.py 加 OpenAI endpoint（1 小时）
3. Open WebUI 直接配 http://m5.tailnet-name.ts.net:8000/v1
```

优势：延迟低、稳定、无需维护 SSH 隧道，Tailscale 自动 NAT 穿透。

---

*报告生成工具: 2026-05-04 手动盘点，所有能跑的命令已实际执行并贴输出。*
