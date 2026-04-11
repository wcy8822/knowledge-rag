#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest
import tempfile
import os

import sys
sys.path.insert(0, '/Users/didi/Downloads/panth/kb_vectorization')

from core.config import Config
from core.vectorizer import Vectorizer, MarkdownParser, SQLParser


class TestVectorizationFix(unittest.TestCase):
    """向量化修复测试"""

    def setUp(self):
        """测试前准备"""
        self.config = Config()
        self.temp_dir = tempfile.mkdtemp()
        self.vectorizer = Vectorizer(self.config)

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)

    def test_markdown_parser_long_content(self):
        """测试 Markdown 解析器 - 长内容"""
        parser = MarkdownParser(self.config)

        # 创建长测试文件（>100 字符）
        test_file = os.path.join(self.temp_dir, "long_content.md")
        long_content = "# Test\n\n" + "Content " * 40 + "\n\nMore data here.\n"

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(long_content)

        # 解析
        chunks = parser.parse(test_file)
        self.assertGreater(len(chunks), 0)

        # 验证
        for chunk in chunks:
            self.assertGreater(len(chunk), 0)

    def test_sql_parser(self):
        """测试 SQL 解析器"""
        parser = SQLParser(self.config)

        # 创建 SQL 测试文件
        test_file = os.path.join(self.temp_dir, "test.sql")
        sql_content = """
-- Test SQL
CREATE TABLE test (
    id INT,
    name VARCHAR(100)
);
INSERT INTO test VALUES (1, 'test');
"""

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(sql_content)

        # 解析
        chunks = parser.parse(test_file)
        self.assertGreater(len(chunks), 0)

    def test_vectorize_md(self):
        """测试 MD 文件向量化"""
        parser = MarkdownParser(self.config)

        # 创建足够大的 MD 文件（>100 字符）
        test_file = os.path.join(self.temp_dir, "test.md")
        test_content = """# Merchant Profile

## 1. Data Sources

Merchant profile data comes from several sources:

1. Transaction data - from merchant settlement system
2. Behavior data - from merchant APP and backend
3. Qualification data - from merchant review system

## 2. Coverage Calculation

Merchant coverage = merchants with profiles / total merchants * 100%

Current coverage about 65%, target is 90%+.

## 3. Accuracy Metrics

- Basic info accuracy: 95%
- Business feature accuracy: 88%
- Demand prediction accuracy: 82%
"""

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)

        # 向量化
        chunks = self.vectorizer.vectorize_file(test_file)

        self.assertGreater(len(chunks), 0)
        self.assertEqual(len(chunks[0].vector), self.config.vector_dim)
        self.assertGreater(len(chunks[0].chunk_text), 0)

    def test_vectorize_batch(self):
        """测试批量向量化"""
        files = []

        for i in range(3):
            test_file = os.path.join(self.temp_dir, f"test_{i}.md")

            # 创建足够大的内容
            test_content = f"# Test File {i}\n\n" + "Content " * 40 + "\n\n"
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(test_content)
            files.append(test_file)

        # 批量向量化
        chunks, stats = self.vectorizer.vectorize_batch(files, batch_size=2)

        self.assertGreater(len(chunks), 0)
        self.assertEqual(stats.total_files, 3)
        self.assertEqual(stats.processed_files, 3)


if __name__ == '__main__':
    # 运行测试
    suite = unittest.TestLoader().loadTestsFromTestCase(TestVectorizationFix)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出结果
    print()
    print("=" * 60)
    print("向量化修复测试结果")
    print("=" * 60)
    print(f"总用例数: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"通过率: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    print("=" * 60)

    sys.exit(0 if result.wasSuccessful() else 1)
