#!/usr/bin/env python3
"""BM25 索引构建器的单元测试"""
import sys, os, pickle, tempfile
from pathlib import Path

# 加载被测模块
sys.path.insert(0, str(Path(__file__).parent.parent))

import jieba
from loki_bm25_index import tokenize, search_bm25, USERDICT

# 初始化 jieba 词典
jieba.load_userdict(USERDICT)


class TestTokenize:
    def test_basic_chinese(self):
        tokens = tokenize("橙化率计算公式")
        assert "橙化率" in tokens
        assert "计算公式" in tokens or "计算" in tokens

    def test_stopwords_removed(self):
        tokens = tokenize("这是一个测试的文本")
        for sw in ["这", "是", "一", "个", "的"]:
            assert sw not in tokens

    def test_custom_dict_terms(self):
        """自定义词典中的术语不应被切碎"""
        tokens = tokenize("BGE-M3模型下载")
        assert "bge-m3" in tokens  # tokenize 做了 lower
        tokens2 = tokenize("S1S2标签ETL")
        assert "s1s2" in tokens2

    def test_empty_input(self):
        assert tokenize("") == []
        assert tokenize("   ") == []

    def test_english_mixed(self):
        tokens = tokenize("ChromaDB HNSW index")
        assert "chromadb" in tokens
        assert "hnsw" in tokens


class TestSearchBm25:
    @classmethod
    def setup_class(cls):
        """构建一个小型测试索引"""
        from rank_bm25 import BM25Okapi

        docs = [
            "橙化率计算公式 分子是DD纯汽油消费量 分母是全国汽油消费量",
            "L4引力模型 城市权重参数 ALPHA vehicle 0.45",
            "发改委搁浅规则 调价幅度低于50元每吨不作调整",
            "ChromaDB HNSW index 修复方法 pickle 重建",
            "BGE-M3 模型下载路径 1024维 embedding",
        ]
        corpus_tokens = [tokenize(d) for d in docs]
        bm25 = BM25Okapi(corpus_tokens)

        cls.index_data = {
            'bm25': bm25,
            'doc_ids': [f'doc_{i}' for i in range(len(docs))],
            'doc_meta': [
                {'source': 'test', 'file': f'test_doc_{i}.md',
                 'heading': '', 'topic': '', 'domain': 'test',
                 'doc_preview': docs[i]}
                for i in range(len(docs))
            ],
            'corpus_tokens': corpus_tokens,
        }

    def test_basic_search(self):
        results = search_bm25(self.index_data, "橙化率", top_k=3)
        assert len(results) > 0
        assert results[0]['file'] == 'test_doc_0.md'

    def test_search_english_term(self):
        results = search_bm25(self.index_data, "HNSW ChromaDB", top_k=3)
        assert len(results) > 0
        assert 'test_doc_3.md' in results[0]['file']

    def test_search_no_results(self):
        results = search_bm25(self.index_data, "完全无关的查询词xyz", top_k=3)
        # 可能返回结果但分数极低，或者空
        # BM25 对不存在的词返回 0 分
        for r in results:
            assert r['bm25_score'] >= 0

    def test_dedup_by_file(self):
        results = search_bm25(self.index_data, "橙化率", top_k=10)
        files = [r['file'] for r in results]
        assert len(files) == len(set(files)), "搜索结果不应有重复文件"

    def test_top_k_limit(self):
        results = search_bm25(self.index_data, "模型", top_k=2)
        assert len(results) <= 2

    def test_empty_query(self):
        results = search_bm25(self.index_data, "", top_k=3)
        assert results == []


class TestIndexPersistence:
    def test_pickle_roundtrip(self):
        """索引可以 pickle 序列化和反序列化"""
        from rank_bm25 import BM25Okapi
        corpus = [
            ["橙化率", "计算", "公式", "汽油"],
            ["引力模型", "城市", "权重"],
            ["搁浅", "规则", "发改委"],
        ]
        bm25 = BM25Okapi(corpus)
        index_data = {'bm25': bm25, 'doc_ids': ['a', 'b', 'c'],
                      'doc_meta': [{'file': 'a.md'}, {'file': 'b.md'}, {'file': 'c.md'}],
                      'doc_count': 3}

        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as f:
            pickle.dump(index_data, f)
            tmp_path = f.name

        try:
            with open(tmp_path, 'rb') as f:
                loaded = pickle.load(f)
            assert loaded['doc_count'] == 3
            assert len(loaded['doc_ids']) == 3
            scores = loaded['bm25'].get_scores(["橙化率"])
            assert scores[0] > 0, "查询词命中的文档应有正分"
        finally:
            os.unlink(tmp_path)
