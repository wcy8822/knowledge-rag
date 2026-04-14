#!/usr/bin/env python3
"""MCP server 搜索逻辑的单元测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rag-mcp-server"))


class TestDedupKey:
    def test_basic_path(self):
        from server import _dedup_key
        assert _dedup_key("/Users/didi/Work/docs/test.md") == "test"

    def test_case_insensitive(self):
        from server import _dedup_key
        assert _dedup_key("FGW项目知识图谱.md") == "fgw项目知识图谱"

    def test_no_extension(self):
        from server import _dedup_key
        assert _dedup_key("dm_store_orange_rate") == "dm_store_orange_rate"

    def test_nested_path(self):
        from server import _dedup_key
        k1 = _dedup_key("/Users/didi/Work/docs/obsidian/1-Projects/test_file.md")
        k2 = _dedup_key("/Users/didi/Work/projects/知识库/test_file.py")
        assert k1 == k2 == "test_file"

    def test_chinese_filename(self):
        from server import _dedup_key
        assert _dedup_key("商户画像宽表_数据字典_20260323.md") == "商户画像宽表_数据字典_20260323"


class TestRrfMerge:
    def test_basic_merge(self):
        from server import _rrf_merge
        vector_hits = [
            {'path': '/a/doc1.md', 'text': 'v1', 'source': 'summaries',
             'heading': '', 'topic': '', 'domain': '', 'similarity': 0.8,
             'weighted_score': 0.4, 'weight': 0.5},
            {'path': '/a/doc2.md', 'text': 'v2', 'source': 'chunks',
             'heading': '', 'topic': '', 'domain': '', 'similarity': 0.7,
             'weighted_score': 0.35, 'weight': 0.5},
        ]
        bm25_hits = [
            {'file': '/b/doc2.md', 'bm25_score': 10.0, 'source': 'chunks',
             'heading': '', 'topic': '', 'domain': '', 'doc_preview': 'bm25 hit'},
            {'file': '/b/doc3.md', 'bm25_score': 8.0, 'source': 'summaries',
             'heading': '', 'topic': '', 'domain': '', 'doc_preview': 'bm25 only'},
        ]
        results = _rrf_merge(vector_hits, bm25_hits, k=60, top_n=5)

        assert len(results) >= 2
        # doc2 应该是 'both'（两路都命中）
        doc2 = [r for r in results if r['match_type'] == 'both']
        assert len(doc2) >= 1, "doc2 应该在两路都被命中"

    def test_empty_bm25(self):
        from server import _rrf_merge
        vector_hits = [
            {'path': '/a/doc1.md', 'text': 'v1', 'source': 's',
             'heading': '', 'topic': '', 'domain': '', 'similarity': 0.8,
             'weighted_score': 0.4, 'weight': 0.5},
        ]
        results = _rrf_merge(vector_hits, [], k=60, top_n=5)
        assert len(results) == 1
        assert results[0]['match_type'] == 'vector'

    def test_dedup_same_basename(self):
        """不同路径但同 basename 的文件应去重"""
        from server import _rrf_merge
        vector_hits = [
            {'path': '/path1/report.md', 'text': 'v1', 'source': 'summaries',
             'heading': '', 'topic': '', 'domain': '', 'similarity': 0.9,
             'weighted_score': 0.45, 'weight': 0.5},
        ]
        bm25_hits = [
            {'file': '/path2/report.md', 'bm25_score': 15.0, 'source': 'chunks',
             'heading': '', 'topic': '', 'domain': '', 'doc_preview': 'same file'},
        ]
        results = _rrf_merge(vector_hits, bm25_hits, k=60, top_n=5)
        assert len(results) == 1
        assert results[0]['match_type'] == 'both'

    def test_rrf_score_ordering(self):
        """双路命中的分数应高于单路"""
        from server import _rrf_merge
        vector_hits = [
            {'path': '/a/both_hit.md', 'text': '', 'source': 's',
             'heading': '', 'topic': '', 'domain': '', 'similarity': 0.8,
             'weighted_score': 0.4, 'weight': 0.5},
            {'path': '/a/vector_only.md', 'text': '', 'source': 's',
             'heading': '', 'topic': '', 'domain': '', 'similarity': 0.7,
             'weighted_score': 0.35, 'weight': 0.5},
        ]
        bm25_hits = [
            {'file': '/b/both_hit.md', 'bm25_score': 10.0, 'source': 'c',
             'heading': '', 'topic': '', 'domain': '', 'doc_preview': ''},
        ]
        results = _rrf_merge(vector_hits, bm25_hits, k=60, top_n=5)
        both = [r for r in results if r['match_type'] == 'both'][0]
        vector = [r for r in results if r['match_type'] == 'vector'][0]
        assert both['rrf_score'] > vector['rrf_score']


class TestNormalize:
    def test_zero_distance(self):
        from server import _normalize
        assert _normalize(0) == 1.0

    def test_max_distance(self):
        from server import _normalize
        assert _normalize(2.0) == 0.0

    def test_mid_distance(self):
        from server import _normalize
        assert _normalize(1.0) == 0.5
