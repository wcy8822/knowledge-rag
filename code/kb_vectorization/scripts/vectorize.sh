#!/bin/bash
# 本地知识库全量向量化自动化系统 - 向量化脚本
# 版本: v1.0
# 日期: 2026-03-01

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 默认参数
BATCH_SIZE=""
MVP_MODE=""

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        --mvp)
            MVP_MODE="--mvp"
            shift
            ;;
        --help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --batch-size N   设置批次大小"
            echo "  --mvp            使用 MVP 模式（小批次测试）"
            echo "  --help           显示帮助信息"
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            exit 1
            ;;
    esac
done

# 运行 Python 向量化脚本
cd "$PROJECT_DIR"

echo "========================================"
echo "  本地知识库 - 文档向量化"
echo "========================================"
echo ""

python3 -c "
import sys
import time
from core import FileScanner, Vectorizer, Config
from core.storage import create_vector_store

config = Config()
scanner = FileScanner(config)
vectorizer = Vectorizer(config)

# 设置批次大小
if '$BATCH_SIZE':
    config.set('vectorize.batch_size', int('$BATCH_SIZE'))
    print(f'使用批次大小: {config.batch_size}')

# MVP 模式
if '$MVP_MODE' == '--mvp':
    batch_size = config.mvp_batch_size
    print('使用 MVP 模式（小批次测试）')
else:
    batch_size = config.batch_size

print('开始扫描目录...')
start_time = time.time()

# 扫描文件
result = scanner.scan()
files = [f.path for f in result.files]

print(f'找到 {len(files)} 个文件')
print(f'总大小: {result.total_size / (1024*1024):.2f} MB')
print()

# 初始化存储
print('初始化向量存储...')
store = create_vector_store(config)
store_stats = store.get_stats()
print(f'当前向量数: {store_stats.get(\"total_vectors\", 0)}')
print()

# 分批向量化
print(f'开始向量化，批次大小: {batch_size}...')
print()

chunks, stats = vectorizer.vectorize_batch(files, batch_size=batch_size)

print()
print('向量化完成!')
print(f'  处理文件: {stats.processed_files}/{stats.total_files}')
print(f'  失败文件: {stats.failed_files}')
print(f'  生成向量: {stats.processed_chunks}')
print(f'  成功率: {stats.success_rate:.1%}')
print(f'  内存峰值: {stats.memory_peak:.2f} GB')
print(f'  处理耗时: {stats.duration:.2f} 秒')

if stats.avg_time_per_file:
    print(f'  平均耗时: {stats.avg_time_per_file:.2f} 秒/文件')

# 添加到存储
if chunks:
    print()
    print('添加向量到存储...')
    success = store.add_vectors(chunks)
    if success:
        print('向量添加成功')
    else:
        print('向量添加失败')
        sys.exit(1)

# 最终统计
final_stats = store.get_stats()
print()
print('最终统计:')
print(f'  总向量数: {final_stats.get(\"total_vectors\", 0)}')
print(f'  总文件数: {final_stats.get(\"metadata_stats\", {}).get(\"total_files\", 0)}')

total_time = time.time() - start_time
print()
print(f'总耗时: {total_time:.2f} 秒')
"

echo ""
echo "========================================"
echo "  向量化完成"
echo "========================================"
