# 🚀 本地RAG系统 - 快速启动指南

## 目标
将你的本地笔记文件（Markdown、TXT等）向量化，通过RAG系统进行智能搜索和问答。

## 📋 前置要求
- Python 3.9+ ✅ (你已有 3.9.6)
- 8GB+ RAM （推荐16GB）
- 磁盘空间：笔记文件大小 × 3（用于向量存储）

---

## 🎯 3步快速开始

### 步骤1️⃣：环境准备（5分钟）

#### 1.1 创建虚拟环境
```bash
cd /Users/didi/Downloads/panth/local-rag-system
python3 -m venv venv
source venv/bin/activate
```

#### 1.2 安装依赖
```bash
# 升级pip
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt
```

**预期时间**：3-5分钟（取决于网络速度）

**验证安装**：
```bash
python3 -c "from sentence_transformers import SentenceTransformer; print('✅ 依赖安装成功')"
```

---

### 步骤2️⃣：准备笔记文件（2分钟）

#### 2.1 创建笔记目录
```bash
mkdir -p ./data/uploads
```

#### 2.2 复制你的笔记文件

**方式A：手动复制**
```bash
# 将你的笔记文件复制到上述目录
cp /path/to/your/notes/*.md ./data/uploads/
cp /path/to/your/notes/*.txt ./data/uploads/
```

**方式B：从项目目录收集**
```bash
# 如果你的笔记在panth目录下
cp /Users/didi/Downloads/panth/*.md ./data/uploads/
cp /Users/didi/Downloads/panth/周报润色记录/*.md ./data/uploads/
```

#### 2.3 验证文件
```bash
ls -la ./data/uploads/
# 应该能看到你的笔记文件
```

---

### 步骤3️⃣：运行向量化（5-15分钟）

#### 3.1 执行向量化测试
```bash
python3 test_local_vectorization.py
```

**预期输出**：
```
============================================================
🎯 本地RAG系统 - 笔记向量化测试
============================================================

✅ 初始化向量化系统

📂 第1步：收集笔记文件
------------------------------------------------------------
📚 找到 5 个笔记文件
   - ./data/uploads/笔记1.md
   - ./data/uploads/笔记2.md
   - ...

🚀 开始向量化 5 个文件...

[1/5] 处理: 笔记1.md
   ✅ 解析成功，生成 12 个chunks
   💾 存储成功，ID: [...uuid...]

📊 向量化完成：
   ✅ 成功处理: 5/5
   📄 总chunks数: 45
   ❌ 失败文件: 0

📈 系统统计:
   📦 向量数量: 45
   🗄️  数据库: ChromaDB
   🧠 嵌入模型: BAAI/bge-m3
   ⚙️  运行设备: cpu

🔍 第4步：测试搜索功能
   ...

✅ 向量化测试完成！
```

---

## ✅ 验证向量化成功

### 检查点1：向量数据库
```bash
ls -la ./data/chroma/
# 应该看到ChromaDB生成的文件
```

### 检查点2：向量数量
```python
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from src.store.vector_stores.chroma_store import ChromaVectorStore
store = ChromaVectorStore()
collection = store.collection
if collection:
    vector_count = len(collection.get()["ids"])
    print(f"✅ 向量数据库包含 {vector_count} 个向量")
else:
    print("❌ 向量数据库为空")
EOF
```

---

## 🌐 启动API服务

一旦向量化成功，你可以启动完整的RAG系统：

### 方式A：使用脚本（推荐）
```bash
./scripts/serve.sh
```

### 方式B：手动启动
```bash
source venv/bin/activate
python3 src/main.py
```

**预期输出**：
```
2025-01-26 10:30:00 - INFO - Starting Local RAG System API on 0.0.0.0:8000
Uvicorn running on http://0.0.0.0:8000
```

---

## 🔍 测试API接口

### 方式A：Web界面（推荐）
打开浏览器访问：
```
http://localhost:8000/docs
```

界面上有所有API接口的交互式文档。

### 方式B：命令行测试

#### 1. 搜索笔记
```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "2025年第一季度",
    "top_k": 5,
    "rerank_enabled": true
  }'
```

**预期响应**：
```json
{
  "query": "2025年第一季度",
  "results": [
    {
      "text": "2025年第一季度销售总结...",
      "score": 0.876,
      "source_file": "季度报告.md"
    },
    ...
  ]
}
```

#### 2. 智能问答
```bash
curl -X POST "http://localhost:8000/api/v1/search/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "最近完成了什么工作？",
    "top_k": 5,
    "rerank_enabled": true
  }'
```

**预期响应**：
```json
{
  "query": "最近完成了什么工作？",
  "answer": "根据您的笔记，最近完成的工作包括...",
  "sources": [
    {"file": "工作总结.md", "confidence": 0.92}
  ]
}
```

---

## 📊 系统架构图

```
你的笔记文件
    ↓
[文档解析器] → 提取文本内容
    ↓
[智能切分] → 750 tokens/chunk
    ↓
[BGE-M3嵌入] → 生成768维向量
    ↓
[ChromaDB] → 存储向量 + 元数据
    ↓
[混合搜索] → 向量搜索 + BM25关键词搜索
    ↓
[重排序] → BGE-Reranker优化结果
    ↓
[FastAPI] → RESTful接口
    ↓
[用户应用] → Web/CLI/移动端
```

---

## 🛠️ 常见问题

### Q1：向量化很慢怎么办？
**A**: 这是正常的。BGE-M3模型首次运行需要下载（约1GB），之后会缓存。

```bash
# 可以调整配置加速
# config.yaml:
embedding:
  batch_size: 64  # 改大这个数字
  device: "cpu"   # 如有GPU，改为"cuda"
```

### Q2：遇到"CUDA not available"错误？
**A**: 这是正常的，系统会自动回退到CPU。如果有GPU，可以安装PyTorch GPU版本。

### Q3：向量数据库在哪里？
**A**: 在 `./data/chroma/` 目录下，可以删除后重新生成。

### Q4：如何增加更多笔记？
**A**: 只需将新文件放入 `./data/uploads/` 并重新运行：
```bash
python3 test_local_vectorization.py
```

### Q5：如何修改搜索参数？
**A**: 编辑 `config.yaml`：
```yaml
retrieval:
  hybrid_search:
    vector_weight: 0.6    # 向量搜索权重
    bm25_weight: 0.4      # 关键词搜索权重
    top_k: 20             # 初始检索数量

  reranker:
    top_n: 6              # 最终返回数量
```

---

## 📈 性能预期

| 指标 | 预期值 | 说明 |
|------|--------|------|
| **向量化速度** | 100-500 文档/分钟 | 取决于文件大小和CPU |
| **搜索延迟** | 100-500ms | P95延迟 |
| **搜索准确率** | Hit@5 > 0.85 | 前5个结果至少1个相关 |
| **内存使用** | 2-4GB | ChromaDB + 模型 |
| **存储空间** | 原文件×3 | 向量 + 元数据 |

---

## 🚀 高级用法

### 添加自定义解析器
```python
# 在 src/ingest/parsers/ 下创建新的解析器
from .base_parser import BaseParser

class YourFormatParser(BaseParser):
    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith('.your_format')

    def parse(self, file_path: str):
        # 实现你的解析逻辑
        pass
```

### 配置Qdrant数据库（高性能）
```yaml
# config.yaml
vector_db:
  provider: "qdrant"
  qdrant:
    host: "localhost"
    port: 6333
```

### 使用云端嵌入模型
```yaml
embedding:
  provider: "openai"
  cloud:
    enabled: true
    api_key_env: "OPENAI_API_KEY"
    model: "text-embedding-3-small"
```

---

## 📞 获取帮助

- **查看日志**: `tail -f logs/app.log`
- **系统健康检查**: `curl http://localhost:8000/health`
- **API文档**: `http://localhost:8000/docs`
- **项目文档**: 查看 `docs/` 目录

---

## ✅ 成功标志

当你看到以下输出时，说明向量化成功：

```
✅ 向量化测试完成！
✅ 向量数据库包含 45 个向量
✅ 搜索功能测试通过
✅ API服务启动成功
```

祝你使用愉快！ 🎉

---

**版本**: 1.0
**最后更新**: 2025-01-26
**维护者**: Local RAG System Team
