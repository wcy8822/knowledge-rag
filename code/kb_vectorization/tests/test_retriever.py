"""
本地知识库全量向量化自动化系统 - 检索模块测试
版本: v1.0
日期: 2026-03-01
"""

import unittest

from core.config import Config
from core.base import VectorChunk
from core.storage import MetadataStore
from core.utils import md5_vector


class TestMetadataStore(unittest.TestCase):
    """元数据存储测试"""

    def setUp(self):
        """测试前准备"""
        self.config = Config()
        self.store = MetadataStore(self.config)

    def tearDown(self):
        """测试后清理"""
        self.store.clear()

    def test_add_vector(self):
        """测试添加向量元数据"""
        chunk = VectorChunk(
            id="test-1",
            file_path="/test/file.md",
            file_name="file.md",
            category="测试",
            chunk_index=0,
            chunk_text="测试内容",
            vector=[0.1, 0.2, 0.3]
        )

        self.store.add_vector(chunk)

        # 验证
        retrieved = self.store.get_vector("test-1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["file_name"], "file.md")

    def test_add_vectors(self):
        """测试批量添加"""
        chunks = []
        for i in range(5):
            chunk = VectorChunk(
                id=f"test-{i}",
                file_path=f"/test/file_{i}.md",
                file_name=f"file_{i}.md",
                category="测试",
                chunk_index=0,
                chunk_text=f"测试内容 {i}",
                vector=[0.1 * i, 0.2 * i, 0.3 * i]
            )
            chunks.append(chunk)

        self.store.add_vectors(chunks)

        # 验证
        for chunk in chunks:
            retrieved = self.store.get_vector(chunk.id)
            self.assertIsNotNone(retrieved)

    def test_get_vectors_by_file(self):
        """测试按文件获取向量"""
        # 添加多个向量
        chunks = []
        for i in range(3):
            chunk = VectorChunk(
                id=f"test-{i}",
                file_path="/test/file.md",
                file_name="file.md",
                category="测试",
                chunk_index=i,
                chunk_text=f"测试内容 {i}",
                vector=[0.1, 0.2, 0.3]
            )
            chunks.append(chunk)
            self.store.add_vector(chunk)

        # 按文件获取
        results = self.store.get_vectors_by_file("/test/file.md")

        self.assertEqual(len(results), 3)

    def test_delete_by_file(self):
        """测试删除文件向量"""
        # 添加向量
        chunk = VectorChunk(
            id="test-1",
            file_path="/test/file.md",
            file_name="file.md",
            category="测试",
            chunk_index=0,
            chunk_text="测试内容",
            vector=[0.1, 0.2, 0.3]
        )
        self.store.add_vector(chunk)

        # 删除
        count = self.store.delete_by_file("/test/file.md")

        self.assertEqual(count, 1)

        # 验证删除
        retrieved = self.store.get_vector("test-1")
        self.assertIsNone(retrieved)

    def test_get_stats(self):
        """测试获取统计"""
        # 添加向量
        for i in range(3):
            chunk = VectorChunk(
                id=f"test-{i}",
                file_path=f"/test/file_{i}.md",
                file_name=f"file_{i}.md",
                category="测试",
                chunk_index=0,
                chunk_text=f"测试内容 {i}",
                vector=[0.1, 0.2, 0.3]
            )
            self.store.add_vector(chunk)

        # 获取统计
        stats = self.store.get_stats()

        self.assertEqual(stats["total_vectors"], 3)
        self.assertEqual(stats["total_files"], 3)


if __name__ == '__main__':
    unittest.main()
