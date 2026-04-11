# 🎯 快速指南：将笔记向量化

这是一个简明扼要的指南，帮助你快速完成笔记向量化。

## ⚡ 超快速开始（5分钟）

### 1️⃣ 一键启动测试

```bash
cd /Users/didi/Downloads/panth/local-rag-system
chmod +x quick_test.sh
./quick_test.sh
```

**就这样！** 脚本会自动完成：
- ✅ 检查Python环境
- ✅ 创建虚拟环境
- ✅ 安装所有依赖
- ✅ 收集笔记文件
- ✅ 执行向量化
- ✅ 测试搜索

---

## 📝 手动步骤（如果不用脚本）

### 1. 进入项目目录
```bash
cd /Users/didi/Downloads/panth/local-rag-system
```

### 2. 创建虚拟环境
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 准备笔记
```bash
mkdir -p ./data/uploads

# 复制你的笔记文件
cp /Users/didi/Downloads/panth/*.md ./data/uploads/
```

### 5. 运行向量化
```bash
python3 test_local_vectorization.py
```

---

## 🔍 查看结果

### 方式1：检查向量数据库
```bash
ls -lh ./data/chroma/
# 应该看到ChromaDB的数据文件
```

### 方式2：Python验证
```python
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from src.store.vector_stores.chroma_store import ChromaVectorStore

store = ChromaVectorStore()
count = len(store.collection.get()["ids"])
print(f"✅ 成功！数据库包含 {count} 个向量")
EOF
```

---

## 🌐 启动完整服务

### 启动API服务
```bash
./scripts/serve.sh
```

### 打开Web界面
```
http://localhost:8000/docs
```

### 测试搜索
```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "你想搜索的内容",
    "top_k": 5,
    "rerank_enabled": true
  }'
```

---

## 📊 支持的文件格式

| 格式 | 说明 |
|------|------|
| `.md` | Markdown文档 |
| `.txt` | 纯文本 |
| `.docx` | Word文档 |
| `.pdf` | PDF文档 |
| `.pptx` | PowerPoint演示文稿 |
| `.py/.js/.java` | 代码文件 |

---

## 🐛 常见问题

### Q: 显示"CUDA not available"？
**A**: 正常的。系统会自动使用CPU，会稍微慢一点。

### Q: 向量化很慢？
**A**: 首次运行需要下载模型（约1GB），之后会缓存。

### Q: 如何添加更多笔记？
**A**: 将文件放入`./data/uploads`，重新运行`python3 test_local_vectorization.py`

### Q: 数据在哪里？
**A**: 向量数据在`./data/chroma/`，元数据在SQLite数据库中。

### Q: 如何重置一切？
**A**:
```bash
rm -rf ./data/chroma/
rm -rf ./data/metadata/
# 然后重新运行向量化
```

---

## ✨ 关键特性

- 🚀 **快速向量化** - BGE-M3本地嵌入，无需API调用
- 🔍 **智能搜索** - 向量+关键词混合搜索+重排序优化
- 💾 **本地存储** - 所有数据本地化，隐私安全
- ⚡ **高性能** - 搜索延迟 < 500ms（P95）
- 📊 **可视化** - Web界面和CLI都支持
- 🔧 **易扩展** - 模块化设计，支持自定义

---

## 📚 更多信息

- 完整指南：[QUICK_START_GUIDE.md](QUICK_START_GUIDE.md)
- 项目评估：[PROJECT_COMPLETION_SUMMARY.md](PROJECT_COMPLETION_SUMMARY.md)
- API文档：启动服务后访问 http://localhost:8000/docs
- 测试示例：[TEST_NOTES_EXAMPLE.md](TEST_NOTES_EXAMPLE.md)

---

## 🎉 你已准备好了！

选择你喜欢的方式开始：

### 自动方式（推荐）
```bash
./quick_test.sh
```

### 手动方式
```bash
python3 test_local_vectorization.py
```

### API方式
```bash
./scripts/serve.sh
# 然后访问 http://localhost:8000/docs
```

祝使用愉快！如有问题，查看[QUICK_START_GUIDE.md](QUICK_START_GUIDE.md)的详细说明。
