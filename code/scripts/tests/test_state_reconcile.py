#!/usr/bin/env python3
"""loki_state_reconcile 单元测试"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loki_state_reconcile import (  # noqa: E402
    content_fingerprint,
    is_32hex,
    read_file_content,
    load_state,
    save_state,
)


class TestIs32Hex:
    def test_valid(self):
        assert is_32hex("a" * 32) is True
        assert is_32hex("0123456789abcdef" * 2) is True

    def test_too_short(self):
        assert is_32hex("a" * 31) is False

    def test_too_long(self):
        assert is_32hex("a" * 33) is False

    def test_non_hex(self):
        assert is_32hex("a" * 31 + "z") is False

    def test_empty(self):
        assert is_32hex("") is False


class TestContentFingerprint:
    def test_deterministic(self):
        fp1 = content_fingerprint("/a.md", b"hello")
        fp2 = content_fingerprint("/a.md", b"hello")
        assert fp1 == fp2
        assert len(fp1) == 32

    def test_diff_path_diff_fp(self):
        fp1 = content_fingerprint("/a.md", b"same")
        fp2 = content_fingerprint("/b.md", b"same")
        assert fp1 != fp2

    def test_diff_content_diff_fp(self):
        fp1 = content_fingerprint("/a.md", b"v1")
        fp2 = content_fingerprint("/a.md", b"v2")
        assert fp1 != fp2

    def test_unicode(self):
        fp = content_fingerprint("/x.md", "知识库".encode("utf-8"))
        assert len(fp) == 32
        assert all(c in "0123456789abcdef" for c in fp)


class TestReadFileContent:
    def test_reads_bytes(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_bytes(b"hello world")
        assert read_file_content(str(f)) == b"hello world"

    def test_missing_returns_none(self, tmp_path):
        assert read_file_content(str(tmp_path / "nope.md")) is None

    def test_directory_returns_none(self, tmp_path):
        assert read_file_content(str(tmp_path)) is None


class TestLoadSaveState:
    def test_missing_file(self, tmp_path):
        docs, ddl = load_state(str(tmp_path / "nope.json"))
        assert docs == {}
        assert ddl == set()

    def test_round_trip(self, tmp_path):
        p = tmp_path / "state.json"
        state_path = Path(str(p))
        # can only test save_state with mocked state
        docs = {"/a.md": "fp1", "/b.md": "fp2"}
        ddl = {"ddl1", "ddl2"}
        save_state(docs, ddl, state_path)

        raw = json.loads(state_path.read_text("utf-8"))
        assert raw["version"] == 2
        assert raw["docs"] == docs
        assert sorted(raw["ddl"]) == sorted(ddl)

    def test_reload(self, tmp_path):
        p = tmp_path / "state.json"
        Path(str(p)).write_text(json.dumps({
            "version": 2,
            "docs": {"/a.md": "fp_a"},
            "ddl": ["d1"],
        }))
        docs, ddl = load_state(str(p))
        assert docs == {"/a.md": "fp_a"}
        assert ddl == {"d1"}

    def test_invalid_format_returns_empty(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("not json")
        docs, ddl = load_state(str(p))
        assert docs == {}
        assert ddl == set()

    def test_old_v1_format_returns_empty(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text(json.dumps(["v1", "list"]))
        docs, ddl = load_state(str(p))
        assert docs == {}
        assert ddl == set()
