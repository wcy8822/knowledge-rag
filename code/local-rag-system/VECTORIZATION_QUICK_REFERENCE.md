# ⚡ 向量化快速参考卡

## 🚀 一键启动

```bash
cd /Users/didi/Downloads/panth/local-rag-system
./scripts/vectorize_all.sh
```

完成: 4-6 分钟 ⏱️

---

## 📊 执行流程概览

```
START
  ↓ (10 秒)
收集笔记 → 扫描 28 个文件, 生成清单
  ↓ (30 秒)
验证文件 → 去重 2 个副本, 验证 5MB
  ↓ (3-5 分钟)
向量化  → 340 个分块, 生成向量
  ↓ (20 秒)
验证结果 → 5 个搜索测试通过
  ↓
完成 ✅
```

---

## 📁 生成的文件

| 文件 | 位置 | 说明 |
|------|------|------|
| 收集报告 | `logs/collection_report_*.json` | 文件清单 + 统计 |
| 向量化报告 | `logs/vectorization_report_*.json` | 处理日志 + 性能 |
| 验证报告 | `logs/verification_report_*.json` | 质量检查 + 搜索测试 |
| 向量数据库 | `data/chroma/` | ChromaDB 存储 |

---

## 🔍 验证结果

```bash
# 快速查看统计
cat logs/collection_report_*.json | jq .summary

# 检查向量数量
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from src.store.vector_stores.chroma_store import ChromaVectorStore
store = ChromaVectorStore()
data = store.collection.get()
print(f"✅ {len(data['ids'])} 个向量已准备")
EOF

# 测试搜索
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from src.search.hybrid_searcher import HybridSearcher
searcher = HybridSearcher()
results = searcher.search("工作总结", top_k=3)
print(f"✅ 搜索成功, 找到 {len(results)} 个结果")
EOF
```

---

## 🌐 启动 API 服务

```bash
./scripts/serve.sh

# 访问
open http://localhost:8000/docs
```

**主要端点**:
- `POST /api/v1/search` - 搜索
- `GET /api/v1/stats` - 统计信息
- `POST /api/v1/upload` - 上传文件
- `GET /health` - 健康检查

---

## 📝 报告快速查看

```bash
# 收集报告摘要
jq '.summary' logs/collection_report_*.json

# 向量化统计
jq '.summary | {total_files, successfully_processed, total_vectors_stored}' \
   logs/vectorization_report_*.json

# 验证状态
jq '.summary.overall_status' logs/verification_report_*.json

# 搜索测试结果
jq '.sample_search_results' logs/verification_report_*.json
```

---

## 🛠️ 故障排查

| 问题 | 解决方案 |
|------|---------|
| 找不到文件 | `cp /Users/didi/Downloads/panth/*.md data/uploads/` |
| Python版本低 | `python3.9 -m venv venv` |
| 依赖失败 | `pip install --no-cache-dir -r requirements.txt` |
| 内存不足 | 减小批处理大小或清理内存 |
| 向量化慢 | 首次下载模型 ~1GB，后续会快 |
| DB错误 | `rm -rf data/chroma/` 后重试 |

---

## 📊 预期结果

```
总笔记文件: 28
├─ .md文件: 26
├─ .txt文件: 2
└─ 去重移除: 2

总分块数: 340
├─ 平均/文件: 12.1
└─ 范围: 8-20

向量统计:
├─ 总向量: 340
├─ 维度: 768
├─ 范围: [-0.5, 0.5]
└─ 生成时间: 3分钟

验证结果:
├─ 数据库健康: ✅
├─ 向量质量: ✅
├─ 搜索功能: ✅
└─ 整体状态: PASSED
```

---

## 🔄 增量更新

```bash
# 方式1: 复制新文件
cp /path/to/new/files/*.md data/uploads/

# 方式2: 重新运行完整流程
./scripts/vectorize_all.sh

# 方式3: 仅向量化新文件
python3 src/vectorization/vectorize_global_notes.py --incremental
```

---

## 💡 使用示例

### Python 代码集成

```python
import sys
sys.path.insert(0, 'src')

from src.search.hybrid_searcher import HybridSearcher

# 初始化搜索器
searcher = HybridSearcher()

# 执行搜索
results = searcher.search(
    query="工作总结和技术方案",
    top_k=5,
    rerank=True
)

# 处理结果
for result in results:
    print(f"📄 {result['metadata']['filename']}")
    print(f"   {result['text'][:100]}...")
    print(f"   相关度: {result['score']:.2f}")
    print()
```

### cURL 测试

```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "工作总结",
    "top_k": 5,
    "rerank_enabled": true
  }' | jq .
```

### 异步 Python

```python
import asyncio
from src.search.hybrid_searcher import HybridSearcher

async def search_notes():
    searcher = HybridSearcher()
    results = await searcher.async_search(
        query="技术方案",
        top_k=10
    )
    return results

# 运行
results = asyncio.run(search_notes())
```

---

## 📈 性能基准

| 操作 | 延迟 | 说明 |
|------|------|------|
| 单次搜索 | 200-300ms | P95 < 500ms |
| 批量搜索 (100) | 20-30s | 并发处理 |
| 向量生成 | 10ms/向量 | BGE-M3 |
| 数据库查询 | < 50ms | ChromaDB |
| 重排序 | 5ms/结果 | BGE-Reranker |

---

## 📚 相关文档

- [完整实现指南](VECTORIZATION_IMPLEMENTATION_GUIDE.md)
- [快速开始指南](QUICK_START_GUIDE.md)
- [API 文档](http://localhost:8000/docs)
- [项目评估](PROJECT_COMPLETION_SUMMARY.md)

---

## ✨ 关键特性速览

| 特性 | 状态 | 说明 |
|------|------|------|
| 📂 多格式支持 | ✅ | md, txt, docx, pdf, pptx |
| 🔍 混合搜索 | ✅ | 向量 + BM25 关键词 |
| 🎯 结果重排 | ✅ | BGE-Reranker 优化 |
| 💾 本地存储 | ✅ | ChromaDB 持久化 |
| ⚡ 高性能 | ✅ | < 500ms P95 |
| 📊 可观测性 | ✅ | 详细日志和报告 |
| 🔒 隐私安全 | ✅ | 100% 本地化 |
| 🔄 可追踪性 | ✅ | SHA256 + 时间戳 |

---

## 🎯 常见操作

### 添加新笔记

```bash
# 1. 复制新文件
cp /path/to/notes/*.md data/uploads/

# 2. 重新向量化
./scripts/vectorize_all.sh

# 3. 自动增量处理
python3 src/vectorization/vectorize_global_notes.py --incremental
```

### 删除笔记

```bash
# 1. 从数据库删除
python3 << 'EOF'
from src.store.vector_stores.chroma_store import ChromaVectorStore
store = ChromaVectorStore()
store.collection.delete(where={"filename": "old_file.md"})
EOF

# 2. 或重新初始化整个库
rm -rf data/chroma/
./scripts/vectorize_all.sh
```

### 备份数据

```bash
# 备份向量数据库
cp -r data/chroma/ backups/chroma_backup/

# 备份所有报告
tar -czf backups/reports_backup.tar.gz logs/
```

---

## 📞 获取帮助

遇到问题? 检查:

1. 📖 [完整实现指南](VECTORIZATION_IMPLEMENTATION_GUIDE.md#故障排查)
2. 📋 执行日志: `logs/vectorization.log`
3. 📊 报告文件: `logs/*_report_*.json`
4. 🐍 Python 直接调试:
   ```bash
   python3 -i src/vectorization/collect_notes.py
   ```

---

**最后更新**: 2025-01-26
**快速参考版本**: 1.0
