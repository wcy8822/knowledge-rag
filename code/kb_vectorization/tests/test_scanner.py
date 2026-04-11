"""
本地知识库全量向量化自动化系统 - 扫描模块测试
版本: v1.0
日期: 2026-03-01
"""

import unittest
import os
import tempfile
import shutil

from core.config import Config
from core.scanner import FileScanner


class TestScanner(unittest.TestCase):
    """扫描模块测试"""

    def setUp(self):
        """测试前准备"""
        # 创建临时测试目录
        self.temp_dir = tempfile.mkdtemp()
        self.test_files = []

        # 创建测试文件
        self._create_test_files()

        # 创建配置
        self.config = Config()

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def _create_test_files(self):
        """创建测试文件"""
        # 创建 MD 文件
        md_file = os.path.join(self.temp_dir, "商户画像.md")
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write("# 商户画像\n\n商户数据需求...")
        self.test_files.append(md_file)

        # 创建 SQL 文件
        sql_file = os.path.join(self.temp_dir, "table_mapping.sql")
        with open(sql_file, 'w', encoding='utf-8') as f:
            f.write("-- 表映射\nCREATE TABLE test...")
        self.test_files.append(sql_file)

        # 创建子目录
        sub_dir = os.path.join(self.temp_dir, "subdir")
        os.makedirs(sub_dir)

        sub_file = os.path.join(sub_dir, "config.py")
        with open(sub_file, 'w', encoding='utf-8') as f:
            f.write("# 配置文件\n")
        self.test_files.append(sub_file)

    def test_scan_directory(self):
        """测试扫描目录"""
        scanner = FileScanner(self.config)
        result = scanner.scan([self.temp_dir])

        self.assertGreater(result.total_files, 0)
        self.assertEqual(len(result.files), 3)

    def test_file_type_identification(self):
        """测试文件类型识别"""
        scanner = FileScanner(self.config)
        result = scanner.scan([self.temp_dir])

        file_types = [f.type for f in result.files]
        self.assertIn(".md", file_types)
        self.assertIn(".sql", file_types)
        self.assertIn(".py", file_types)

    def test_recursive_scan(self):
        """测试递归扫描"""
        scanner = FileScanner(self.config)
        result = scanner.scan([self.temp_dir])

        # 检查是否扫描了子目录
        file_paths = [f.path for f in result.files]
        has_subdir_file = any("subdir" in p for p in file_paths)
        self.assertTrue(has_subdir_file)

    def test_export_csv(self):
        """测试导出 CSV"""
        scanner = FileScanner(self.config)
        result = scanner.scan([self.temp_dir])

        # 导出到临时文件
        csv_path = os.path.join(self.temp_dir, "test_scan.csv")
        exported_path = scanner.export_csv(result, csv_path)

        self.assertEqual(exported_path, csv_path)
        self.assertTrue(os.path.exists(csv_path))

        # 验证 CSV 内容
        with open(csv_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("路径,文件名,类型,分类", content)


if __name__ == '__main__':
    unittest.main()
