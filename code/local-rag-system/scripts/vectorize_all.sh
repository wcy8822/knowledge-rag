#!/bin/bash

# 一键向量化脚本
# 功能：自动完成收集、向量化、验证的完整流程

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}🚀 本地全局笔记向量化 - 一键启动${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "${CYAN}项目目录: ${PROJECT_DIR}${NC}"
echo -e "${CYAN}执行时间: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo -e "${BLUE}============================================================${NC}"

# 创建必要的目录
echo -e "\n${YELLOW}📁 准备工作目录...${NC}"
mkdir -p logs
mkdir -p data/chroma
echo -e "${GREEN}✅ 工作目录准备完成${NC}"

# 检查虚拟环境
echo -e "\n${YELLOW}🔧 检查Python环境...${NC}"
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 创建虚拟环境...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ 虚拟环境创建完成${NC}"
fi

# 激活虚拟环境
echo -e "${YELLOW}🔄 激活虚拟环境...${NC}"
source venv/bin/activate

# 检查依赖
if ! python3 -c "import chromadb" 2>/dev/null; then
    echo -e "${YELLOW}📥 安装项目依赖...${NC}"
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r requirements.txt
    echo -e "${GREEN}✅ 依赖安装完成${NC}"
else
    echo -e "${GREEN}✅ Python环境准备完成${NC}"
fi

# ============================================================
# 阶段1：收集笔记文件
# ============================================================
echo -e "\n${PURPLE}============================================================${NC}"
echo -e "${PURPLE}📋 阶段 1/3: 收集笔记文件${NC}"
echo -e "${PURPLE}============================================================${NC}"

echo -e "${YELLOW}⏳ 正在扫描全局笔记位置...${NC}"
python3 src/vectorization/collect_notes.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 阶段1完成：笔记收集成功${NC}"
else
    echo -e "${RED}❌ 阶段1失败：笔记收集出错${NC}"
    exit 1
fi

# 检查收集报告
COLLECTION_REPORT=$(ls -t logs/collection_report_*.json 2>/dev/null | head -1)
if [ -z "$COLLECTION_REPORT" ]; then
    echo -e "${RED}❌ 找不到收集报告${NC}"
    exit 1
fi

echo -e "${CYAN}📄 收集报告: ${COLLECTION_REPORT}${NC}"

# 显示收集统计
if command -v jq &> /dev/null; then
    TOTAL_FILES=$(jq -r '.summary.valid_notes' "$COLLECTION_REPORT")
    TOTAL_SIZE=$(jq -r '.summary.total_size_human' "$COLLECTION_REPORT")
    echo -e "${CYAN}📊 收集统计: ${TOTAL_FILES} 个文件, ${TOTAL_SIZE}${NC}"
fi

# ============================================================
# 阶段2：向量化处理
# ============================================================
echo -e "\n${PURPLE}============================================================${NC}"
echo -e "${PURPLE}🔮 阶段 2/3: 向量化处理${NC}"
echo -e "${PURPLE}============================================================${NC}"

echo -e "${YELLOW}⏳ 正在进行向量化处理...${NC}"
echo -e "${CYAN}   (这可能需要几分钟，请耐心等待)${NC}"

# 创建软链接到最新的收集报告
ln -sf "$(basename "$COLLECTION_REPORT")" logs/collection_report_latest.json

python3 src/vectorization/vectorize_global_notes.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 阶段2完成：向量化成功${NC}"
else
    echo -e "${RED}❌ 阶段2失败：向量化出错${NC}"
    exit 1
fi

# 检查向量化报告
VECTORIZATION_REPORT=$(ls -t logs/vectorization_report_*.json 2>/dev/null | head -1)
if [ -z "$VECTORIZATION_REPORT" ]; then
    echo -e "${RED}❌ 找不到向量化报告${NC}"
    exit 1
fi

echo -e "${CYAN}📄 向量化报告: ${VECTORIZATION_REPORT}${NC}"

# 显示向量化统计
if command -v jq &> /dev/null; then
    PROCESSED_FILES=$(jq -r '.summary.successfully_processed' "$VECTORIZATION_REPORT")
    TOTAL_VECTORS=$(jq -r '.summary.total_vectors_stored' "$VECTORIZATION_REPORT")
    echo -e "${CYAN}📊 向量化统计: ${PROCESSED_FILES} 个文件, ${TOTAL_VECTORS} 个向量${NC}"
fi

# ============================================================
# 阶段3：验证结果
# ============================================================
echo -e "\n${PURPLE}============================================================${NC}"
echo -e "${PURPLE}✅ 阶段 3/3: 验证结果${NC}"
echo -e "${PURPLE}============================================================${NC}"

echo -e "${YELLOW}⏳ 正在验证向量化结果...${NC}"

python3 src/vectorization/verify_vectorization.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 阶段3完成：验证成功${NC}"
else
    echo -e "${YELLOW}⚠️  阶段3警告：验证可能有问题${NC}"
fi

# 检查验证报告
VERIFICATION_REPORT=$(ls -t logs/verification_report_*.json 2>/dev/null | head -1)
if [ -z "$VERIFICATION_REPORT" ]; then
    echo -e "${YELLOW}⚠️  找不到验证报告${NC}"
else
    echo -e "${CYAN}📄 验证报告: ${VERIFICATION_REPORT}${NC}"

    # 显示验证统计
    if command -v jq &> /dev/null; then
        OVERALL_STATUS=$(jq -r '.summary.overall_status' "$VERIFICATION_REPORT")
        TOTAL_CHECKS=$(jq -r '.summary.checks_passed + .summary.checks_failed' "$VERIFICATION_REPORT")
        PASSED_CHECKS=$(jq -r '.summary.checks_passed' "$VERIFICATION_REPORT")
        echo -e "${CYAN}📊 验证统计: ${PASSED_CHECKS}/${TOTAL_CHECKS} 检查通过, 状态: ${OVERALL_STATUS}${NC}"
    fi
fi

# ============================================================
# 完成总结
# ============================================================
echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}🎉 全局笔记向量化完成！${NC}"
echo -e "${GREEN}============================================================${NC}"

echo -e "\n${CYAN}📊 完整统计信息:${NC}"
echo -e "${CYAN}------------------------------------------------------------${NC}"

# 收集所有报告信息
if command -v jq &> /dev/null && [ -n "$COLLECTION_REPORT" ] && [ -n "$VECTORIZATION_REPORT" ]; then
    echo -e "${CYAN}1️⃣  笔记收集:${NC}"
    echo -e "   • 收集文件: $(jq -r '.summary.valid_notes' "$COLLECTION_REPORT") 个"
    echo -e "   • 文件大小: $(jq -r '.summary.total_size_human' "$COLLECTION_REPORT")"
    echo -e "   • 去重移除: $(jq -r '.summary.duplicates_removed' "$COLLECTION_REPORT") 个"

    echo -e "\n${CYAN}2️⃣  向量化处理:${NC}"
    echo -e "   • 处理文件: $(jq -r '.summary.successfully_processed' "$VECTORIZATION_REPORT") 个"
    echo -e "   • 生成分块: $(jq -r '.summary.total_chunks' "$VECTORIZATION_REPORT") 个"
    echo -e "   • 存储向量: $(jq -r '.summary.total_vectors_stored' "$VECTORIZATION_REPORT") 个"
    echo -e "   • 成功率: $(jq -r '.summary.success_rate' "$VECTORIZATION_REPORT")"

    if [ -n "$VERIFICATION_REPORT" ]; then
        echo -e "\n${CYAN}3️⃣  验证结果:${NC}"
        echo -e "   • 总向量数: $(jq -r '.summary.total_vectors' "$VERIFICATION_REPORT") 个"
        echo -e "   • 总文档数: $(jq -r '.summary.total_documents' "$VERIFICATION_REPORT") 个"
        echo -e "   • 验证状态: $(jq -r '.summary.overall_status' "$VERIFICATION_REPORT")"
    fi
fi

echo -e "\n${CYAN}📂 生成的报告文件:${NC}"
echo -e "${CYAN}------------------------------------------------------------${NC}"
[ -n "$COLLECTION_REPORT" ] && echo -e "   📄 收集报告: ${COLLECTION_REPORT}"
[ -n "$VECTORIZATION_REPORT" ] && echo -e "   📄 向量化报告: ${VECTORIZATION_REPORT}"
[ -n "$VERIFICATION_REPORT" ] && echo -e "   📄 验证报告: ${VERIFICATION_REPORT}"

echo -e "\n${CYAN}💾 向量数据位置:${NC}"
echo -e "${CYAN}------------------------------------------------------------${NC}"
echo -e "   📁 ChromaDB: ./data/chroma/"
if [ -d "./data/chroma" ]; then
    DB_SIZE=$(du -sh ./data/chroma 2>/dev/null | awk '{print $1}')
    echo -e "   💿 数据库大小: ${DB_SIZE}"
fi

echo -e "\n${CYAN}🌐 后续步骤:${NC}"
echo -e "${CYAN}------------------------------------------------------------${NC}"
echo -e "   1️⃣  启动API服务:"
echo -e "      ${YELLOW}./scripts/serve.sh${NC}"
echo -e ""
echo -e "   2️⃣  访问Web界面:"
echo -e "      ${YELLOW}http://localhost:8000/docs${NC}"
echo -e ""
echo -e "   3️⃣  测试搜索:"
echo -e "      ${YELLOW}curl -X POST http://localhost:8000/api/v1/search \\\\${NC}"
echo -e "      ${YELLOW}  -H 'Content-Type: application/json' \\\\${NC}"
echo -e "      ${YELLOW}  -d '{\"query\": \"你的搜索关键词\", \"top_k\": 5}'${NC}"
echo -e ""
echo -e "   4️⃣  查看详细报告:"
echo -e "      ${YELLOW}cat ${COLLECTION_REPORT}${NC}"
echo -e "      ${YELLOW}cat ${VECTORIZATION_REPORT}${NC}"
if [ -n "$VERIFICATION_REPORT" ]; then
    echo -e "      ${YELLOW}cat ${VERIFICATION_REPORT}${NC}"
fi

echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}✅ 全部完成！向量化数据已准备就绪。${NC}"
echo -e "${GREEN}============================================================${NC}"

# 成功退出
exit 0
