#!/bin/bash
# 本地知识库全量向量化自动化系统 - 文件扫描脚本
# 版本: v1.0
# 日期: 2026-03-01

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 加载配置
if [ -f "$PROJECT_DIR/config/config.yaml" ]; then
    echo "加载配置文件..."
else
    echo "错误: 配置文件不存在"
    exit 1
fi

# 运行 Python 扫描脚本
cd "$PROJECT_DIR"

echo "========================================"
echo "  本地知识库 - 文件扫描"
echo "========================================"
echo ""

python3 -c "
from core import FileScanner, Config

config = Config()
scanner = FileScanner(config)

print('开始扫描目录...')
result = scanner.scan()

print()
print('扫描结果:')
print(f'  文件总数: {result.total_files}')
print(f'  总大小: {result.total_size / (1024*1024):.2f} MB')
print(f'  扫描耗时: {result.scan_time:.2f} 秒')

print()
print('按类型统计:')
for file_type, count in result.by_type.items():
    print(f'  {file_type}: {count}')

print()
print('按分类统计:')
for category, count in result.by_category.items():
    print(f'  {category}: {count}')

# 导出 CSV
csv_path = scanner.export_csv(result)
print()
print(f'CSV 文件已保存: {csv_path}')
"

echo ""
echo "========================================"
echo "  扫描完成"
echo "========================================"
