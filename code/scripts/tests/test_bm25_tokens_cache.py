#!/usr/bin/env python3
"""bm25_tokens_cache 单元测试 (H.1)"""

import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bm25_tokens_cache import (  # noqa: E402
    compute_sig,
    load_cache,
    lookup,
)


class TestComputeSig:
    def test_basic(self):
        s = compute_sig("hello")
        assert isinstance(s, str)
        assert len(s) == 16
        assert all(c in "0123456789abcdef" for c in s)

    def test_deterministic(self):
        assert compute_sig("xyz") == compute_sig("xyz")

    def test_different_inputs(self):
        assert compute_sig("a") != compute_sig("b")

    def test_empty(self):
        assert len(compute_sig("")) == 16

    def test_none_safe(self):
        assert len(compute_sig(None)) == 16

    def test_chinese(self):
        s = compute_sig("商户画像标签")
        assert len(s) == 16

    def test_long_text(self):
        s = compute_sig("a" * 100000)
        assert len(s) == 16


class TestLoadCache:
    def _write_pickle(self, p: Path, data: dict):
        with open(p, "wb") as f:
            pickle.dump(data, f)

    def test_missing_file(self, tmp_path):
        assert load_cache(tmp_path / "nope.pkl") == {}

    def test_corrupt_file(self, tmp_path):
        p = tmp_path / "x.pkl"
        p.write_bytes(b"not a valid pickle")
        assert load_cache(p) == {}

    def test_old_format_no_sigs(self, tmp_path):
        """旧版 pickle 没有 doc_text_sigs → 返回空 cache（首跑）"""
        p = tmp_path / "old.pkl"
        self._write_pickle(p, {
            "doc_ids": ["a"*32],
            "corpus_tokens": [["hello"]],
            "build_time": "2026-04-25",
        })
        assert load_cache(p) == {}

    def test_length_mismatch_returns_empty(self, tmp_path):
        p = tmp_path / "bad.pkl"
        self._write_pickle(p, {
            "doc_ids": ["a"*32, "b"*32],
            "doc_text_sigs": ["sig1"],
            "corpus_tokens": [["a"], ["b"]],
        })
        assert load_cache(p) == {}

    def test_full_round_trip(self, tmp_path):
        p = tmp_path / "ok.pkl"
        self._write_pickle(p, {
            "doc_ids": ["a"*32, "b"*32],
            "doc_text_sigs": ["sig_aaa", "sig_bbb"],
            "corpus_tokens": [["hello", "world"], ["foo", "bar"]],
            "build_time": "2026-04-26",
            "doc_count": 2,
        })
        cache = load_cache(p)
        assert len(cache) == 2
        assert cache[("a"*32, "sig_aaa")] == ["hello", "world"]
        assert cache[("b"*32, "sig_bbb")] == ["foo", "bar"]

    def test_skip_empty_id_or_sig(self, tmp_path):
        p = tmp_path / "ok.pkl"
        self._write_pickle(p, {
            "doc_ids": ["a"*32, "", "c"*32],
            "doc_text_sigs": ["s1", "s2", ""],
            "corpus_tokens": [["t1"], ["t2"], ["t3"]],
        })
        cache = load_cache(p)
        # 中间 doc_id 空 + 末尾 sig 空 → 都被跳过
        assert len(cache) == 1
        assert cache[("a"*32, "s1")] == ["t1"]


class TestLookup:
    def test_hit(self):
        cache = {("a"*32, "sig"): ["x", "y"]}
        assert lookup(cache, "a"*32, "sig") == ["x", "y"]

    def test_miss_wrong_id(self):
        cache = {("a"*32, "sig"): ["x"]}
        assert lookup(cache, "b"*32, "sig") is None

    def test_miss_wrong_sig(self):
        cache = {("a"*32, "sig1"): ["x"]}
        assert lookup(cache, "a"*32, "sig2") is None

    def test_empty_cache(self):
        assert lookup({}, "a"*32, "sig") is None
