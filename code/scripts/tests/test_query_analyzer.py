#!/usr/bin/env python3
"""loki_query_analyzer 单元测试 (Phase 2)"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from loki_query_analyzer import (  # noqa: E402
    build_report,
    compute_cold_files,
    compute_slow_queries,
    compute_top_files,
    compute_top_queries,
    compute_zero_hit_queries,
    filter_window,
    load_entries,
    parse_ts,
    render_markdown,
    write_report,
)


def _entry(ts, query="q", n_returned=3, top_files=None, latency_ms=100, tool="search_knowledge"):
    return {
        "ts": ts,
        "tool": tool,
        "query": query,
        "n_requested": 5,
        "n_returned": n_returned,
        "top_files": top_files or [],
        "latency_ms": latency_ms,
        "extra": {},
    }


def _ts(now: datetime, days_ago: float) -> str:
    return (now - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S")


@pytest.fixture
def now():
    return datetime(2026, 4, 26, 12, 0, 0)


@pytest.fixture
def sample_entries(now):
    return [
        _entry(_ts(now, 0.5), query="商户画像", top_files=["/a.md", "/b.md"]),
        _entry(_ts(now, 1), query="商户画像", top_files=["/a.md"]),
        _entry(_ts(now, 2), query="油价预测", top_files=["/c.md"]),
        _entry(_ts(now, 3), query="无结果Q", n_returned=0, top_files=[]),
        _entry(_ts(now, 4), query="慢查询Q", latency_ms=8000, top_files=["/d.md"]),
        _entry(_ts(now, 10), query="窗口外", top_files=["/e.md"]),
    ]


class TestParseTs:
    def test_iso_with_tz(self):
        dt = parse_ts("2026-04-26T17:00:00+08:00")
        assert dt is not None
        assert dt.year == 2026

    def test_iso_naive(self):
        assert parse_ts("2026-04-26T17:00:00") is not None

    def test_garbage(self):
        assert parse_ts("not a date") is None
        assert parse_ts("") is None


class TestLoadEntries:
    def test_missing_file(self, tmp_path):
        assert load_entries(tmp_path / "nope.jsonl") == []

    def test_skips_bad_lines(self, tmp_path):
        p = tmp_path / "q.jsonl"
        p.write_text(
            '{"ts":"2026-04-26T10:00:00","tool":"t","query":"a","n_requested":1,"n_returned":1,"top_files":[],"latency_ms":1}\n'
            "BROKEN LINE\n"
            "\n"
            '{"ts":"2026-04-26T10:01:00","tool":"t","query":"b","n_requested":1,"n_returned":1,"top_files":[],"latency_ms":1}\n'
        )
        es = load_entries(p)
        assert len(es) == 2
        assert es[0]["query"] == "a"


class TestFilterWindow:
    def test_filters_by_days(self, now, sample_entries):
        out = filter_window(sample_entries, days=7, now=now)
        assert len(out) == 5

    def test_zero_window(self, now, sample_entries):
        assert filter_window(sample_entries, days=0, now=now) == []


class TestAggregations:
    def test_top_queries(self, now, sample_entries):
        window = filter_window(sample_entries, 7, now=now)
        top = compute_top_queries(window, top=3)
        assert top[0] == ("商户画像", 2)

    def test_zero_hit(self, now, sample_entries):
        window = filter_window(sample_entries, 7, now=now)
        zh = compute_zero_hit_queries(window)
        assert ("无结果Q", 1) in zh

    def test_slow_queries(self, now, sample_entries):
        window = filter_window(sample_entries, 7, now=now)
        slow = compute_slow_queries(window, threshold_ms=5000)
        assert len(slow) == 1
        assert slow[0][0] == "慢查询Q"
        assert slow[0][1] == 8000

    def test_top_files(self, now, sample_entries):
        window = filter_window(sample_entries, 7, now=now)
        tf = compute_top_files(window)
        d = dict(tf)
        assert d["/a.md"] == 2
        assert d["/b.md"] == 1


class TestColdFiles:
    def test_skipped_when_no_loader(self):
        cold, reason = compute_cold_files([], cold_days=30, kb_files_loader=None)
        assert cold == []
        assert "未提供" in reason

    def test_loader_failure(self):
        def boom():
            raise RuntimeError("boom")
        cold, reason = compute_cold_files([], cold_days=30, kb_files_loader=boom)
        assert cold == []
        assert "boom" in reason

    def test_empty_kb(self):
        cold, reason = compute_cold_files([], cold_days=30, kb_files_loader=lambda: [])
        assert cold == []
        assert "为空" in reason

    def test_cold_diff(self, now):
        kb = ["/a.md", "/b.md", "/c.md"]
        entries = [_entry(_ts(now, 5), top_files=["/a.md"])]
        cold, reason = compute_cold_files(entries, cold_days=30, kb_files_loader=lambda: kb, now=now)
        assert reason is None
        assert cold == ["/b.md", "/c.md"]


class TestBuildReport:
    def test_full_report(self, now, sample_entries):
        r = build_report(
            entries_all=sample_entries,
            days=7,
            cold_days=30,
            top=10,
            slow_threshold_ms=5000,
            kb_files_loader=lambda: ["/a.md", "/b.md", "/cold_only.md"],
            now=now,
        )
        assert r.total_queries == 5
        assert r.window_days == 7
        assert r.cold_days == 30
        assert r.cold_files_skipped_reason is None
        assert "/cold_only.md" in r.cold_files
        assert r.by_tool.get("search_knowledge") == 5

    def test_no_loader_skips_cold(self, now, sample_entries):
        r = build_report(
            entries_all=sample_entries, days=7, cold_days=30, top=10,
            slow_threshold_ms=5000, kb_files_loader=None, now=now,
        )
        assert r.cold_files == []
        assert r.cold_files_skipped_reason


class TestRenderMarkdown:
    def test_markdown_has_sections(self, now, sample_entries):
        r = build_report(
            entries_all=sample_entries, days=7, cold_days=30, top=10,
            slow_threshold_ms=5000, kb_files_loader=None, now=now,
        )
        md = render_markdown(r)
        assert md.startswith("---\n")
        assert "type: report" in md
        assert "## 高频 query" in md
        assert "## 零结果 query" in md
        assert "## 慢查询" in md
        assert "## 高命中文件" in md
        assert "## 冷文件" in md
        assert "商户画像" in md


class TestWriteReport:
    def test_writes_file(self, tmp_path, now):
        p = write_report("# hi\n", tmp_path, now=now)
        assert p.exists()
        assert p.suffix == ".md"
        assert "Loki周报" in p.name
        assert p.read_text() == "# hi\n"

    def test_creates_dir(self, tmp_path, now):
        target = tmp_path / "deep" / "Inbox"
        p = write_report("# x\n", target, now=now)
        assert p.exists()
