#!/usr/bin/env python3
"""loki_state.StateV2 单元测试 (B.1)"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from loki_state import StateV2  # noqa: E402


FP_A = "a" * 32
FP_B = "b" * 32
FP_NEW = "n" * 32
MD5_X = "x" * 32
MD5_Y = "y" * 32


class TestEmptyAndBasic:
    def test_empty(self):
        s = StateV2()
        assert len(s) == 0
        assert not s.is_doc_done("/a.md", FP_A)
        assert not s.is_ddl_done(MD5_X)

    def test_mark_and_check(self):
        s = StateV2()
        s.mark_doc("/a.md", FP_A)
        assert s.is_doc_done("/a.md", FP_A)
        assert not s.is_doc_done("/a.md", FP_B)
        s.mark_ddl(MD5_X)
        assert s.is_ddl_done(MD5_X)

    def test_mtime_change_overwrites(self):
        """同 path 不同 fp 自动覆盖（v2 解决残留的核心特性）"""
        s = StateV2()
        s.mark_doc("/a.md", FP_A)
        s.mark_doc("/a.md", FP_NEW)
        assert s.docs == {"/a.md": FP_NEW}
        assert len(s.docs) == 1


class TestRoundTrip:
    def test_save_load(self, tmp_path):
        p = tmp_path / "state.json"
        s = StateV2()
        s.mark_doc("/a.md", FP_A)
        s.mark_doc("/b.md", FP_B)
        s.mark_ddl(MD5_X)
        s.save(p)

        s2 = StateV2.load(p)
        assert s2.docs == {"/a.md": FP_A, "/b.md": FP_B}
        assert s2.ddl == {MD5_X}

    def test_to_json_format(self):
        s = StateV2(docs={"/a.md": FP_A}, ddl={MD5_X})
        d = json.loads(s.to_json())
        assert d["version"] == 2
        assert d["docs"] == {"/a.md": FP_A}
        assert d["ddl"] == [MD5_X]


class TestLoad:
    def test_missing_file(self, tmp_path):
        s = StateV2.load(tmp_path / "nope.json")
        assert s.docs == {} and s.ddl == set()

    def test_corrupt_json(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("{bad json")
        s = StateV2.load(p)
        assert len(s) == 0

    def test_unknown_format(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps({"version": 999}))
        s = StateV2.load(p)
        assert len(s) == 0


class TestV1Migration:
    def test_v1_no_loader_safe_degrade(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps([FP_A, FP_B, MD5_X]))
        s = StateV2.load(p, chroma_loader=None)
        assert len(s) == 0

    def test_v1_with_loader(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps([FP_A, FP_B]))

        def loader():
            return ({"/a.md": FP_A, "/b.md": FP_B}, {MD5_X})

        s = StateV2.load(p, chroma_loader=loader)
        assert s.docs == {"/a.md": FP_A, "/b.md": FP_B}
        assert s.ddl == {MD5_X}

    def test_loader_raises_safe_degrade(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps([FP_A]))

        def loader():
            raise RuntimeError("chroma down")

        s = StateV2.load(p, chroma_loader=loader)
        assert len(s) == 0


class TestLen:
    def test_counts_docs_plus_ddl(self):
        s = StateV2(docs={"/a": FP_A, "/b": FP_B}, ddl={MD5_X, MD5_Y})
        assert len(s) == 4


class TestIsDocDoneMultiFp:
    """v3 兼容：is_doc_done(*fps) 任一命中即 True。"""

    def test_single_fp_matches(self):
        s = StateV2(docs={"/a.md": FP_A})
        assert s.is_doc_done("/a.md", FP_A)

    def test_single_fp_misses(self):
        s = StateV2(docs={"/a.md": FP_A})
        assert not s.is_doc_done("/a.md", FP_B)

    def test_two_fps_first_matches(self):
        # state 存的是 content_fp，pipeline 传 (content_fp, mtime_fp) 两个
        s = StateV2(docs={"/a.md": "content_fp"})
        assert s.is_doc_done("/a.md", "content_fp", "mtime_fp")

    def test_two_fps_second_matches(self):
        # state 仍是旧 mtime_fp，pipeline 传 (content_fp, mtime_fp)
        s = StateV2(docs={"/a.md": "old_mtime_fp"})
        assert s.is_doc_done("/a.md", "new_content_fp", "old_mtime_fp")

    def test_two_fps_neither_matches(self):
        s = StateV2(docs={"/a.md": "stored"})
        assert not s.is_doc_done("/a.md", "x", "y")

    def test_path_not_present(self):
        s = StateV2(docs={"/a.md": FP_A})
        assert not s.is_doc_done("/b.md", FP_A)

    def test_empty_fp_filtered(self):
        # fp="" 不应误命中（防御 fingerprint 计算失败）
        s = StateV2(docs={"/a.md": ""})
        assert not s.is_doc_done("/a.md", "")
        assert not s.is_doc_done("/a.md", "", "")


class TestPipelineEntryFilter:
    def test_filters_legacy_doc_X(self):
        from loki_state import _is_valid_pipeline_entry
        assert not _is_valid_pipeline_entry("doc_14", "README.md")
        assert not _is_valid_pipeline_entry("oil-algo-v1-3", "/a.md")

    def test_accepts_hex32_abs_path(self):
        from loki_state import _is_valid_pipeline_entry
        assert _is_valid_pipeline_entry(FP_A, "/Users/didi/x.md")

    def test_rejects_relative_path(self):
        from loki_state import _is_valid_pipeline_entry
        assert not _is_valid_pipeline_entry(FP_A, "x.md")
        assert not _is_valid_pipeline_entry(FP_A, "")
