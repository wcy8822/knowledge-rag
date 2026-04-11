#!/bin/bash

# 本地RAG系统 - 一键测试脚本
# 功能：自动完成环境检查、笔记收集、向量化和测试

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}🎯 本地RAG系统 - 一键测试${NC}"
echo -e "${BLUE}============================================================${NC}"

# 当前目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# 第1步：检查Python环境
echo -e "\n${YELLOW}📋 第1步：检查Python环境${NC}"
echo -e "${YELLOW}------------------------------------------------------------${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 未找到Python 3，请先安装Python 3.9+${NC}"
    exit 1
fi

python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}❌ Python版本过低：$python_version（需要3.9+）${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python版本检查通过：$python_version${NC}"

# 第2步：检查虚拟环境
echo -e "\n${YELLOW}🔧 第2步：准备虚拟环境${NC}"
echo -e "${YELLOW}------------------------------------------------------------${NC}"

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 创建虚拟环境...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ 虚拟环境创建成功${NC}"
fi

# 激活虚拟环境
echo -e "${YELLOW}🔄 激活虚拟环境...${NC}"
source venv/bin/activate

# 检查依赖
echo -e "${YELLOW}📦 检查依赖包...${NC}"

# 快速检查核心依赖
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}📥 安装项目依赖...${NC}"
    echo -e "${YELLOW}   (首次运行可能需要5-10分钟)${NC}"
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r requirements.txt
    echo -e "${GREEN}✅ 依赖安装完成${NC}"
else
    echo -e "${GREEN}✅ 依赖已安装${NC}"
fi

# 第3步：准备测试数据
echo -e "\n${YELLOW}📂 第3步：准备测试笔记${NC}"
echo -e "${YELLOW}------------------------------------------------------------${NC}"

# 创建数据目录
mkdir -p ./data/uploads

# 统计笔记文件
note_count=$(find ./data/uploads -name "*.md" -o -name "*.txt" 2>/dev/null | wc -l | tr -d ' ')

if [ "$note_count" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  未找到笔记文件${NC}"
    echo -e "${BLUE}💡 提示：${NC}"
    echo -e "   请将笔记文件复制到: ${BLUE}./data/uploads/${NC}"
    echo -e "   支持格式: ${GREEN}.md, .txt, .docx, .pdf${NC}"
    echo -e ""
    echo -e "   示例命令:"
    echo -e "   ${BLUE}cp /your/notes/*.md ./data/uploads/${NC}"
    echo -e "   ${BLUE}cp /Users/didi/Downloads/panth/*.md ./data/uploads/${NC}"
    echo -e ""
    read -p "是否自动从panth目录收集Markdown文件？[y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}📥 收集panth目录下的Markdown文件...${NC}"
        find /Users/didi/Downloads/panth -maxdepth 2 -name "*.md" ! -path "*/.*" -exec cp {} ./data/uploads/ \; 2>/dev/null || true
        note_count=$(find ./data/uploads -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
        echo -e "${GREEN}✅ 收集到 $note_count 个文件${NC}"
    fi

    # 再次检查
    note_count=$(find ./data/uploads -name "*.md" -o -name "*.txt" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$note_count" -eq 0 ]; then
        echo -e "${RED}❌ 仍未找到笔记文件，退出${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ 找到 $note_count 个笔记文件${NC}"
echo -e "${BLUE}📝 文件列表:${NC}"
find ./data/uploads -name "*.md" -o -name "*.txt" | head -5 | while read file; do
    echo -e "   - $(basename $file)"
done

if [ "$note_count" -gt 5 ]; then
    echo -e "   - ... (共 $note_count 个文件)"
fi

# 第4步：运行向量化测试
echo -e "\n${YELLOW}🚀 第4步：运行向量化测试${NC}"
echo -e "${YELLOW}------------------------------------------------------------${NC}"
echo -e "${YELLOW}⏳ 正在向量化笔记文件...${NC}"
echo -e "${BLUE}   (这可能需要几分钟时间)${NC}"
echo ""

if python3 test_local_vectorization.py; then
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}🎉 测试成功完成！${NC}"
    echo -e "${GREEN}============================================================${NC}"
    echo ""
    echo -e "${BLUE}📌 后续步骤:${NC}"
    echo -e "   1️⃣  启动API服务:"
    echo -e "      ${YELLOW}./scripts/serve.sh${NC}"
    echo -e ""
    echo -e "   2️⃣  访问Web界面:"
    echo -e "      ${YELLOW}http://localhost:8000/docs${NC}"
    echo -e ""
    echo -e "   3️⃣  测试搜索:"
    echo -e "      ${YELLOW}curl -X POST http://localhost:8000/api/v1/search \\${NC}"
    echo -e "      ${YELLOW}  -H 'Content-Type: application/json' \\${NC}"
    echo -e "      ${YELLOW}  -d '{\"query\": \"你的搜索关键词\", \"top_k\": 5}'${NC}"
    echo ""
    echo -e "${GREEN}✅ 向量数据已保存到: ./data/chroma/${NC}"
else
    echo -e "${RED}❌ 向量化测试失败${NC}"
    echo -e "${YELLOW}💡 请检查日志输出查找错误原因${NC}"
    exit 1
fi
