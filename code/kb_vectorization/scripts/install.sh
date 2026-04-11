#!/bin/bash
# 本地知识库全量向量化自动化系统 - 安装脚本
# 版本: v1.0
# 日期: 2026-03-01

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "========================================"
echo "  本地知识库 - 安装脚本"
echo "========================================"
echo ""

# 检查 Python
echo "检查 Python..."
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}Python 版本:${NC} $PYTHON_VERSION"

# 检查 pip
echo ""
echo "检查 pip..."
if ! command -v pip3 &> /dev/null; then
    echo "错误: 未找到 pip3"
    exit 1
fi

echo -e "${GREEN}pip 版本:${NC} $(pip3 --version)"

# 创建虚拟环境（可选）
if [ "$1" == "--venv" ]; then
    echo ""
    echo "创建虚拟环境..."
    if [ ! -d "$PROJECT_DIR/venv" ]; then
        python3 -m venv "$PROJECT_DIR/venv"
        echo -e "${GREEN}虚拟环境已创建${NC}"
    else
        echo "虚拟环境已存在"
    fi
    source "$PROJECT_DIR/venv/bin/activate"
fi

# 安装依赖
echo ""
echo "安装 Python 依赖..."
echo ""

# 基础依赖
cat > "$PROJECT_DIR/requirements.txt" << 'EOF'
# 核心依赖
pyyaml>=6.0

# 可选依赖（推荐安装）
# chromadb>=0.4.0      # Chroma 向量库
# faiss-cpu>=1.7.0    # FAISS 向量库
# watchdog>=3.0.0     # 文件监控
# schedule>=1.2.0     # 定时任务
# psutil>=5.9.0       # 系统监控

# API 依赖
flask>=3.0.0
EOF

pip3 install -r "$PROJECT_DIR/requirements.txt"

echo ""
echo -e "${GREEN}基础依赖安装完成${NC}"

# 可选依赖
echo ""
echo "安装可选依赖..."
echo ""
echo -e "${YELLOW}提示: 以下为可选依赖，可根据需要安装${NC}"
echo ""

# Chroma
echo -n "安装 Chroma... "
if pip3 install chromadb 2>/dev/null; then
    echo -e "${GREEN}成功${NC}"
else
    echo -e "${YELLOW}失败（可选）${NC}"
fi

# FAISS
echo -n "安装 FAISS... "
if pip3 install faiss-cpu 2>/dev/null; then
    echo -e "${GREEN}成功${NC}"
else
    echo -e "${YELLOW}失败（可选）${NC}"
fi

# Watchdog
echo -n "安装 Watchdog... "
if pip3 install watchdog 2>/dev/null; then
    echo -e "${GREEN}成功${NC}"
else
    echo -e "${YELLOW}失败（可选）${NC}"
fi

# Schedule
echo -n "安装 Schedule... "
if pip3 install schedule 2>/dev/null; then
    echo -e "${GREEN}成功${NC}"
else
    echo -e "${YELLOW}失败（可选）${NC}"
fi

# Psutil
echo -n "安装 Psutil... "
if pip3 install psutil 2>/dev/null; then
    echo -e "${GREEN}成功${NC}"
else
    echo -e "${YELLOW}失败（可选）${NC}"
fi

# 创建必要目录
echo ""
echo "创建目录结构..."
mkdir -p "$PROJECT_DIR/data/vector_db"
mkdir -p "$PROJECT_DIR/data/stats/daily_reports"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/data/temp"
echo -e "${GREEN}目录创建完成${NC}"

# 设置脚本执行权限
echo ""
echo "设置脚本执行权限..."
chmod +x "$PROJECT_DIR/scripts/"*.sh
echo -e "${GREEN}脚本权限设置完成${NC}"

# 完成
echo ""
echo "========================================"
echo -e "${GREEN}  安装完成${NC}"
echo "========================================"
echo ""
echo "接下来可以:"
echo "  1. 编辑配置文件: $PROJECT_DIR/config/config.yaml"
echo "  2. 扫描文件: $PROJECT_DIR/scripts/scan.sh"
echo "  3. 向量化: $PROJECT_DIR/scripts/vectorize.sh"
echo "  4. 启动 API: $PROJECT_DIR/scripts/start_api.sh"
echo "  5. 查看状态: $PROJECT_DIR/scripts/check_status.sh"
echo ""
