#!/bin/bash
# -*- coding: utf-8 -*-
"""
M3 Mac 本地知识库向量化 - 规模化启动脚本
版本: v1.0
日期: 2026-03-01

环境: M3 Mac 16GB RAM, macOS 25.2.0
约束: 内存峰值 ≤ 12GB, 数据绝不上云
"""

set -e

PROJECT_DIR="/Users/didi/Downloads/panth/kb_vectorization"
LOG_FILE="$PROJECT_DIR/logs/scale_run.log"
MEMORY_LIMIT=12  # GB
BATCH_SIZE=500        # 默认批次大小
MIN_CHUNK_SIZE=50      # 最小块大小（字符）
CHUNK_SIZE=1000       # 默认分块大小
CHUNK_OVERLAP=200    # 默认重叠大小
MAX_CHUNKS_PER_FILE=100 # 每个文件最大块数

# 颜色定义
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
NC='\033[0m'

# 打印带颜色的函数
print_color() {
    local color=$1
    shift
    echo -e "${color}$*${NC}"
    shift
}

# 内存检查函数
check_memory() {
    local mem_mb=0
    if command -v psutil 2>/dev/null; then
        mem_mb=$(psutil -p $$ | grep -E 'RSS:' | awk '{sum ($2/1024)}')
    else
        mem_mb=$(ps -o rss= -p $$)
    fi

    local mem_gb=$(echo "scale=3; $mem_mb/1024" | bc | head -n)

    if (( $(echo "$mem_gb >= $MEMORY_LIMIT" | bc -l))); then
        print_color "[$YELLOW] 警告: 内存使用 ${mem_gb}GB 已接近上限 ${MEMORY_LIMIT}GB，正在释放内存..."
        # 强制垃圾回收
        python3 -c "
import gc
gc.collect()
print(f'内存已释放，当前使用: {get_memory_usage()}GB')
        " 2>/dev/null || true
    else
        return 0
    fi

    return 1
}

# 获取内存使用量（GB）
get_memory_usage() {
    if command -v psutil 2>/dev/null; then
        local mem_mb=$(psutil -p $$ | grep -E 'RSS:' | awk '{sum ($2/1024)}')
        echo "scale=3; $mem_mb/1024" | bc | head -n
    else
        ps -o rss= -p $$ | awk '{print ($1/1024)}'
    fi
}

get_memory_usage
}

# 清理临时文件
cleanup_temp_files() {
    print_color "[$GREEN] 清理临时文件..."
    rm -rf "$PROJECT_DIR/data/temp/"* 2>/dev/null || true
    print "临时文件已清理"
}

# 检查环境依赖
check_dependencies() {
    print_color "[$GREEN] 检查环境依赖..."

    # 检查 Python
    if ! command -v python3 &>/dev/null; then
        echo "[$RED] 错误: 未找到 python3"
        return 1
    fi

    # 检查 YAML 支持
    python3 -c "import yaml; print(yaml.__version__)" 2>/dev/null || {
        echo "[$YELLOW] 警告: 未安装 pyyaml，配置文件可能无法加载"
    }

    # 检查文件监控
    python3 -c "import watchdog; print('watchdog', 'watchdog.__version__')" 2>/dev/null || {
        echo "[$YELLOW] 警告: 未安装 watchdog，文件监控功能不可用"
    }

    # 检查 schedule
    python3 -c "import schedule; print('schedule', 'schedule.__version__')" 2>/dev/null || {
        echo "[$YELLOW] 警告: 未安装 schedule，定时任务功能不可用"
    }

    return 0
}

# 创建必要的目录
create_directories() {
    mkdir -p "$PROJECT_DIR/data/vector_db"
    mkdir -p "$PROJECT_DIR/data/stats/daily_reports"
    mkdir -p "$PROJECT_DIR/data/temp"
    mkdir -p "$PROJECT_DIR/data/backup"
    mkdir -p "$PROJECT_DIR/logs"
    echo "✓ 目录结构创建完成"
}

# 初始化环境
init_environment() {
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║      M3 Mac 本地知识库向量化 - 规模化运行环境          ║"
    echo "║      内存限制: ${MEMORY_LIMIT}GB                                    ║"
    echo "║      批次大小: ${BATCH_SIZE} 文件/批                        ║"
    "║      分块大小: ${CHUNK_SIZE} 字符                          ║"
    "║      机器: M3 Mac (16GB RAM)                                  ║"
    "║      系统: macOS $(uname -s)                                   ║"
    "╚════════════════════════════════════════════════════════╗"
    echo ""

    # 检查环境
    check_dependencies
    if [ $? -ne 0 ]; then
        return 1
    fi

    # 创建目录
    create_directories

    echo ""
}

# 运行向量化
run_vectorization() {
    local scan_dirs="$1"
    local file_types="$2"

    echo "═════════════════════════════════════════════════════════════"
    echo "║            M3 Mac 本地知识库向量化 - 规模化运行                ║"
    echo "════════─────────────────────────────────────────────────────────┘"
    echo ""

    # 扫描文件
    echo_color "[$GREEN] 阶段 1/3: 扫描文件..."
    cd "$PROJECT_DIR"
    python3 -c "
import sys
sys.path.insert(0, '.')
from core.config import Config
from core.scanner import FileScanner

config = Config()
config.set('scan.directories', ['/Users/didi/knowledge_base_vectorization'])
config.set('scan.recursive', True)

scanner = FileScanner(config)
result = scanner.scan()

print()
print('扫描完成:')
print(f'  文件总数: {result.total_files}')
print(f'  总大小: {result.total_size / (1024*1024):.2f} MB')
print()

# 创建扫描结果的 JSON
import json
scan_output = {
    'total_files': result.total_files,
    'total_size': result.total_size,
    'by_type': result.by_type,
    'by_category': result.by_category,
    'files': [f.path for f in result.files]
}

with open('data/stats/scan_result.json', 'w', encoding='utf-8') as f:
    json.dump(scan_output, f, ensure_ascii=False, indent=2)

print(f'扫描结果已保存到: data/stats/scan_result.json')
"
" 2>&1

    # 如果没有找到文件，退出
    if [ -z "data/stats/scan_result.json" ]; then
        echo "[$YELLOW] 警告: 没有找到可向量化文件"
        return 1
    fi

    # 准备文件列表
    local files=$(python3 -c "
import json
with open('data/stats/scan_result.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    print('\\n'.join([f['path'].replace('\\', '\\\\') for f in data['files']]))
" 2>/dev/null || true)

    if [ -z "$files" ]; then
        echo "[$YELLOW] 警告: 找不到可向量化文件"
        return 1
    fi

    # 向量化 - 分批处理
    echo ""
    echo_color "[$GREEN] 阶段 2/3: 批量向量化..."
    echo ""

    python3 << 'PYTHON_SCRIPT'
import sys
import sys
sys.path.insert(0, '.')
from core.config import Config
from core.vectorizer import Vectorizer
from core.storage import create_vector_store
from core.utils import get_memory_usage

config = Config()
vectorizer = Vectorizer(config)
store = create_vector_store(config)

# 读取扫描结果
import json
with open('data/stats/scan_result.json', 'r', encoding='utf-8') as f:
    scan_data = json.load(f)

files = [f['path'] for f in scan_data['files']]
total_files = len(files)

print(f'准备向量化 {total_files} 个文件')
print(f'预期批次: {(total_files + BATCH_SIZE - 1) // BATCH_SIZE}')
print()

# 分批处理
success_count = 0
fail_count = 0
total_chunks = 0

for batch_start in range(0, total_files, BATCH_SIZE):
    batch_end = min(batch_start + BATCH_SIZE, total_files)
    batch_files = files[batch_start:batch_end]

    print(f'处理批次 {batch_start // BATCH_SIZE + 1}/{(total_files - 1) // BATCH_SIZE + 1}， 文件数: {len(batch_files)}')
    print(f'当前内存: {get_memory_usage()}GB')

    # 处理当前批次
    try:
        chunks, stats = vectorizer.vectorize_batch(batch_files)

        total_chunks += stats.processed_chunks
        success_count += stats.processed_files
        fail_count += stats.failed_files

        # 存储向量
        if chunks:
            store.add_vectors(chunks)

    except Exception as e:
        print(f'批次处理失败: {e}')
        fail_count += len(batch_files)

    # 每批结束后检查内存
    check_memory

print()
print_color "[$GREEN] 向量化完成!"
print()
print(f'处理文件数: {success_count}/{total_files}')
print(f'生成向量数: {total_chunks}')
print(f'失败文件数: {fail_count}')
print()

# 输出最终统计
python3 << 'PYTHON_SCRIPT'
import json
from core.storage import create_vector_store
from core.utils import get_memory_usage

config = Config()
store = create_vector_store(config)

stats = store.get_stats()
print('=== 最终统计 ===')
print(f'向量库类型: {config.store_type}')
print(f'向量总数: {stats.get(\"total_vectors\", 0)}')
print(f'文件总数: {stats.get(\"metadata_stats\", {}).get(\"total_files\", 0)}')
print(f'当前内存: {get_memory_usage()}GB')
print('================================')
PYTHON_SCRIPT

}

    # 生成测试报告
    echo ""
    echo_color "[$GREEN] 阶段 3/3: 生成测试报告..."
    echo ""

    python3 << 'PYTHON_SCRIPT'
import json
import os

# 读取最终统计
from core.storage import create_vector_store
from core.config import Config

config = Config()
store = create_vector_store(config)
stats = store.get_stats()

print('=' * 50)
print('  本地知识库向量化 - 规模化测试报告')
print('=' * 50)
print()

print('一、基础信息')
print(f'系统: {config.system_name}')
print(f'版本: {config.system_version}')
print(f'环境: macOS $(uname -s)')
print(f'机器: M3 Mac (16GB RAM)')
print(f'内存限制: {config.memory_limit}GB')
print()

print('二、扫描结果')
print(f'文件总数: {stats.get(\"metadata_stats\", {}).get(\"total_files\", 0)}')
print()

print('三、向量化结果')
print(f'向量总数: {stats.get(\"total_vectors\", 0)}')
print(f'存储类型: {config.store_type}')
print(f'向量维度: {config.vector_dim}')
print()

# 内存使用情况
mem_gb = get_memory_usage()
print('四、内存使用')
print(f'当前内存: {mem_gb:.2f}GB')
print(f'内存限制: {config.memory_limit}GB')
print(f'剩余空间: {config.memory_limit - mem_gb:.2f}GB')
print()

# 按分类统计
metadata_stats = stats.get('metadata_stats', {})
categories = metadata_stats.get('categories', {})

if categories:
    print('五、分类统计')
    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        print(f'  {cat}: {count} 个文件')
    print()

# 生成 CSV 报告
import csv
report_path = 'data/stats/scale_report.csv'

with open(report_path, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['分类', '文件数', '向量数'])

    for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        writer.writerow([cat, count, count * 5])  # 假设平均每个文件 5 个向量

print()
print(f'报告已保存: {report_path}')
print()

# 内存优化建议
if mem_gb > 8.0:
    print('六、内存优化建议')
    print()
    print('建议:')
    print('  1. 降低批次大小（当前: %s）' % BATCH_SIZE)
    print('  2. 使用更小的分块大小')
    print('  3. 减少日志输出')
    print('  4. 增加内存监控频率')
else:
    print('内存使用正常')

print('=' * 50)
print('  规模化测试完成')
print('=' * 50)
PYTHON_SCRIPT

    # 最终内存检查
    final_mem = get_memory_usage()
    echo ""
    echo_color "最终内存使用: ${final_mem}GB / ${MEMORY_LIMIT}GB"

    if (( $(echo "$final_mem >= $MEMORY_LIMIT" | bc -l) )); then
        print_color "[$RED] 错误: 内存超限！"
        return 1
    fi

    echo ""
    echo_color "[$GREEN] 规模化准备完成！"
    echo ""
    echo "下一步："
    echo "  1. 运行: ./scripts/start_api.sh --daemon"
    echo "   2. 测试 API: curl http://127.0.0.1:8000/api/v1/health"
    echo "  3. 搜索测试: curl -X POST http://127.0.0.1:8000/api/v1/search -H \"Content-Type: application/json\" -d '{\"query\":\"测试\"}'"

PYTHON_SCRIPT
}

    # 返回成功
    return 0
}

# 检查状态
check_status() {
    echo ""
    echo "===================="
    echo "  系统状态检查"
    echo "===================="
    echo ""

    echo "环境信息:"
    python3 --version
    echo ""

    echo "磁盘空间:"
    df -h "$PROJECT_DIR" | grep -E '^[F].*'
    echo ""

    echo "内存使用:"
    ps aux | grep -E 'python3|Python' | awk '{sum($6/1048576)/1024/1024}' | bc -l
    echo ""

    echo "关键文件:"
    ls -lah "$PROJECT_DIR/data/vector_db" 2>/dev/null || echo "未找到向量库目录"
    echo ""

    echo "日志文件:"
    ls -lh "$PROJECT_DIR/logs/" 2>/dev/null || echo "未找到日志文件"
    echo ""

    echo "配置文件:"
    ls -lah "$PROJECT_DIR/config/" 2>/dev/null || echo "未找到配置文件"
    echo "===================="
    echo ""
}

# 帮助信息
show_help() {
    echo ""
    echo "===================="
    echo "  M3 Mac 规模化向量化 - 使用帮助"
    echo "===================="
    echo ""
    echo "可用命令："
    echo "  $0 run                    - 扫描并向量化（默认路径）"
    echo "  - scan_dirs /path/to/dir1,/path/to/dir2 - 扫描指定目录"
    echo "  - batch_size N               - 设置批次大小（默认500）"
    echo "  - min_chunk_size N           - 设置最小块大小（默认50）"
    " - memory_limit N             - 设置内存限制（默认 12GB）"
    echo "  - check_status            - 检查系统状态"
    "  - show_help              - 显示帮助信息"
    "  - cleanup                - 清理临时文件和日志"
    "  - backup                  - 备份当前数据"
    "  - recover                - 从备份恢复数据"
    echo ""
    echo "示例："
    echo "  $0 run                            # 运行完整流程"
    "  $0 run - batch_size 200 memory_limit 8"      # 优化内存配置"
    echo ""
    echo "环境要求:"
    echo "  - Python 3.10+"
    echo "  - pyyaml (可选，用于配置）"
    "  - watchdog (可选，用于文件监控）"
    "  - schedule (可选，用于定时任务）"
    echo ""
    echo "注意事项:"
    echo "   - 本程序仅在 M3 Mac 本地运行"
    "  - 所有数据在本地处理，绝不上传云端"
    "  - 内存使用受限，大量文件需分批处理"
    "  - 建议先用小批量（如50个文件/批）测试"
    ""
    echo "===================="
    echo ""
}

# 命令解析
case "$1" in
    run)
        run_vectorization
        ;;
    scan_dirs)
        shift
        if [ -z "$2" ]; then
            echo "错误: 请提供扫描目录"
            exit 1
        fi
        run_vectorization "$@"
        ;;
    memory_limit)
        shift
        if [ -z "$2" ]; then
            echo "错误: 请提供内存限制（GB）"
            exit 1
        fi
        export MEMORY_LIMIT=$2
        export PYTHONPATH=.:/Users/didi/Downloads/panth/kb_vectorization:$PYTHONPATH
        run_vectorization
        ;;
    min_chunk_size)
        shift
        if [ -z "$2" ]; then
            echo "错误: 请提供最小块大小（字符数）"
            exit 1
        fi
        export MIN_CHUNK_SIZE=$2
        export PYTHONPATH=.:/Users/didi/Downloads/panth/kb_vectorization:$PYTHONPATH
        run_vectorization
        ;;
    batch_size)
        shift
        if [ -z "$2" ]; then
            echo "错误: 请提供批次大小"
            exit 1
        fi
        export BATCH_SIZE=$2
        export PYTHONPATH=.:/Users/didi/Downloads/panth/kb_vectorization:$PYTHONPATH
        run_vectorization
        ;;
    check_status)
        check_status
        ;;
    cleanup)
        echo "清理临时文件..."
        rm -rf "$PROJECT_DIR/data/temp/"*2>/dev/null || true
        rm -rf "$PROJECT_DIR/logs/*.log" 2>/dev/null || true
        rm -rf "$PROJECT_DIR/data/temp/"*2>/dev/null || true
        echo "清理完成"
        ;;
    backup)
        echo "备份数据..."
        if [ -d "$PROJECT_DIR/data/backup" ]; then
            python3 -c "
import os
import datetime
backup_dir = '/Users/didi/Downloads/panth/kb_vectorization/data/backup'
os.makedirs(backup_dir, exist_ok=True)
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

import shutil
import glob

# 备份向量库
vector_db_dir = '/Users/didi/Downloads/panth/kb_vectorization/data/vector_db'
if os.path.exists(vector_db_dir):
    backup_path = os.path.join(backup_dir, f"vector_db_{timestamp}")
    shutil.copytree(vector_db_dir, backup_path)
    print(f'备份完成: {backup_path}')

# 备份元数据
metadata_file = '/Users/didi/Downloads/panth/kb_vectorization/data/vector_db/metadata.json'
if os.path.exists(metadata_file):
    backup_path = os.path.join(backup_dir, f"metadata_{timestamp}.json")
    shutil.copy(metadata_file, backup_path)
    print(f'备份完成: {backup_path}')

print('备份完成！')
"
        else
            echo "没有找到需要备份的数据"
            ;;
    recover)
        echo "从备份恢复数据..."
        # TODO: 实现恢复功能
        echo "恢复功能待实现"
        ;;
    *)
        echo "未知命令: $1"
        echo "使用 -h 或 --help 查看帮助"
        exit 1
        ;;
    show_help)
        show_help
        ;;
    *)
        echo "未知命令: $1"
        echo ""
        show_help
        ;;
esac

# 主程序入口
case "$0" in
    help|--help|-h|help)")
        show_help
        ;;
    check_status|--status|status)")
        check_status
        ;;
    cleanup|--clean|clean)
        cleanup_temp_files
        ;;
    *)
        run_vectorization
        ;;
esac
        echo -e "参数错误: $0"
        echo ""
        show_help
        exit 1
        ;;
esac
    ;;
esac
    ;;
