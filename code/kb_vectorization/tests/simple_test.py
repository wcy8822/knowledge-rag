#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简化测试，避免框架内存问题"""

import os
import sys

# 设置项目路径
project_dir = '/Users/didi/Downloads/panth/kb_vectorization'
sys.path.insert(0, project_dir)

print("=" * 50)
print("简化测试 - 避免框架内存泄漏")
print("=" * 50)

from core.config import Config
from core.vectorizer import Vectorizer, MarkdownParser, SQLParser

config = Config()
print(f"配置加载成功: {config.system_name}")
print(f"min_chunk_size: {config.min_chunk_size}")
print(f"chunk_size: {config.chunk_size}")
print()

# 测试1: Markdown 解析
print("测试1: Markdown 解析器")
print("-" * 30)
parser = MarkdownParser(config)
content = """# Test

This is test content.

Paragraph 2 with sufficient text to ensure chunking.

Paragraph 3 with enough text to ensure it's over min_chunk_size (100 chars).

"""  # > 150 chars

print(f"测试内容长度: {len(content)} 字符")

# 预处理
processed = parser._preprocess(content)
print(f"预处理后长度: {len(processed)} 字符")

# 分块
chunks = parser._split_by_structure(processed)
print(f"分块数量: {len(chunks)}")
for i, chunk in enumerate(chunks[:5]):  # 只看前5个
    print(f"  块 {i}: {len(chunk)} 字符")

print()

# 测试2: 向量化器
print("测试2: 向量化器")
print("-" * 30)
vectorizer = Vectorizer(config)

# 创建足够大的测试文件（> 1000 字符）
test_content = """# 商户画像数据

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

1.增加数据来源
2.优化算法模型
3.加强数据校验

## 5. 扩展方向

1. 增加数据来源
2.优化算法模型
3.加强数据校验

"""  # > 1000 字符

print(f"测试内容长度: {len(test_content)} 字符")

import tempfile

# 创建测试文件
test_file = tempfile.mktemp(suffix='.md')
with open(test_file, 'w', encoding='utf-8') as f:
    f.write(test_content)

print(f"测试文件: {test_file}")
print(f"文件大小: {os.path.getsize(test_file)} 字节")
print()

# 向量化测试
try:
    chunks = vectorizer.vectorize_file(test_file)
    print(f"✅ 向量化成功: {len(chunks)} 个向量块")
    if chunks:
        print(f"第一个向量信息:")
        print(f"  ID: {chunks[0].id}")
        print(f"  文件名: {chunks[0].file_name}")
        print(f"  分类: {chunks[0].category}")
        print(f" 向量维度: {len(chunks[0].vector)}")
        print(f"  文本长度: {len(chunks[0].chunk_text)}")
        print()
except Exception as e:
    print(f"❌ 向量化失败: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
finally:
    # 清理
    os.unlink(test_file)

print()
print("=" * 50)
print("✅ 测试完成!")
print("=" * 50)
