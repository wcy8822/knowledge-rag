#!/bin/bash
# 向量化进度检查脚本

echo "======================================"
echo "📊 向量化进度检查"
echo "======================================"
echo ""

# 检查收集报告
if [ -f "logs/collection_report_"*".json" ]; then
    latest_collection=$(ls -t logs/collection_report_*.json | head -1)
    echo "✅ 阶段1: 文件收集 - 已完成"
    echo "   报告: $latest_collection"
    python3 -c "
import json
with open('$latest_collection', 'r') as f:
    r = json.load(f)
    print(f'   文件数: {r[\"metadata\"][\"unique_files\"]}')
    print(f'   大小: {r[\"metadata\"][\"total_size_mb\"]:.2f} MB')
"
    echo ""
else
    echo "❌ 阶段1: 文件收集 - 未完成"
    echo ""
fi

# 检查向量化报告
if [ -f "logs/vectorization_report_"*".json" ]; then
    latest_vectorization=$(ls -t logs/vectorization_report_*.json | head -1)
    echo "✅ 阶段2: 向量化处理 - 已完成"
    echo "   报告: $latest_vectorization"
    python3 -c "
import json
with open('$latest_vectorization', 'r') as f:
    r = json.load(f)
    print(f'   处理文件: {r[\"metadata\"][\"successful_files\"]}/{r[\"metadata\"][\"total_files\"]}')
    print(f'   生成chunks: {r[\"metadata\"][\"total_chunks\"]}')
    print(f'   生成embeddings: {r[\"metadata\"][\"total_embeddings\"]}')
    print(f'   耗时: {r[\"metadata\"][\"processing_time_seconds\"]:.2f}秒')
    print(f'   吞吐量: {r[\"metadata\"][\"throughput_per_minute\"]:.1f} 文件/分钟')
"
    echo ""
else
    echo "⏳ 阶段2: 向量化处理 - 进行中..."
    echo "   (这可能需要30-50分钟)"
    echo ""
fi

# 检查验证报告
if [ -f "logs/verification_report_"*".json" ]; then
    latest_verification=$(ls -t logs/verification_report_*.json | head -1)
    echo "✅ 阶段3: 三层验证 - 已完成"
    echo "   报告: $latest_verification"
    echo ""
else
    echo "⏳ 阶段3: 三层验证 - 待执行"
    echo ""
fi

# 检查ChromaDB
echo "🔍 检查依赖:"
python3 -c "import chromadb; print('   ✅ ChromaDB已安装')" 2>/dev/null || echo "   ⏳ ChromaDB安装中..."
python3 -c "from sentence_transformers import SentenceTransformer; print('   ✅ sentence-transformers已安装')" 2>/dev/null || echo "   ❌ sentence-transformers未安装"

echo ""
echo "======================================"
echo "💡 提示:"
echo "   - 重新运行此脚本: bash check_progress.sh"
echo "   - 查看详细报告: cat logs/*.json | python3 -m json.tool"
echo "======================================"
