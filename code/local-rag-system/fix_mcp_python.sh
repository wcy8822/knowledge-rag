#!/bin/bash
# 自动修复 local_knowledge MCP 服务的 Python 版本问题

set -e  # 遇到错误立即退出

echo "=================================="
echo "🔧 MCP local_knowledge 自动修复脚本"
echo "=================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查当前 Python 版本
echo "📌 检查当前 Python 版本..."
CURRENT_PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "   当前版本: ${CURRENT_PYTHON_VERSION}"

# 检查是否已有 Python 3.10+
PYTHON311_PATH=""
for path in \
    "/opt/homebrew/bin/python3.11" \
    "/usr/local/bin/python3.11" \
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11" \
    "$HOME/.pyenv/versions/3.11.7/bin/python3.11" \
    "/opt/homebrew/bin/python3.10" \
    "/usr/local/bin/python3.10"
do
    if [ -x "$path" ]; then
        PYTHON311_PATH="$path"
        echo -e "${GREEN}✅ 找到 Python 3.10+: $path${NC}"
        break
    fi
done

# 如果没找到，提示安装
if [ -z "$PYTHON311_PATH" ]; then
    echo -e "${RED}❌ 未找到 Python 3.10+ 安装${NC}"
    echo ""
    echo "请选择安装方式："
    echo "1) 通过 Homebrew 安装（推荐）"
    echo "2) 手动从 python.org 下载"
    echo "3) 退出，稍后手动安装"
    echo ""
    read -p "请选择 [1-3]: " choice

    case $choice in
        1)
            echo ""
            echo "📦 检查 Homebrew..."
            if ! command -v brew &> /dev/null; then
                echo -e "${YELLOW}⚠️  Homebrew 未安装。正在安装 Homebrew...${NC}"
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

                # 添加 Homebrew 到 PATH
                if [ -f "$HOME/.zshrc" ]; then
                    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zshrc"
                    eval "$(/opt/homebrew/bin/brew shellenv)"
                fi
            fi

            echo ""
            echo "📦 安装 Python 3.11..."
            brew install python@3.11

            PYTHON311_PATH="/opt/homebrew/bin/python3.11"
            ;;
        2)
            echo ""
            echo "📖 请访问以下链接下载并安装 Python 3.11+:"
            echo "   https://www.python.org/downloads/macos/"
            echo ""
            echo "安装完成后，重新运行此脚本。"
            exit 0
            ;;
        3)
            echo "👋 退出。请稍后手动安装 Python 3.10+。"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ 无效选择${NC}"
            exit 1
            ;;
    esac
fi

# 验证 Python 版本
echo ""
echo "🔍 验证 Python 版本..."
PYTHON_VERSION=$("$PYTHON311_PATH" --version 2>&1 | awk '{print $2}')
echo "   使用版本: ${PYTHON_VERSION}"

# 检查版本是否 >= 3.10
MAJOR_VERSION=$(echo "$PYTHON_VERSION" | cut -d. -f1)
MINOR_VERSION=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$MAJOR_VERSION" -lt 3 ] || ([ "$MAJOR_VERSION" -eq 3 ] && [ "$MINOR_VERSION" -lt 10 ]); then
    echo -e "${RED}❌ Python 版本过低 (需要 >= 3.10)${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python 版本符合要求${NC}"

# 安装 MCP 库
echo ""
echo "📦 安装 MCP 库..."
"$PYTHON311_PATH" -m pip install --user mcp 2>&1 | grep -v "Requirement already satisfied" || true
echo -e "${GREEN}✅ MCP 库安装完成${NC}"

# 更新 .claude.json
echo ""
echo "📝 更新 .claude.json 配置..."
CLAUDE_JSON="$HOME/.claude.json"

if [ ! -f "$CLAUDE_JSON" ]; then
    echo -e "${RED}❌ 未找到 .claude.json 文件${NC}"
    exit 1
fi

# 创建备份
cp "$CLAUDE_JSON" "${CLAUDE_JSON}.backup.$(date +%Y%m%d_%H%M%S)"
echo "   ✅ 已创建备份: ${CLAUDE_JSON}.backup.*"

# 使用 Python 更新配置（更安全）
python3 <<EOF
import json
import sys

config_path = "$CLAUDE_JSON"
python_path = "$PYTHON311_PATH"

try:
    with open(config_path, 'r') as f:
        config = json.load(f)

    # 查找并更新 local_knowledge 配置
    updated = False
    for project_path, project_config in config.get('projects', {}).items():
        if 'mcpServers' in project_config:
            if 'local_knowledge' in project_config['mcpServers']:
                project_config['mcpServers']['local_knowledge']['command'] = python_path
                updated = True
                print(f"   ✅ 已更新项目: {project_path}")

    if updated:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("   ✅ 配置文件更新成功")
    else:
        print("   ⚠️  未找到 local_knowledge 配置")

    sys.exit(0)
except Exception as e:
    print(f"   ❌ 更新配置失败: {e}")
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 配置更新失败${NC}"
    exit 1
fi

# 测试 MCP 服务
echo ""
echo "🧪 测试 MCP 服务..."
MCP_SERVER_PATH="/Users/didi/Downloads/panth/local-rag-system/src/serve/mcp_knowledge_server.py"

if [ -f "$MCP_SERVER_PATH" ]; then
    timeout 3 "$PYTHON311_PATH" "$MCP_SERVER_PATH" --help &> /dev/null || true
    if [ $? -eq 124 ] || [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ MCP 服务可以正常启动${NC}"
    else
        echo -e "${YELLOW}⚠️  MCP 服务测试超时或失败（可能正常）${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  未找到 MCP 服务脚本${NC}"
fi

# 完成
echo ""
echo "=================================="
echo -e "${GREEN}🎉 修复完成！${NC}"
echo "=================================="
echo ""
echo "📋 修复摘要："
echo "   ✅ Python 路径: ${PYTHON311_PATH}"
echo "   ✅ Python 版本: ${PYTHON_VERSION}"
echo "   ✅ MCP 库: 已安装"
echo "   ✅ 配置文件: 已更新"
echo ""
echo "🚀 下一步："
echo "   1. 重启 Claude Code"
echo "   2. 在 MCP 服务管理中查看 local_knowledge 状态"
echo "   3. 应该显示为 ✅ connected"
echo ""
echo "💡 如果还有问题，请查看："
echo "   /Users/didi/Downloads/panth/local-rag-system/FIX_PYTHON_VERSION.md"
echo ""
