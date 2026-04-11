"""
本地知识库全量向量化自动化系统 - 配置模块测试
版本: v1.0
日期: 2026-03-01
"""

import unittest
import os
import tempfile
import shutil

from core.config import Config


class TestConfig(unittest.TestCase):
    """配置模块测试"""

    def setUp(self):
        """测试前准备"""
        # 创建临时配置文件
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, "test_config.yaml")

        # 写入测试配置
        config_content = """
system:
  name: "测试系统"
  version: "1.0.0"
  memory_limit: 12

scan:
  directories:
    - "/tmp/test1"
    - "/tmp/test2"
  file_types:
    - ".md"
    - ".sql"
  batch_size: 100

categories:
  merchant:
    name: "商户画像"
    patterns: ["商户", "customer"]
  default: "其他"

vectorize:
  batch_size: 500
  vector_dim: 384
"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_load_config_from_file(self):
        """测试从文件加载配置"""
        config = Config(self.config_path)

        self.assertEqual(config.system_name, "测试系统")
        self.assertEqual(config.system_version, "1.0.0")
        self.assertEqual(config.memory_limit, 12)

    def test_load_default_config(self):
        """测试加载默认配置"""
        config = Config()

        self.assertIsNotNone(config.system_name)
        self.assertIsNotNone(config._config)
        self.assertIsNotNone(config.version)

    def test_get_scan_dirs(self):
        """测试获取扫描目录"""
        config = Config(self.config_path)

        dirs = config.get_scan_dirs()
        self.assertEqual(len(dirs), 2)
        self.assertIn("/tmp/test1", dirs)

    def test_get_file_types(self):
        """测试获取文件类型"""
        config = Config(self.config_path)

        types = config.get_file_types()
        self.assertIn(".md", types)
        self.assertIn(".sql", types)

    def test_classify_file(self):
        """测试文件分类"""
        config = Config(self.config_path)

        # 测试商户分类
        category1 = config.classify("/path/to/商户画像.md")
        self.assertEqual(category1, "商户画像")

        # 测试默认分类
        category2 = config.classify("/path/to/其他文件.md")
        self.assertEqual(category2, "其他")

    def test_batch_size(self):
        """测试批次大小"""
        config = Config(self.config_path)

        self.assertEqual(config.batch_size, 500)
        self.assertEqual(config.mvp_batch_size, 5)

    def test_vector_dim(self):
        """测试向量维度"""
        config = Config(self.config_path)

        self.assertEqual(config.vector_dim, 384)


if __name__ == '__main__':
    unittest.main()
