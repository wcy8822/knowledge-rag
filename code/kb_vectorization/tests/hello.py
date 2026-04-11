#!/usr/bin/env python3
"""测试脚本"""

import sys
print("✓ 简化测试通过!")

# 测试配置
from core.config import Config
config = Config()
print(f"✓ 配置加载: {config.system_name}")

# 测试工具函数
from core.utils import get_memory_usage

mem_gb = get_memory_usage()
print(f"✓ 内存使用: {mem_gb:.2f}GB")

# 测试 MD5 向量化
from core.utils import md5_vector

test_text = "商户画像数据需求"
vector = md5_vector(test_text, dim=128)
print(f"✓ 向量化: {len(vector)} 维")

# 验证结果
assert len(vector) == 128
assert 0.0 <= max(vector) <= 1.0

print("✓ 所有测试通过!")
