#!/usr/bin/env python3
"""loki_state_cleanup 单元测试"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from loki_state_cleanup import (  # noqa: E402
    CleanupReport,
    backup_state,
    compute_new_state,
    load_state_ids,
    write_state,
)


class TestLoadStateIds:
    def test_missing_returns_empty(self, tmp_path):
        assert load_state_ids(tmp_path / "nope.json") == set()

    def test_loads_list(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps(["a", "b", "c"]))
        assert load_state_ids(p) == {"a", "b", "c"}

    def test_dedups(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps(["a", "a", "b"]))
        assert load_state_ids(p) == {"a", "b"}


class TestComputeNewState:
    def test_basic_diff(self):
        old = {"keep1", "keep2", "stale1", "stale2"}
        summaries = {"keep1", "keep2", "new1"}
        ddl = {"ddl1"}
        new, report = compute_new_state(old, summaries, ddl)
        assert new == {"keep1", "keep2", "new1", "ddl1"}
        assert report.state_size == 4
        assert report.summaries_size == 3
        assert report.ddl_size == 1
        assert report.state_new_size == 4
        assert report.removed == 2
        assert report.added == 2

    def test_full_overlap(self):
        old = {"a", "b"}
        new, report = compute_new_state(old, {"a", "b"}, set())
        assert new == {"a", "b"}
        assert report.removed == 0
        assert report.added == 0

    def test_empty_old(self):
        new, report = compute_new_state(set(), {"a"}, {"b"})
        assert new == {"a", "b"}
        assert report.removed == 0
        assert report.added == 2

    def test_empty_chroma(self):
        new, report = compute_new_state({"a", "b"}, set(), set())
        assert new == set()
        assert report.removed == 2

    def test_realistic_scale(self):
        keep = {f"k{i}" for i in range(58729)}
        stale = {f"s{i}" for i in range(94013)}
        summary_only = {f"o{i}" for i in range(4269)}
        ddl = {f"d{i}" for i in range(605)}

        old = keep | stale
        summaries = keep | summary_only
        new, report = compute_new_state(old, summaries, ddl)

        assert report.state_size == 152742
        assert report.summaries_size == 62998
        assert report.ddl_size == 605
        assert report.state_new_size == 63603
        assert report.removed == 94013
        assert report.added == 4874


class TestBackupState:
    def test_creates_backup(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text('["a","b"]')
        bak = backup_state(p, ts="20260426170000")
        assert bak.exists()
        assert ".bak.20260426170000" in bak.name
        assert bak.read_text() == '["a","b"]'

    def test_distinct_ts(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("[]")
        b1 = backup_state(p, ts="20260426170000")
        b2 = backup_state(p, ts="20260426170001")
        assert b1 != b2
        assert b1.exists() and b2.exists()


class TestWriteState:
    def test_writes_sorted(self, tmp_path):
        p = tmp_path / "state.json"
        write_state(p, {"c", "a", "b"})
        data = json.loads(p.read_text())
        assert data == ["a", "b", "c"]

    def test_round_trip(self, tmp_path):
        p = tmp_path / "state.json"
        ids = {"x" * 32, "y" * 32}
        write_state(p, ids)
        assert load_state_ids(p) == ids


class TestCleanupReportText:
    def test_renders_all_fields(self):
        r = CleanupReport(
            state_size=100, summaries_size=50, ddl_size=10,
            state_new_size=60, removed=42, added=2,
        )
        t = r.to_text()
        assert "原 state: 100" in t
        assert "summaries ids: 50" in t
        assert "ddl ids: 10" in t
        assert "清洗后 state: 60" in t
        assert "剔除: 42" in t
        assert "补回: 2" in t
