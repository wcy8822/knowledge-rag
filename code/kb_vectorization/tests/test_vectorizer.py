"""
本地知识库全量向量化自动化系统 - 向量化模块测试
版本: v1.0
日期: 2026-03-01
"""

import unittest
import os
import tempfile
import shutil

from core.config import Config
from core.vectorizer import Vectorizer, MarkdownParser, SQLParser


class TestMarkdownParser(unittest.TestCase):
    """Markdown 解析器测试"""

    def setUp(self):
        """测试前准备"""
        self.config = Config()
        self.parser = MarkdownParser(self.config)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_can_parse_md(self):
        """测试判断是否可以解析 MD"""
        self.assertTrue(self.parser.can_parse("test.md"))
        self.assertTrue(self.parser.can_parse("test.markdown"))
        self.assertFalse(self.parser.can_parse("test.txt"))

    def test_parse_md_file(self):
        """测试解析 MD 文件"""
        # 创建测试文件
        test_file = os.path.join(self.temp_dir, "test.md")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("# 标题1\n\n段落1\n\n## 标题2\n\n段落2")

        # 解析
        chunks = self.parser.parse(test_file)

        self.assertGreater(len(chunks), 0)

    def test_preprocessing(self):
        """测试预处理功能"""
        text = "# 标题\n\n**粗体**\n\n*斜体*"

        result = self.parser._preprocess(text)

        # 标记符号应该被移除
        self.assertNotIn("#", result)
        self.assertNotIn("**", result)


class TestSQLParser(unittest.TestCase):
    """SQL 解析器测试"""

    def setUp(self):
        """测试前准备"""
        self.config = Config()
        self.parser = SQLParser(self.config)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_can_parse_sql(self):
        """测试判断是否可以解析 SQL"""
        self.assertTrue(self.parser.can_parse("test.sql"))
        self.assertFalse(self.parser.can_parse("test.md"))

    def test_parse_sql_file(self):
        """测试解析 SQL 文件"""
        # 创建测试文件
        test_file = os.path.join(self.temp_dir, "test.sql")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("-- 这是注释\nSELECT * FROM table;\n\nINSERT INTO t VALUES (1);")

        # 解析
        chunks = self.parser.parse(test_file)

        self.assertGreater(len(chunks), 0)
        # 注释应该被移除
        self.assertNotIn("这是注释", " ".join(chunks))


class TestVectorizer(unittest.TestCase):
    """向量化器测试"""

    def setUp(self):
        """测试前准备"""
        self.config = Config()
        self.vectorizer = Vectorizer(self.config)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_vectorize_md_file(self):
        """测试向量化 MD 文件"""
        # 创建测试文件 - 内容超过 min_chunk_size (100)
        test_file = os.path.join(self.temp_dir, "test.md")
        test_content = """# 商户画像数据需求

## 1. 数据来源

商户画像数据主要来源于以下几个方面：

1. 交易数据 - 来自商户结算系统
2. 行为数据 - 来自商户APP和后台
3. 资质数据 - 来自商户入驻审核系统

## 2. 覆盖率计算

商户覆盖率 = 有画像的商户数 / 总商户数 × 100%

当前覆盖率约65%，目标是达到90%以上。

## 3. 准确率指标

- 基础信息准确率：95%
- 经营特征准确率：88%
- 需求预测准确率：82%

## 4. 优化方向

1. 增加数据来源
2. 优化算法模型
3. 加强数据校验
"""

        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_content)

        # 向量化
        chunks = self.vectorizer.vectorize_file(test_file)

        self.assertGreater(len(chunks), 0)

        # 验证向量
        for chunk in chunks:
            self.assertIsNotNone(chunk.id)
            self.assertEqual(len(chunk.vector), self.config.vector_dim)
            self.assertGreater(len(chunk.chunk_text), 0)

    def test_vectorize_batch(self):
        """测试批量向量化"""
        # 创建多个测试文件 - 内容超过 min_chunk_size (100)
        files = []
        base_content = """# 测试文档标题

这是一段测试内容，确保长度超过 min_chunk_size (100字符)。
商户画像数据需求来源于多个系统，包括交易数据、行为数据和资质数据。

## 数据来源详解

1. 交易数据来源于商户结算系统
2. 行为数据来自商户APP和后台管理平台
3. 资质数据由商户入驻审核系统提供
"""

        for i in range(3):
            test_file = os.path.join(self.temp_dir, f"test_{i}.md")
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(f"## 文件 {i}\n\n{base_content}")
            files.append(test_file)

        # 批量向量化
        chunks, stats = self.vectorizer.vectorize_batch(files, batch_size=2)

        self.assertGreater(len(chunks), 0)
        self.assertEqual(stats.total_files, 3)
        self.assertGreater(stats.processed_files, 0)

    def test_get_memory_usage(self):
        """测试获取内存使用"""
        mem = self.vectorizer.get_memory_usage()

        self.assertIsInstance(mem, float)
        self.assertGreater(mem, 0)


if __name__ == '__main__':
    unittest.main()
