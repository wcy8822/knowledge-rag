# MCP HTTP Transport

## 启动
```bash
cd ~/Work/projects/knowledge-rag-知识库/code/rag-mcp-server
python3 server_http.py --port 8765
```

## 端点

| 端点 | 用途 |
|------|------|
| `POST /mcp` | MCP JSON-RPC（OpenClaw/mcporter 用） |
| `GET /health` | 健康检查 |
| `POST /api/search` | REST 知识库搜索 |
| `POST /api/nl2sql` | REST NL2SQL |
| `POST /api/query` | REST MySQL 查询 |

## OpenClaw 配置
mcporter skill 中将 MCP transport 改为 HTTP，目标 `http://127.0.0.1:8765/mcp`

## 测试
```bash
curl -X POST http://127.0.0.1:8765/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```
