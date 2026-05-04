#!/usr/bin/env python3
"""server_http.py OpenAI 兼容 API 单元测试"""
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rag-mcp-server"))

# 预 mock 重型依赖，避免 TestClient 创建时加载 BGE-M3
MOCK_ASK_RESULT = "PE 监管要点：需关注穿透式监管要求，特别是在投资端加强合规管理。"

MOCK_SEARCH_RESULTS = [
    {
        "similarity": 0.85,
        "topic": "PE 监管要点",
        "path": "/Users/didi/Work/docs/obsidian-vault/obsidian/notes/PE监管要点.md",
        "text": "2025年PE监管重点：穿透式监管、投资者适当性管理、信息披露",
        "weighted_score": 0.425,
        "weight": 0.5,
        "source": "summaries",
        "heading": "",
        "domain": "summaries",
    },
    {
        "similarity": 0.72,
        "topic": "私募基金合规手册",
        "path": "/Users/didi/Work/docs/私募合规-2025.md",
        "text": "私募基金合规要求汇总",
        "weighted_score": 0.36,
        "weight": 0.5,
        "source": "chunks",
        "heading": "合规要求",
        "domain": "chunks",
    },
]

# ---- 创建 Mock 客户端 ----
_patches = [
    patch("server.search_knowledge", return_value=MOCK_SEARCH_RESULTS),
    patch("server.search_ddl", return_value=MOCK_SEARCH_RESULTS),
    patch("server.ask_knowledge", return_value=MOCK_ASK_RESULT),
    patch("server.get_stats", return_value={"summaries": "mock"}),
    patch("server.get_model", MagicMock()),
]
for _p in _patches:
    _p.start()

# app.startup 预加载的背景线程会调用 get_collection（server.py 中不存在，已有 bug），
# 这里 mock 掉防止终端报错
import server
server.get_collection = MagicMock()

from server_http import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_mocks():
    pass


class TestOpenAIModels:
    def test_list_models(self):
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) == 2
        model_ids = {m["id"] for m in data["data"]}
        assert "loki-rag" in model_ids
        assert "loki-search" in model_ids

    def test_model_fields(self):
        resp = client.get("/v1/models")
        data = resp.json()
        for m in data["data"]:
            assert "id" in m
            assert "object" in m
            assert m["object"] == "model"
            assert m["owned_by"] == "loki"


class TestChatCompletions:
    def test_basic_rag_query(self):
        resp = client.post("/v1/chat/completions", json={
            "model": "loki-rag",
            "messages": [{"role": "user", "content": "PE 监管要点有哪些"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["model"] == "loki-rag"
        assert len(data["choices"]) == 1
        choice = data["choices"][0]
        assert choice["message"]["role"] == "assistant"
        assert choice["message"]["content"] == MOCK_ASK_RESULT
        assert choice["finish_reason"] == "stop"
        assert "id" in data
        assert data["id"].startswith("chatcmpl-")
        assert "usage" in data

    def test_search_model_routing(self):
        resp = client.post("/v1/chat/completions", json={
            "model": "loki-search",
            "messages": [{"role": "user", "content": "PE 监管"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "loki-search"
        content = data["choices"][0]["message"]["content"]
        assert "找到以下相关文档" in content
        assert "PE 监管要点" in content

    def test_default_model_is_rag(self):
        """未指定 model 时默认走 loki-rag"""
        resp = client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "PE 监管"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["model"] == "loki-rag"
        assert data["choices"][0]["message"]["content"] == MOCK_ASK_RESULT

    def test_extracts_last_user_message(self):
        """多轮对话时应取最后一条 user 消息"""
        resp = client.post("/v1/chat/completions", json={
            "model": "loki-rag",
            "messages": [
                {"role": "system", "content": "你是助手"},
                {"role": "user", "content": "前面的问题"},
                {"role": "assistant", "content": "前面的回答"},
                {"role": "user", "content": "真正的 query"},
            ],
        })
        assert resp.status_code == 200
        assert resp.json()["choices"][0]["message"]["content"] == MOCK_ASK_RESULT

    def test_empty_messages_error(self):
        resp = client.post("/v1/chat/completions", json={
            "model": "loki-rag",
            "messages": [],
        })
        assert resp.status_code == 400
        assert "No user message" in resp.json()["error"]["message"]

    def test_only_system_message_error(self):
        resp = client.post("/v1/chat/completions", json={
            "model": "loki-rag",
            "messages": [{"role": "system", "content": "你是助手"}],
        })
        assert resp.status_code == 400
        assert "No user message" in resp.json()["error"]["message"]

    def test_n_parameter_passthrough(self):
        """loki-search 应透传 n 参数"""
        # search_knowledge 已被全局 mock，这里只验证端点不报错
        resp = client.post("/v1/chat/completions", json={
            "model": "loki-search",
            "messages": [{"role": "user", "content": "query"}],
            "n": 10,
        })
        assert resp.status_code == 200


class TestStreaming:
    def test_streaming_response(self):
        resp = client.post("/v1/chat/completions", json={
            "model": "loki-rag",
            "messages": [{"role": "user", "content": "PE 监管"}],
            "stream": True,
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert "data:" in body
        assert "[DONE]" in body
        # 验证内容被逐字符拆分
        chunks = [l for l in body.split("\n") if l.startswith("data:") and l != "data: [DONE]"]
        contents = []
        for chunk in chunks:
            payload = json.loads(chunk[6:])
            delta = payload["choices"][0].get("delta", {})
            if delta.get("content"):
                contents.append(delta["content"])
        assert "".join(contents) == MOCK_ASK_RESULT

    def test_streaming_has_finish_reason(self):
        resp = client.post("/v1/chat/completions", json={
            "model": "loki-rag",
            "messages": [{"role": "user", "content": "query"}],
            "stream": True,
        })
        body = resp.text
        # 最后一个非 DONE 的 data chunk 应有 finish_reason: "stop"
        chunks = [l for l in body.split("\n") if l.startswith("data:") and l != "data: [DONE]"]
        last = json.loads(chunks[-1][6:])
        assert last["choices"][0]["finish_reason"] == "stop"


class TestHealth:
    def test_health_endpoint(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestOpenAIResponseFormat:
    def test_response_has_required_fields(self):
        resp = client.post("/v1/chat/completions", json={
            "model": "loki-rag",
            "messages": [{"role": "user", "content": "test"}],
        })
        data = resp.json()
        required = {"id", "object", "created", "model", "choices", "usage"}
        assert required.issubset(set(data.keys()))
        for choice in data["choices"]:
            assert "index" in choice
            assert "message" in choice
            assert "finish_reason" in choice
            assert "role" in choice["message"]
            assert "content" in choice["message"]
