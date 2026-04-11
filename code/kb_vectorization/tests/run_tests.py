#!/usr/bin/env python3
"""
本地知识库全量向量化自动化系统 - 测试运行脚本
版本: v1.0
日期: 2026-03-01
"""

import sys
import os
import unittest
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 导入测试模块
import test_config
import test_scanner
import test_vectorizer
import test_retriever


def run_tests():
    """运行所有测试"""
    print("=" * 60)
    print("  本地知识库全量向量化自动化系统 - 测试套件")
    print("=" * 60)
    print()

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试模块
    suite.addTests(loader.loadTestsFromModule(test_config))
    suite.addTests(loader.loadTestsFromModule(test_scanner))
    suite.addTests(loader.loadTestsFromModule(test_vectorizer))
    suite.addTests(loader.loadTestsFromModule(test_retriever))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    start_time = datetime.now()
    result = runner.run(suite)
    end_time = datetime.now()

    # 打印总结
    print()
    print("=" * 60)
    print("  测试结果总结")
    print("=" * 60)
    print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {(end_time - start_time).total_seconds():.2f} 秒")
    print()
    print(f"总用例数: {result.testsRun}")
    print(f"成功用例: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败用例: {len(result.failures)}")
    print(f"错误用例: {len(result.errors)}")
    print(f"通过率: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100:.1f}%")
    print("=" * 60)

    # 返回退出码
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
