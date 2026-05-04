# Loki — 本地知识库 RAG 系统

> 企业知识库检索增强生成：自研 Hybrid Search (BGE-M3 + BM25 + RRF) + 11-tool MCP Server + OpenAI 兼容 API

## 架构

```
┌──────────────┐    MCP/HTTP    ┌────────────────────┐
│  Claude/GPT  │ ◄─────────── ► │  rag-mcp-server    │
│  Open WebUI  │                │  11 tools          │
└──────────────┘                │  + OpenAI API      │
                                └──────┬─────────────┘
                                       │
              ┌────────────────────────┼────────────────────┐
              │                        │                    │
         ChromaDB                  MySQL              File System
    BGE-M3 (1024-dim)          11库 461表         Obsidian/项目文档
    3 collections ~49K 向量
```

## 项目结构

| 模块 | 目录 | 说明 |
|------|------|------|
| **MCP Server** | `code/rag-mcp-server/` | 11 tool MCP + HTTP 传输 + OpenAI 兼容端点 |
| **Pipeline** | `code/scripts/` | 全量扫描→BGE-M3 embed→ChromaDB 入库→BM25 重建 |
| **本地RAG** | `code/local-rag-system/` | 早期 FastAPI 版本（备用） |
| **批量向量化** | `code/kb_vectorization/` | 旧向量化流程 |

## 快速启动

```bash
# Python 环境
~/mlx-env/bin/pip install chromadb sentence-transformers fastapi uvicorn jieba rank-bm25 pymysql

# 启动 HTTP API (OpenAI 兼容)
~/mlx-env/bin/python code/rag-mcp-server/server_http.py
# → 监听 0.0.0.0:8000
# → POST /v1/chat/completions  (OpenAI 兼容)
# → POST /mcp                   (MCP JSON-RPC)
```

## 数据资产（不入库）

| 资源 | 说明 |
|------|------|
| BGE-M3 模型 | 本地路径，4.3GB，1024-dim |
| ChromaDB 向量 | 本地路径，~902MB，~49K 向量 |
| BM25 索引 | 运行时构建，~211MB |

## 测试

```bash
~/mlx-env/bin/python -m pytest code/scripts/tests/ -q  # 269 tests
```
