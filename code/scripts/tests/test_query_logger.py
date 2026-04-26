#!/usr/bin/env python3
"""query_logger 单元测试 (Phase 1)"""

import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rag-mcp-server"))

from query_logger import (  # noqa: E402
    QueryLogEntry,
    QueryTimer,
    build_entry,
    log_query,
    write_entry,
)


@pytest.fixture
def tmp_log(tmp_path):
    return tmp_path / "queries.jsonl"


class TestBuildEntry:
    def test_minimal(self):
        e = build_entry("search_knowledge", "q", 5, 3, ["/a.md"], 100)
        assert isinstance(e, QueryLogEntry)
        assert e.tool == "search_knowledge"
        assert e.query == "q"
        assert e.n_requested == 5
        assert e.n_returned == 3
        assert e.top_files == ("/a.md",)
        assert e.latency_ms == 100
        assert e.extra == {}
        assert e.ts

    def test_query_truncation(self):
        long_q = "x" * 1000
        e = build_entry("t", long_q, 0, 0, [], 0)
        assert len(e.query) == 500

    def test_top_files_cap(self):
        files = [f"/f{i}.md" for i in range(50)]
        e = build_entry("t", "q", 0, 0, files, 0)
        assert len(e.top_files) == 10

    def test_explicit_ts(self):
        e = build_entry("t", "q", 0, 0, [], 0, ts="2026-04-26T10:00:00+0800")
        assert e.ts == "2026-04-26T10:00:00+0800"

    def test_extra_dict_independent(self):
        d = {"a": 1}
        e = build_entry("t", "q", 0, 0, [], 0, extra=d)
        d["a"] = 999
        assert e.extra["a"] == 1

    def test_immutable(self):
        e = build_entry("t", "q", 0, 0, ["/a.md"], 0)
        with pytest.raises(Exception):
            e.tool = "other"


class TestJsonlSerialize:
    def test_round_trip(self):
        e = build_entry("t", "测试", 5, 3, ["/a.md", "/b.md"], 99)
        line = e.to_jsonl()
        d = json.loads(line)
        assert d["tool"] == "t"
        assert d["query"] == "测试"
        assert d["top_files"] == ["/a.md", "/b.md"]

    def test_chinese_no_escape(self):
        e = build_entry("t", "中文查询", 0, 0, [], 0)
        assert "中文查询" in e.to_jsonl()


class TestWriteEntry:
    def test_creates_dir(self, tmp_path):
        p = tmp_path / "deep" / "nested" / "queries.jsonl"
        e = build_entry("t", "q", 0, 0, [], 0)
        assert write_entry(e, log_path=p) is True
        assert p.exists()

    def test_appends(self, tmp_log):
        e1 = build_entry("t", "q1", 0, 0, [], 0)
        e2 = build_entry("t", "q2", 0, 0, [], 0)
        write_entry(e1, log_path=tmp_log)
        write_entry(e2, log_path=tmp_log)
        lines = tmp_log.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["query"] == "q1"
        assert json.loads(lines[1])["query"] == "q2"

    def test_swallow_failure(self, tmp_path):
        bad_file = tmp_path / "blocker"
        bad_file.write_text("x")
        bad_path = bad_file / "nope.jsonl"
        e = build_entry("t", "q", 0, 0, [], 0)
        assert write_entry(e, log_path=bad_path) is False


class TestLogQuery:
    def test_full_flow(self, tmp_log):
        ok = log_query("search_knowledge", "Q", 5, 2, ["/a.md", "/b.md"], 1500, log_path=tmp_log)
        assert ok is True
        d = json.loads(tmp_log.read_text().strip())
        assert d["tool"] == "search_knowledge"
        assert d["n_returned"] == 2
        assert d["top_files"] == ["/a.md", "/b.md"]

    def test_zero_results(self, tmp_log):
        ok = log_query("search_knowledge", "无结果Q", 5, 0, [], 800, log_path=tmp_log)
        assert ok is True
        d = json.loads(tmp_log.read_text().strip())
        assert d["n_returned"] == 0
        assert d["top_files"] == []


class TestQueryTimer:
    def test_measures_latency(self):
        with QueryTimer() as t:
            time.sleep(0.02)
        assert t.latency_ms >= 15

    def test_exception_still_records(self):
        t = QueryTimer()
        try:
            with t:
                time.sleep(0.01)
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert t.latency_ms >= 5
