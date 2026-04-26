#!/usr/bin/env python3
"""Benchmark 评测逻辑的单元测试"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loki_benchmark import evaluate


class TestEvaluate:
    def test_full_recall(self):
        hits = [
            {'file': '/path/to/FGW项目知识图谱.md', 'doc': 'some content'},
            {'file': '/path/to/l4_gravity_model_v3.py', 'doc': 'other content'},
        ]
        recall, chunk_hit = evaluate(hits, ["FGW项目知识图谱", "l4_gravity_model"], None)
        assert recall == 1.0

    def test_partial_recall(self):
        hits = [
            {'file': '/path/to/FGW项目知识图谱.md', 'doc': 'content'},
        ]
        recall, _ = evaluate(hits, ["FGW项目知识图谱", "missing_file"], None)
        assert recall == 0.5

    def test_zero_recall(self):
        hits = [
            {'file': '/path/to/unrelated.md', 'doc': 'content'},
        ]
        recall, _ = evaluate(hits, ["expected_file"], None)
        assert recall == 0.0

    def test_chunk_hit_found(self):
        hits = [
            {'file': 'test.md', 'doc': '橙化率计算公式 分子 = (日均汽油订单 * 30升)'},
        ]
        _, chunk_hit = evaluate(hits, ["test"], "日均汽油订单")
        assert chunk_hit is True

    def test_chunk_hit_not_found(self):
        hits = [
            {'file': 'test.md', 'doc': '不相关的内容'},
        ]
        _, chunk_hit = evaluate(hits, ["test"], "日均汽油订单")
        assert chunk_hit is False

    def test_chunk_hit_case_insensitive(self):
        hits = [
            {'file': 'test.md', 'doc': 'HNSW index repair'},
        ]
        _, chunk_hit = evaluate(hits, ["test"], "hnsw")
        assert chunk_hit is True

    def test_empty_hits(self):
        recall, chunk_hit = evaluate([], ["file1", "file2"], "keyword")
        assert recall == 0.0
        assert chunk_hit is False

    def test_empty_expected(self):
        recall, _ = evaluate([{'file': 'a.md', 'doc': ''}], [], None)
        assert recall == 0


class TestBenchmarkQueriesIntegrity:
    def test_all_queries_have_required_fields(self):
        from loki_benchmark import BENCHMARK_QUERIES
        for i, bq in enumerate(BENCHMARK_QUERIES):
            assert 'query' in bq, f"Query {i} missing 'query'"
            assert 'expected_files' in bq, f"Query {i} missing 'expected_files'"
            assert len(bq['expected_files']) > 0, f"Query {i} has empty expected_files"

    def test_all_queries_have_qa_fields(self):
        from loki_benchmark import BENCHMARK_QUERIES
        for i, bq in enumerate(BENCHMARK_QUERIES):
            assert 'qa_question' in bq, f"Query {i} missing 'qa_question'"
            assert 'qa_facts' in bq, f"Query {i} missing 'qa_facts'"
            assert len(bq['qa_facts']) > 0, f"Query {i} has empty qa_facts"

    def test_20_queries(self):
        from loki_benchmark import BENCHMARK_QUERIES
        assert len(BENCHMARK_QUERIES) == 20


class TestParseWeights:
    def test_empty_returns_default(self):
        from loki_benchmark import DEFAULT_WEIGHTS, parse_weights
        assert parse_weights("") == DEFAULT_WEIGHTS
        assert parse_weights(None) == DEFAULT_WEIGHTS

    def test_partial_override(self):
        from loki_benchmark import DEFAULT_WEIGHTS, parse_weights
        out = parse_weights("ddl=0.2")
        assert out["ddl_schema_bge_m3"] == 0.2
        assert out["doc_knowledge_bge_m3"] == DEFAULT_WEIGHTS["doc_knowledge_bge_m3"]

    def test_full_override(self):
        from loki_benchmark import parse_weights
        out = parse_weights("summaries=0.6,chunks=0.4,ddl=0.2")
        assert out["doc_knowledge_bge_m3"] == 0.6
        assert out["doc_knowledge_chunks"] == 0.4
        assert out["ddl_schema_bge_m3"] == 0.2

    def test_skip_invalid(self):
        from loki_benchmark import DEFAULT_WEIGHTS, parse_weights
        out = parse_weights("ddl=NaN_oops,chunks=0.5")
        assert out["ddl_schema_bge_m3"] == DEFAULT_WEIGHTS["ddl_schema_bge_m3"]
        assert out["doc_knowledge_chunks"] == 0.5

    def test_whitespace_tolerance(self):
        from loki_benchmark import parse_weights
        out = parse_weights(" summaries = 0.6 , chunks = 0.4 ")
        assert out["doc_knowledge_bge_m3"] == 0.6
        assert out["doc_knowledge_chunks"] == 0.4

    def test_unknown_key_passthrough(self):
        from loki_benchmark import parse_weights
        out = parse_weights("doc_knowledge_chunks=0.7")
        # 长 key 直接生效
        assert out["doc_knowledge_chunks"] == 0.7
