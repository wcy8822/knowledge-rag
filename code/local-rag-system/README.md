# 本地知识库向量化系统

一个企业级的本地知识库向量化和检索系统，支持多种文档格式的智能处理、语义检索和知识管理。

## 🌟 核心特性

### 📚 多格式文档支持
- **Excel**: 智能表格解析，主键识别，行聚合策略
- **PPT**: 幻灯片内容提取，标题感知，备注处理
- **代码**: Python/JavaScript/Java/C++/Go/Rust多语言支持，结构化摘要
- **Markdown**: 标题感知切分，层次结构保持
- **通用**: PDF、Word、Text、HTML等格式

### 🔍 混合检索引擎
- **向量检索**: 本地BGE-M3嵌入模型，语义相似度搜索
- **BM25检索**: 传统关键词搜索，精确匹配
- **智能融合**: 向量相似度0.6 + BM25 0.4权重
- **重排序**: BGE-reranker-base二次优化，Top-K→Top-N

### 🛡️ 安全合规
- **完全本地**: 默认本地嵌入，数据不上传云端
- **可选云端**: OpenAI等云端嵌入可选，带脱敏管道
- **最小暴露**: 问答阶段只向LLM发送少量Top-N片段
- **审计日志**: 完整操作记录，可追溯

### 📊 企业级监控
- **实时指标**: Hit@K、nDCG、延迟、空集率监控
- **性能统计**: 检索准确率、LLM响应时间、并发量
- **质量评估**: 基础性分数，引用完整性检查

## 🚀 快速开始

### 环境要求
- Python 3.9+
- 8GB+ RAM（推荐16GB）
- 存储空间：文档大小 × 3（用于向量存储）

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd local-rag-system
```

2. **环境设置**
```bash
# 运行自动化设置脚本
chmod +x scripts/*.sh
./scripts/setup.sh
```

3. **文档摄入**
```bash
# 将文档放入 data/uploads 目录
./scripts/ingest.sh --input-dir ./data/uploads
```

4. **启动服务**
```bash
# 启动API服务
./scripts/serve.sh
```

5. **访问服务**
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health
- 系统信息: http://localhost:8000/info

## 📖 API 使用示例

### 搜索文档
```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "2024年第一季度销售数据",
    "top_k": 6,
    "rerank_enabled": true,
    "filters": {
      "file_types": ["excel"]
    }
  }'
```

### 智能问答
```bash
curl -X POST "http://localhost:8000/api/v1/search/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "产品A的销售额是多少？",
    "top_k": 5,
    "rerank_enabled": true
  }'
```

### 摄入文档
```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": ["/path/to/document.xlsx", "/path/to/document.md"],
    "force_reprocess": false
  }'
```

## ⚙️ 配置说明

### 主要配置文件: `config.yaml`

```yaml
# 文档处理配置
document:
  supported_formats: ["pdf", "xlsx", "pptx", "md", "docx", "txt", "html", "py", "js", "java"]
  chunk_size: 750              # 块大小（token）
  chunk_overlap: 0.15         # 重叠比例
  max_file_size_mb: 50        # 最大文件大小

# 嵌入配置
embedding:
  provider: "local"                    # local | openai | azure
  model_name: "BAAI/bge-m3"          # BGE-M3 模型
  device: "cpu"                        # cpu | cuda
  batch_size: 32                       # 批处理大小
  normalize_embeddings: true           # 向量归一化

# 检索配置
retrieval:
  hybrid_search:
    enabled: true
    vector_weight: 0.6               # 向量权重
    bm25_weight: 0.4                 # BM25权重
    top_k: 20                       # 初始检索数量
  
  reranker:
    enabled: true
    model_name: "BAAI/bge-reranker-base"
    top_n: 6                         # 最终结果数量
```

## 🏗️ 系统架构

```
文档文件 → 解析器 → 文本切分 → 本地嵌入 → 向量存储
    ↓                                               ↓
ChromaDB ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← 
    ↓
混合检索 → 重排序 → API响应 → 用户界面
```

### 核心组件

1. **Ingest模块**
   - 多格式解析器（Excel、PPT、代码、Markdown等）
   - 智能文本切分
   - 元数据提取和存储

2. **Store模块**
   - BGE-M3本地嵌入服务
   - ChromaDB向量存储
   - SQLite元数据管理

3. **Search模块**
   - 混合检索引擎
   - BGE-reranker重排序
   - BM25全文搜索

4. **Serve模块**
   - FastAPI REST服务
   - 响应生成和会话管理
   - 实时监控和审计

## 📊 性能指标

### 检索质量
- **Hit@5**: ≥0.85（前5个结果命中率）
- **nDCG@5**: ≥0.82（归一化折损累积增益）
- **空集率**: ≤0.05（无结果查询比例）

### 系统性能
- **搜索延迟**: P95 < 500ms
- **并发处理**: 100 QPS
- **嵌入吞吐**: 1000 文档/分钟

## 🔧 开发和部署

### 开发模式
```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
pytest tests/ -v

# 代码格式化
black src/
isort src/

# 类型检查
mypy src/
```

### 生产部署
```bash
# Docker部署
docker build -t local-rag-system .
docker run -p 8000:8000 -v ./data:/app/data local-rag-system

# 或使用docker-compose
docker-compose up -d
```

## 📁 项目结构

```
local-rag-system/
├── src/                    # 源代码
│   ├── models/             # 数据模型
│   ├── ingest/             # 文档处理模块
│   ├── store/              # 存储模块
│   ├── search/             # 检索模块
│   └── serve/              # API服务模块
├── tests/                  # 测试用例
├── scripts/                # 脚本工具
├── data/                   # 数据目录
├── config.yaml.template     # 配置模板
├── requirements.txt         # 依赖包
└── README.md              # 项目文档
```

## 🔍 故障排查

### 常见问题

1. **内存不足**
```bash
# 减少批处理大小
export EMBEDDING_BATCH_SIZE=16
export CHROMA_BATCH_SIZE=50
```

2. **GPU不可用**
```bash
# 强制使用CPU
export EMBEDDING_DEVICE=cpu
```

3. **端口冲突**
```bash
# 使用不同端口
export PORT=8001
./scripts/serve.sh
```

### 日志查看
```bash
# 应用日志
tail -f logs/app.log

# 访问日志
tail -f logs/access.log

# 系统状态
curl http://localhost:8000/health
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙋 致谢

- [BGE](https://github.com/FlagOpen/FlagEmbedding) - 优秀的中文嵌入模型
- [ChromaDB](https://www.trychroma.com/) - 开源向量数据库
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化的Python Web框架
- [Sentence Transformers](https://www.sbert.net/) - 优秀的嵌入模型库

## 📞 支持

- 文档: [项目Wiki](wiki-link)
- 问题: [GitHub Issues](issues-link)
- 讨论: [GitHub Discussions](discussions-link)

---

**注意**: 这是一个企业级的本地RAG系统，适合对数据隐私有严格要求的企业和组织使用。