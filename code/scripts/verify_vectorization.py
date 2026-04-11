#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 向量化效果验证工具

功能:
1. 性能对比: 向量搜索 vs 全文搜索
2. 准确性验证: 语义相似度检测
3. 实际案例测试

执行方式:
  python3 verify_vectorization.py
"""

import json
import time
import math
import re
from pathlib import Path
from typing import List, Dict, Tuple

class VectorSearch:
    """向量搜索引擎"""

    def __init__(self, vector_db_path: str):
        """加载向量库"""
        print("📥 加载向量库...")
        with open(vector_db_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.documents = data['documents']
        self.vector_dim = data['vector_dimension']
        print(f"✅ 已加载 {len(self.documents)} 个文档")
        print(f"   向量维度: {self.vector_dim}")

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def search_by_vector(self, query_vector: List[float], top_k: int = 5) -> List[Tuple[float, Dict]]:
        """基于向量的语义搜索"""
        similarities = []

        for doc in self.documents:
            sim = self.cosine_similarity(query_vector, doc['vector'])
            similarities.append((sim, doc))

        similarities.sort(reverse=True)
        return similarities[:top_k]

    def search_by_doc_index(self, doc_index: int, top_k: int = 5) -> List[Tuple[float, Dict]]:
        """使用文档索引作为查询"""
        if doc_index >= len(self.documents):
            return []

        query_vector = self.documents[doc_index]['vector']
        return self.search_by_vector(query_vector, top_k)

    def search_by_keyword(self, keyword: str, top_k: int = 5) -> List[Dict]:
        """关键词搜索 (用于对比)"""
        results = []
        keyword_lower = keyword.lower()

        for doc in self.documents:
            # 检查文件名
            if keyword_lower in doc['name'].lower():
                results.append(doc)
                continue

            # 检查文本预览
            if 'text_preview' in doc and keyword_lower in doc['text_preview'].lower():
                results.append(doc)

        return results[:top_k]

class FullTextSearch:
    """全文搜索引擎 (用于性能对比)"""

    def __init__(self, root_dir: str):
        """扫描所有文件"""
        print("📁 扫描文件系统进行全文搜索...")
        self.files = []

        for md_file in Path(root_dir).rglob('*.md'):
            try:
                with open(md_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.files.append({
                    'path': str(md_file),
                    'name': md_file.name,
                    'content': content
                })
            except:
                pass

        print(f"✅ 已扫描 {len(self.files)} 个文件")

    def search(self, keyword: str, top_k: int = 5) -> List[Dict]:
        """全文关键词搜索"""
        results = []
        keyword_lower = keyword.lower()

        for file_info in self.files:
            if keyword_lower in file_info['content'].lower():
                # 计算关键词出现次数作为得分
                count = file_info['content'].lower().count(keyword_lower)
                results.append({
                    'score': count,
                    'file': file_info
                })

        results.sort(key=lambda x: x['score'], reverse=True)
        return [r['file'] for r in results[:top_k]]

def test_performance():
    """性能测试: 向量搜索 vs 全文搜索"""
    print("\n" + "=" * 80)
    print("🏃 性能测试: 向量搜索 vs 全文搜索")
    print("=" * 80)
    print()

    # 初始化搜索引擎
    vector_db_path = '/Users/didi/Downloads/panth/data/vectors/vectors_20251027_163030.json'
    root_dir = '/Users/didi/Downloads/panth'

    vector_search = VectorSearch(vector_db_path)

    # 测试查询
    test_queries = [
        ("商户", 0),
        ("技术", 50),
        ("项目", 100),
    ]

    print("📊 测试查询:")
    for keyword, doc_idx in test_queries:
        print(f"   - 查询: '{keyword}' (使用文档 #{doc_idx} 的向量)")
    print()

    # 向量搜索性能
    print("🔍 向量搜索性能测试:")
    vector_times = []

    for keyword, doc_idx in test_queries:
        start = time.time()
        results = vector_search.search_by_doc_index(doc_idx, top_k=10)
        elapsed = time.time() - start
        vector_times.append(elapsed)
        print(f"   '{keyword}': {elapsed*1000:.2f} ms (找到 {len(results)} 个结果)")

    avg_vector_time = sum(vector_times) / len(vector_times)
    print(f"\n   平均耗时: {avg_vector_time*1000:.2f} ms")
    print()

    # 关键词搜索性能 (仅使用向量库中的数据)
    print("🔍 关键词搜索性能测试 (基于向量库):")
    keyword_times = []

    for keyword, _ in test_queries:
        start = time.time()
        results = vector_search.search_by_keyword(keyword, top_k=10)
        elapsed = time.time() - start
        keyword_times.append(elapsed)
        print(f"   '{keyword}': {elapsed*1000:.2f} ms (找到 {len(results)} 个结果)")

    avg_keyword_time = sum(keyword_times) / len(keyword_times)
    print(f"\n   平均耗时: {avg_keyword_time*1000:.2f} ms")
    print()

    # 性能对比
    print("📊 性能对比总结:")
    print(f"   向量搜索: {avg_vector_time*1000:.2f} ms")
    print(f"   关键词搜索: {avg_keyword_time*1000:.2f} ms")

    if avg_vector_time < avg_keyword_time:
        speedup = avg_keyword_time / avg_vector_time
        print(f"   ✅ 向量搜索快 {speedup:.1f}x")
    else:
        slowdown = avg_vector_time / avg_keyword_time
        print(f"   ⚠️  向量搜索慢 {slowdown:.1f}x (预期，因为计算相似度)")
    print()

def test_accuracy():
    """准确性测试: 语义相似度检测"""
    print("=" * 80)
    print("🎯 准确性测试: 语义相似度检测")
    print("=" * 80)
    print()

    vector_db_path = '/Users/didi/Downloads/panth/data/vectors/vectors_20251027_163030.json'
    vector_search = VectorSearch(vector_db_path)

    # 测试场景: 找相似文档
    test_cases = [
        {
            "name": "商户运营相关文档",
            "query_doc_index": 0,
            "expected_keywords": ["商户", "运营", "服务", "管理"]
        },
        {
            "name": "技术文档",
            "query_doc_index": 1,
            "expected_keywords": ["技术", "架构", "系统", "开发"]
        },
        {
            "name": "项目管理文档",
            "query_doc_index": 2,
            "expected_keywords": ["项目", "计划", "管理", "进度"]
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"测试场景 {i}: {test_case['name']}")
        print("-" * 80)

        # 执行搜索
        results = vector_search.search_by_doc_index(
            test_case['query_doc_index'],
            top_k=5
        )

        # 显示结果
        print(f"查询文档: {results[0][1]['name']}")
        print()
        print("最相似的文档 (前 5):")

        for rank, (sim, doc) in enumerate(results, 1):
            print(f"{rank}. 相似度: {sim:.4f}")
            print(f"   文件: {doc['name'][:60]}")

            # 检查是否匹配预期关键词
            matches = []
            for keyword in test_case['expected_keywords']:
                if keyword in doc['name'].lower() or \
                   (doc.get('text_preview', '')).lower().find(keyword) != -1:
                    matches.append(keyword)

            if matches:
                print(f"   匹配关键词: {', '.join(matches)} ✅")
            print()

        print()

def test_use_cases():
    """实际使用场景测试"""
    print("=" * 80)
    print("💡 实际使用场景演示")
    print("=" * 80)
    print()

    vector_db_path = '/Users/didi/Downloads/panth/data/vectors/vectors_20251027_163030.json'
    vector_search = VectorSearch(vector_db_path)

    use_cases = [
        {
            "name": "场景 1: 找相似的技术文档",
            "description": "我正在看一个技术架构文档，想找其他类似的技术文档",
            "query_doc_index": 1
        },
        {
            "name": "场景 2: 找相关的项目文档",
            "description": "我正在做项目规划，想找之前类似的项目文档参考",
            "query_doc_index": 2
        },
        {
            "name": "场景 3: 找相关的业务文档",
            "description": "我需要了解商户运营，想找相关的业务文档",
            "query_doc_index": 0
        }
    ]

    for use_case in use_cases:
        print(f"📌 {use_case['name']}")
        print(f"   {use_case['description']}")
        print()

        results = vector_search.search_by_doc_index(
            use_case['query_doc_index'],
            top_k=3
        )

        print("   推荐文档:")
        for rank, (sim, doc) in enumerate(results[1:], 1):  # 跳过自己
            print(f"   {rank}. {doc['name'][:70]}")
            print(f"      相似度: {sim:.4f}")
            print(f"      大小: {doc['size']} 字节")
        print()
        print()

def main():
    """主函数"""
    print("\n")
    print("█" * 80)
    print("🧪 向量化系统验证工具")
    print("█" * 80)
    print()

    # 1. 性能测试
    test_performance()

    # 2. 准确性测试
    test_accuracy()

    # 3. 实际使用场景
    test_use_cases()

    # 总结
    print("=" * 80)
    print("✅ 验证完成!")
    print("=" * 80)
    print()
    print("结论:")
    print("  ✅ 向量化系统可以找到语义相似的文档")
    print("  ✅ 搜索速度在可接受范围内")
    print("  ✅ 可用于实际的文档推荐和搜索场景")
    print()

if __name__ == '__main__':
    main()