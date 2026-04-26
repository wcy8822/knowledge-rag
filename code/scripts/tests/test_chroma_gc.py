#!/usr/bin/env python3
"""loki_chroma_gc 单元测试 (C.3)"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from loki_chroma_gc import (  # noqa: E402
    GcReport,
    is_legacy_id,
    sync_state_ddl,
)


HEX = "a" * 32
HEX2 = "b" * 32


class TestIsLegacyId:
    def test_summaries_hex32_legal(self):
        assert is_legacy_id("summaries", HEX) is False

    def test_summaries_doc_X_legacy(self):
        assert is_legacy_id("summaries", "doc_14") is True

    def test_summaries_oil_algo_legacy(self):
        assert is_legacy_id("summaries", "oil-algo-v1-3") is True

    def test_summaries_short_hex_legacy(self):
        assert is_legacy_id("summaries", "abc123") is True

    def test_ddl_hex32_legal(self):
        assert is_legacy_id("ddl", HEX) is False

    def test_ddl_legacy_format(self):
        assert is_legacy_id("ddl", "ddl_data_manager_db_tag_master") is True

    def test_chunks_legal_pattern(self):
        assert is_legacy_id("chunks", f"{HEX}_chunk_0") is False
        assert is_legacy_id("chunks", f"{HEX}_chunk_999") is False

    def test_chunks_bad_head(self):
        assert is_legacy_id("chunks", "doc_14_chunk_0") is True

    def test_chunks_no_chunk_suffix(self):
        assert is_legacy_id("chunks", HEX) is True

    def test_chunks_non_digit_index(self):
        assert is_legacy_id("chunks", f"{HEX}_chunk_X") is True


class TestGcReport:
    def test_default(self):
        r = GcReport(collection="summaries")
        assert r.total == 0
        assert r.legacy == 0
        assert r.sample_legacy_ids == []

    def test_populated(self):
        r = GcReport(collection="ddl", total=605, legacy=12,
                     sample_legacy_ids=["ddl_a", "ddl_b"])
        assert r.legacy == 12
        assert "ddl_a" in r.sample_legacy_ids


class TestSyncStateDdl:
    def _write_v2(self, p: Path, ddl):
        p.write_text(json.dumps({"version": 2, "docs": {}, "ddl": ddl}, ensure_ascii=False))

    def test_removes_deleted_ids(self, tmp_path):
        p = tmp_path / "state.json"
        self._write_v2(p, [HEX, HEX2, "ddl_legacy_a", "ddl_legacy_b"])
        before, after = sync_state_ddl(p, ["ddl_legacy_a", "ddl_legacy_b"])
        assert before == 4
        assert after == 2
        d = json.loads(p.read_text())
        assert sorted(d["ddl"]) == sorted([HEX, HEX2])

    def test_no_op_when_no_match(self, tmp_path):
        p = tmp_path / "state.json"
        self._write_v2(p, [HEX])
        before, after = sync_state_ddl(p, ["nonexistent"])
        assert before == 1
        assert after == 1

    def test_skips_v1(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps([HEX, HEX2]))
        before, after = sync_state_ddl(p, [HEX])
        assert before == 0 and after == 0
        assert json.loads(p.read_text()) == [HEX, HEX2]

    def test_missing_file(self, tmp_path):
        before, after = sync_state_ddl(tmp_path / "nope.json", ["x"])
        assert before == 0 and after == 0

    def test_preserves_docs(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps({
            "version": 2,
            "docs": {"/a.md": HEX, "/b.md": HEX2},
            "ddl": ["ddl_legacy_a", HEX],
        }, ensure_ascii=False))
        sync_state_ddl(p, ["ddl_legacy_a"])
        d = json.loads(p.read_text())
        assert d["docs"] == {"/a.md": HEX, "/b.md": HEX2}
        assert d["ddl"] == [HEX]

    def test_sorted_output(self, tmp_path):
        p = tmp_path / "state.json"
        self._write_v2(p, ["c"*32, "a"*32, "b"*32, "ddl_legacy"])
        sync_state_ddl(p, ["ddl_legacy"])
        d = json.loads(p.read_text())
        assert d["ddl"] == sorted(["c"*32, "a"*32, "b"*32])
