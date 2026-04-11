#!/bin/bash
# 本地知识库全量向量化自动化系统 - 状态检查脚本
# 版本: v1.0
# 日期: 2026-03-01

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "  本地知识库 - 系统状态"
echo "========================================"
echo ""

# 检查 Python
echo -n "Python:      "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}已安装${NC} ($PYTHON_VERSION)"
else
    echo -e "${RED}未安装${NC}"
fi

# 检查目录结构
echo -n "项目目录:    "
if [ -d "$PROJECT_DIR" ]; then
    echo -e "${GREEN}存在${NC} ($PROJECT_DIR)"
else
    echo -e "${RED}不存在${NC}"
fi

echo -n "配置文件:    "
if [ -f "$PROJECT_DIR/config/config.yaml" ]; then
    echo -e "${GREEN}存在${NC}"
else
    echo -e "${RED}不存在${NC}"
fi

echo -n "核心模块:    "
if [ -d "$PROJECT_DIR/core" ]; then
    MODULE_COUNT=$(ls -1 "$PROJECT_DIR/core"/*.py 2>/dev/null | wc -l)
    echo -e "${GREEN}存在${NC} ($MODULE_COUNT 个模块)"
else
    echo -e "${RED}不存在${NC}"
fi

echo -n "数据目录:    "
if [ -d "$PROJECT_DIR/data" ]; then
    echo -e "${GREEN}存在${NC}"
else
    echo -e "${YELLOW}不存在（运行时自动创建）${NC}"
fi

# 检查 API 服务
echo -n "API 服务:    "
PID_FILE="$PROJECT_DIR/.api.pid"
if [ -f "$PID_FILE" ]; then
    API_PID=$(cat "$PID_FILE)
    if ps -p $API_PID > /dev/null 2>&1; then
        echo -e "${GREEN}运行中${NC} (PID: $API_PID)"
    else
        echo -e "${RED}已停止${NC} (PID 文件存在但进程不存在)"
    fi
else
    echo -e "${YELLOW}未运行${NC}"
fi

# 检查向量库
echo -n "向量库:      "
VECTOR_DB_DIR="$PROJECT_DIR/data/vector_db"
if [ -d "$VECTOR_DB_DIR" ]; then
    CHROMA_DIR="$VECTOR_DB_DIR/chroma"
    if [ -d "$CHROMA_DIR" ]; then
        echo -e "${GREEN}存在${NC} (Chroma)"
    else
        echo -e "${YELLOW}存在${NC} (空)"
    fi
else
    echo -e "${YELLOW}不存在${NC}"
fi

# 检查日志
echo -n "日志目录:    "
LOG_DIR="$PROJECT_DIR/logs"
if [ -d "$LOG_DIR" ]; then
    LOG_COUNT=$(ls -1 "$LOG_DIR"/*.log 2>/dev/null | wc -l)
    echo -e "${GREEN}存在${NC} ($LOG_COUNT 个日志文件)"
else
    echo -e "${YELLOW}不存在${NC}"
fi

# 内存使用
echo -n "内存使用:    "
if command -v python3 &> /dev/null; then
    MEM_INFO=$(python3 -c "
import psutil
process = psutil.Process()
mem_mb = process.memory_info().rss / (1024 ** 2)
mem_gb = mem_mb / 1024
print(f'{mem_mb:.1f} MB ({mem_gb:.2f} GB)')
")
    echo "$MEM_INFO"
else
    echo -e "${YELLOW}无法获取${NC}"
fi

echo ""
echo "========================================"
echo "  检查完成"
echo "========================================"
