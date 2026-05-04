#!/usr/bin/env python3
"""MCP HTTP Transport + OpenAI Compatible API
启动: python3 server_http.py [--port 8000] [--host 0.0.0.0]
供 Open WebUI 调用的 OpenAI 兼容端点在 /v1/chat/completions
"""

import json
import sys
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import time
import uuid

# 复用 stdio server 的全部 tool 函数
from server import (
    search_knowledge, search_ddl, ask_knowledge, get_stats,
    nl2sql, query_mysql, list_mysql_tables, search_by_fields,
    read_notes, read_worklog, add_worklog,
)

app = FastAPI(title="Knowledge RAG MCP Server (HTTP)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 工具注册表（与 stdio server.py 的 tools/list 保持一致）──
TOOLS = [
    {
        "name": "search_knowledge",
        "description": "在本地知识库中语义搜索，返回最相关的文档。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词或问题，中文"},
                "n": {"type": "integer", "description": "返回结果数量，默认5", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_ddl",
        "description": "专搜 MySQL 数据库表结构（DDL：库表名、字段、注释）。用于查\"哪张表存什么数据\"\"字段定义\"等 schema 问题。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词或问题，中文"},
                "n": {"type": "integer", "description": "返回结果数量，默认5", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "ask_knowledge",
        "description": "向本地知识库提问并获得AI总结的回答。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "你的问题，中文"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "knowledge_stats",
        "description": "查看知识库的统计信息",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "nl2sql",
        "description": "用自然语言查询 MySQL 数据库。自动将中文问题转为SQL并执行。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "自然语言问题，中文"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "query_mysql",
        "description": "在本地 MySQL 数据库执行只读查询。只允许 SELECT/SHOW/DESCRIBE。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL 查询语句"},
                "database": {"type": "string", "description": "数据库名，默认 data_manager_db", "default": "data_manager_db"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "list_mysql_tables",
        "description": "列出指定 MySQL 数据库的所有表及行数。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "database": {"type": "string", "description": "数据库名", "default": "data_manager_db"}
            }
        }
    },
    {
        "name": "search_by_fields",
        "description": "用字段名反查数据库，找出包含这些字段的所有表。用于精确定位业务概念对应的源头表。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fields": {"type": "array", "items": {"type": "string"}, "description": "字段名列表"},
                "min_match": {"type": "integer", "description": "最少匹配字段数，默认3", "default": 3}
            },
            "required": ["fields"]
        }
    },
    {
        "name": "read_notes",
        "description": "读取 Obsidian 笔记。可按项目名或标签搜索。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "笔记相对路径"},
                "project": {"type": "string", "description": "项目名关键词"},
                "tag": {"type": "string", "description": "标签关键词"}
            }
        }
    },
    {
        "name": "read_worklog",
        "description": "读取项目工作日志。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目名关键词，不传则返回全局日志"}
            }
        }
    },
    {
        "name": "add_worklog",
        "description": "向项目工作日志添加一条记录。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "项目名关键词"},
                "entry": {"type": "string", "description": "日志内容"}
            },
            "required": ["project", "entry"]
        }
    }
]

# ── Tool 执行路由 ──
def call_tool(name: str, args: dict) -> str:
    if name == "search_knowledge":
        results = search_knowledge(args["query"], args.get("n", 5))
        text = f"找到 {len(results)} 个相关文档:\n\n"
        for i, doc in enumerate(results):
            text += f"#{i+1} [相似度:{doc['similarity']}] {doc['topic']}\n"
            text += f"   路径: {doc['path']}\n"
            text += f"   摘要: {doc['text'][:300]}\n\n"
        return text
    elif name == "search_ddl":
        results = search_ddl(args["query"], args.get("n", 5))
        text = f"找到 {len(results)} 张相关表:\n\n"
        for i, doc in enumerate(results):
            text += f"#{i+1} [相似度:{doc['similarity']}] 表: {doc.get('topic', '')}\n"
            text += f"   摘要: {doc['text'][:300]}\n\n"
        return text
    elif name == "ask_knowledge":
        return ask_knowledge(args["question"])
    elif name == "knowledge_stats":
        stats = get_stats()
        return "\n".join(f"{k}: {v}" for k, v in stats.items())
    elif name == "nl2sql":
        return nl2sql(args["question"])
    elif name == "query_mysql":
        return query_mysql(args["query"], args.get("database", "data_manager_db"))
    elif name == "list_mysql_tables":
        return list_mysql_tables(args.get("database", "data_manager_db"))
    elif name == "search_by_fields":
        return search_by_fields(args["fields"], args.get("min_match", 3))
    elif name == "read_notes":
        return read_notes(args.get("path"), args.get("tag"), args.get("project"))
    elif name == "read_worklog":
        return read_worklog(args.get("project"))
    elif name == "add_worklog":
        return add_worklog(args["project"], args["entry"])
    else:
        raise ValueError(f"Unknown tool: {name}")

# ── MCP JSON-RPC over HTTP ──
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    body = await request.json()
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "knowledge-rag", "version": "1.0.0"},
            "capabilities": {"tools": {}}
        }})

    elif method == "tools/list":
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})

    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        try:
            text = call_tool(tool_name, args)
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {
                "content": [{"type": "text", "text": text}]
            }})
        except Exception as e:
            return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {
                "content": [{"type": "text", "text": f"错误: {e}"}], "isError": True
            }})

    elif method == "ping":
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {}})

    else:
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": {
            "code": -32601, "message": f"Unknown method: {method}"
        }})

# ── 便捷 REST 端点（给非 MCP 客户端用）──
@app.get("/health")
async def health():
    return {"status": "ok", "tools": len(TOOLS)}

@app.post("/api/search")
async def api_search(request: Request):
    body = await request.json()
    results = search_knowledge(body["query"], body.get("n", 5))
    return {"results": results}

@app.post("/api/nl2sql")
async def api_nl2sql(request: Request):
    body = await request.json()
    return {"result": nl2sql(body["question"])}

@app.post("/api/query")
async def api_query(request: Request):
    body = await request.json()
    return {"result": query_mysql(body["query"], body.get("database", "data_manager_db"))}

# ── OpenAI 兼容 API (供 Open WebUI 调用) ──
OPENAI_MODELS = [
    {"id": "loki-rag", "object": "model", "created": 1714780800,
     "owned_by": "loki"},
    {"id": "loki-search", "object": "model", "created": 1714780800,
     "owned_by": "loki"},
]

@app.get("/v1/models")
async def openai_models():
    return {"object": "list", "data": OPENAI_MODELS}

@app.post("/v1/chat/completions")
async def openai_chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "loki-rag")
    messages = body.get("messages", [])
    stream = body.get("stream", False)

    user_content = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_content = msg.get("content", "")
            break

    if not user_content:
        return JSONResponse({"error": {"message": "No user message found", "type": "invalid_request_error"}}, status_code=400)

    if model == "loki-search":
        results = search_knowledge(user_content, body.get("n", 5))
        answer = "找到以下相关文档:\n\n" + "\n".join(
            f"- [{doc['similarity']}] {doc.get('topic','')} ({doc['path']})"
            for doc in results
        )
    else:
        answer = ask_knowledge(user_content)

    if stream:
        async def generate():
            chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
            for char in answer:
                chunk = json.dumps({
                    "id": chunk_id, "object": "chat.completion.chunk",
                    "created": int(time.time()), "model": model,
                    "choices": [{"index": 0, "delta": {"content": char}, "finish_reason": None}]
                })
                yield f"data: {chunk}\n\n"
            yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": answer},
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    }

# ── 启动时预加载模型（避免首次请求超时）──
@app.on_event("startup")
async def preload():
    import threading
    def _load():
        try:
            from server import get_model, get_collection
            get_model()
            get_collection()
            print("✅ BGE-M3 模型 + ChromaDB 预加载完成")
        except Exception as e:
            print(f"⚠️ 预加载失败（首次调用时会重试）: {e}")
    threading.Thread(target=_load, daemon=True).start()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    print(f"🚀 MCP HTTP Server starting on http://{args.host}:{args.port}")
    print(f"   OpenAI API:   POST /v1/chat/completions")
    print(f"   Models:       GET  /v1/models")
    print(f"   MCP endpoint: POST /mcp")
    print(f"   REST:         /api/search, /api/nl2sql, /api/query")
    print(f"   Health:       GET /health")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
