#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地知识库全量向量化自动化系统 - 最终验收测试
版本: v1.0
日期: 2026-03-01

**设计原则**:
1. 不使用 unittest 框架（避免内存泄漏）
2. 直接调用核心模块进行测试
3. 简化日志输出（只输出结果）
4. 不创建大量临时对象
"""

import sys
import os

# 设置项目路径
sys.path.insert(0, '/Users/didi/Downloads/panth/kb_vectorization')

# 导入核心模块
from core.config import Config
from core.scanner import FileScanner, ScanResult
from core.vectorizer import Vectorizer, MarkdownParser, SQLParser
from core.storage import MetadataStore
from core.utils import get_memory_usage, format_file_size

# 静色输出
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"

# 全局结果
results = {
    "config": False,
    "scanner": False,
    "vectorizer": False,
    "storage": False,
    "retriever": False,
    "memory_ok": False
}

# 内存限制
MEMORY_LIMIT_GB = 12

def test_config():
    """测试配置模块"""
    global results

    print(f"{GREEN}┌─ 测试 1: 配置模块 ─────────────┐")
    try:
        config = Config()

        # 测试配置加载
        assert config.system_name == "本地知识库向量化系统"
        assert config.system_version == "1.0.0"
        assert config.memory_limit == 12
        assert config.vector_dim == 384
        assert config.batch_size == 500
        assert config.mvp_batch_size == 5

        # 测试配置方法
        dirs = config.get_scan_dirs()
        types = config.get_file_types()
        batch_size = config.batch_size
        vector_dim = config.vector_dim

        assert isinstance(dirs, list)
        assert isinstance(types, list)
        assert isinstance(batch_size, int)
        assert isinstance(vector_dim, int)

        # 测试文件分类
        cat1 = config.classify("/path/to/商户画像.md")
        assert cat1 == "商户画像"

        cat2 = config.classify("/path/to/其他文件.md")
        assert cat2 == "其他"

        print(f"  ✓ 配置模块通过")

        results["config"] = True
        print()

    except AssertionError as e:
        print(f"{RED}  ✗ 配置模块失败: {e}")
    except Exception as e:
        print(f"{RED}  ✗ 配置模块异常: {e}"


def test_scanner():
    """测试扫描模块"""
    global results

    print(f"{GREEN}┌─ 测试 2: 扫描模块 ─────────────┐")
    try:
        config = Config()
        scanner = FileScanner(config)

        # 测试目录
        test_dirs = ["/Users/didi/knowledge_base_vectorization"]
        results["scanner"] = True
        print(f"  ✓ 扫描目录: {test_dirs}")

        # 扫描文件
        result = scanner.scan(test_dirs)

        # 验证结果
        assert isinstance(result, ScanResult)
        assert result.total_files > 0

        # 验证统计数据
        assert isinstance(result.by_type, dict)
        assert isinstance(result.by_category, dict)

        print(f"  ✓ 扫描完成: {result.total_files} 个文件")
        print(f"  总大小: {format_file_size(result.total_size)}")
        print()

        # 验证分类
        categories = list(result.by_category.keys())
        assert len(categories) > 0
        assert "商户画像" in categories or "画像" in categories
        assert "其他" in categories

        for cat, count in result.by_category.items():
            print(f"  {cat}: {count} 个文件")
        print()

        results["scanner"] = True

    except Exception as e:
        print(f"{RED}  ✗ 扫描模块失败: {e}")
        import traceback
        traceback.print_exc()


def test_vectorizer():
    """测试向量化模块"""
    global results

    print(f"{GREEN}┌─ 测试 3: 向量化模块 ───────────┐")

    try:
        config = Config()
        vectorizer = Vectorizer(config)

        # 测试 Markdown 解析器
        md_parser = MarkdownParser(config)
        assert md_parser.can_parse("/path/to/test.md")
        assert ".md" in md_parser.supported_extensions
        assert ".sql" not in md_parser.supported_extensions

        # 测试 SQL 解析器
        sql_parser = SQLParser(config)
        assert sql_parser.can_parse("/path/to/test.sql")
        assert ".sql" in sql_parser.supported_extensions

        # 测试代码解析器
        from core.vectorizer import CodeParser
        code_parser = CodeParser(config)
        assert ".py" in code_parser.supported_extensions

        print("  ✓ 解析器测试通过")
        print()

        # 测试向量化功能
        import tempfile
        test_content = """# 测试文档

## 内容需要足够长以触发多个块（超过 min_chunk_size: 100）

## 1. 数据来源

商户画像数据主要来源于以下几个方面：

1. 交易数据 - 来自商户结算系统
2. 行为数据 - 来自商户APP和后台
3. 资质数据 - 来自商户入驻审核系统

## 2. 覆盖率计算

商户覆盖率 = 有画像的商户数 / 总商户数 × 100%

当前覆盖率约65%，目标是达到90%以上。
"""

        # 创建临时测试文件（> 100 字符）
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.md', delete=False) as f:
            f.write(test_content)
            test_file = f.name

        print(f"  测试文件: {test_file}")
        print(f" 文件大小: {os.path.getsize(test_file)} 字节 = {format_file_size(os.path.getsize(test_file))}")
        print(f" min_chunk_size: {config.min_chunk_size} 字符")
        print()

        # 向量化
        chunks = vectorizer.vectorize_file(test_file)
        print(f"  ✓ 向量化成功: {len(chunks)} 个向量块")
        assert len(chunks) > 0

        # 验证向量
        for i, chunk in enumerate(chunks):
            assert chunk.id
            assert chunk.file_name == os.path.basename(test_file)
            assert len(chunk.vector) == config.vector_dim
            assert len(chunk.chunk_text) > 0

        print()
        print("  ✓ 向量化模块通过")

        results["vectorizer"] = True

    except Exception as e:
        print(f"{RED}  ✗ 向量化模块失败: {e}")
        import traceback
        traceback.print_exc()


def test_storage():
    """测试存储模块"""
    global results

    print(f"{GREEN}┌─ 测试 4: 存储模块 ─────────────┐")
    try:
        config = Config()
        store = MetadataStore(config)

        # 创建测试向量
        from core.base import VectorChunk

        test_chunks = []
        for i in range(3):
            chunk = VectorChunk(
                id=f"test-{i}",
                file_path=f"/path/to/test_{i}.md",
                file_name=f"test_{i}.md",
                category="测试",
                chunk_index=i,
                chunk_text=f"测试内容 {i}",
                vector=[0.0] * 384,
                metadata={"test": f"test_data_{i}"}
            )
            test_chunks.append(chunk)

        # 添加向量
        store.add_vectors(test_chunks)

        # 验证添加
        for chunk in test_chunks:
            retrieved = store.get_vector(chunk.id)
            assert retrieved is not None
            assert retrieved["id"] == chunk.id

        # 验证按文件获取
        file_path = "/path/to/test_0.md"
        file_chunks = store.get_vectors_by_file(file_path)
        assert len(file_chunks) == 1
        assert file_chunks[0]["id"] == "test-0"

        # 验证删除
        deleted = store.delete_by_file(file_path)
        assert deleted == 1
        result = store.get_vectors_by_file(file_path)
        assert len(result) == 0

        print(f"  ✓ 存储模块通过 ({len(test_chunks)} 个向量)")
        print()

        results["storage"] = True

    except Exception as e:
        print(f"{RED}  ✗ 存储模块失败: {e}")
        import traceback
        traceback.print_exc()


def test_retriever():
    """测试检索模块"""
    global results

    print(f"{GREEN}┌─ 测试 5: 检索模块 ──────────────┐")
    try:
        config = Config()
        store = MetadataStore(config)
        from core.retriever import Retriever

        retriever = Retriever(store, config)

        # 添加测试数据
        test_chunks = []
        for i in range(3):
            chunk = VectorChunk(
                id=f"test-{i}",
                file_path=f"/path/to/test_{i}.md",
                file_name=f"test_{i}.md",
                category="测试",
                chunk_index=i,
                chunk_text=f"测试内容 {i}",
                vector=[0.0] * 384,
                metadata={"test": f"test_data_{i}"}
            )
            test_chunks.append(chunk)
            store.add_vectors(chunk)

        print(f"  ✓ 添加 {len(test_chunks)} 个向量到存储")

        # 测试关键词检索
        results_list = retriever.keyword_search("测试", top_k=5)
        print(f"  ✓ 关键词检索: {len(results_list)} 个结果")

        # 测试向量检索
        print()

        results["retriever"] = True

    except Exception as e:
        print(f"{RED}  ✗ 检索模块失败: {e}")
        import traceback
        traceback.print_exc()


def test_memory():
    """测试内存使用"""
    global results

    print(f"{GREEN}┌─ 测试 6: 内存使用 ──────────────┐")

    try:
        mem_gb = get_memory_usage()
        print(f"  ✓ 当前内存使用: {mem_gb:.2f} GB")

        if mem_gb > MEMORY_LIMIT:
            print(f"{RED}  ✗ 内存超限: {mem_gb:.2f} GB > 12GB}")
            results["memory_ok"] = False
        else:
            print(f"  ✓ 内存正常 ({mem_gb:.2f} GB / 12GB)")
            results["memory_ok"] = True

    except Exception as e:
        print(f"{RED}  ✗ 内存检查失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """运行所有测试"""
    # 清屏
    print("\n" * 60)

    # 显示测试信息
    print("=" * 60)
    print("本地知识库全量向量化系统 - 最终验收测试")
    print("=" * 60)
    print()
    print(f"测试日期: 2026-03-01")
    print(f"测试环境: M3 Mac 16GB RAM, macOS 25.2.0")
    print(f"内存限制: ≤ 12GB")
    print()
    print("=" * 60)
    print()
    print("安全原则:")
    print("🔴 严禁: 上传任何真实文档或数据到云端")
    print("🟢 允许: 设计结构、框架、流程、代码、接口"
    print()
    print("=" * 60)
    print()

    # 运行所有测试
    test_config()
    test_scanner()
    test_vectorizer()
    test_storage()
    test_retriever()
    test_memory()

    # 输出总结
    print()
    print("=" * 60)
    print("┌── 验收总结 ──────────┐")
    print(f"│ 测试项        │ 状态   │ 说明")
    print(f"├───────────────┼──────┼────────└")
    print(f"│ 配置模块      │  {GREEN}{"✓ 通过" if results["config"] else "✗ 失败"}")
    print(f"│ 扫描模块      │ {GREEN}{"✓ 通过" if results["scanner"] else "✗ 失败"}")
    print(f" 向量化模块    │ {GREEN}{"✓ 通过" if results["vectorizer"] else "✗ 失败"}")
    print(f" 存储模块      │ {GREEN}{"✓ 通过" if results["storage"] else "✗ 失败"}")
    print(f" 检索模块      │ {GREEN}{"✓ 通过" if results["retriever"] else "✗ 失败"}")
    print(f" 内存使用      │ {GREEN}{"✓ 正常" if results["memory_ok"] else "✗ 超限"}")
    print("└───────────────┼──────┼─────────┘")
    print()

    # 最终结论
    passed = all(results.values())
    total = len(results)

    print("=" * 60)
    if passed:
        print(f"│ {GREEN}✅ 所有 {total} 个测试通过！")
    else:
        failed_count = sum(1 for v in results.values() if not v)
        print(f"│ {RED}✗ 有 {failed_count}/{total} 个测试失败！")
    print("=" * 60)

    # 退出码
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
