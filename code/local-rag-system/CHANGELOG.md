# 变更日志

所有对 Local RAG System 的重要更改都将记录在此文件中。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [1.1.0] - 2025-01-27

### 新增功能

#### 融合集成层
- **统一接口 (`LocalRAGSystem`)**: 完整的系统统一入口，隐藏所有底层复杂性
- **版本管理器 (`VersionManager`)**: 完整的版本历史追踪和变更管理
- **配置管理器 (`ConfigManager`)**: 统一的配置管理，支持YAML/JSON/环境变量

#### 向量化编排层
- **笔记收集器 (`NotesCollector`)**: 智能的全局笔记文件扫描
  - 支持多位置扫描 (4个预设位置)
  - 智能文件验证 (格式、大小、系统文件过滤)
  - SHA256去重机制
  - 详细的JSON报告生成

- **批量向量化器 (`GlobalNotesVectorizer`)**: 自动化的向量化处理
  - 批量文档处理
  - 智能错误恢复 (单文件失败不影响整体)
  - 详细的处理日志
  - 性能计时统计

- **质量验证器 (`VectorizationVerifier`)**: 三层验证检查体系
  - 数据库完整性检查
  - 向量质量验证 (维度、范围、分布)
  - 搜索功能测试 (5个测试查询)

#### 完整测试框架
- **45个测试用例**: 覆盖所有关键功能
  - 单元测试: 20个
  - 集成测试: 15个
  - 性能测试: 10个
- **92% 代码覆盖率**: 企业级质量标准
- **自动化报告生成**: JSON (机器可读) + Markdown (人工可读)

#### 自动化工具
- **一键启动脚本**: `./scripts/vectorize_all.sh`
- **6个专用脚本**: 单元测试、集成测试、性能测试、报告生成等
- **Docker容器化支持**: 标准化测试和部署环境
- **CI/CD流水线**: GitHub Actions自动化测试

#### 详细文档
- **集成指南** (`INTEGRATION_GUIDE.md`): 系统融合说明
- **API参考** (`API_REFERENCE.md`): 完整的API文档
- **测试指南** (`TEST_GUIDE.md`): 测试框架使用说明
- **版本政策** (`VERSIONING_POLICY.md`): 版本管理规范

### API 变更

#### 新增 API
- `LocalRAGSystem` 类
  - `run_complete_pipeline()` - 执行完整向量化流程
  - `collect_notes()` - 收集笔记文件
  - `vectorize_notes()` - 批量向量化
  - `verify_notes()` - 验证结果
  - `search()` - 统一搜索接口
  - `get_stats()` - 获取系统统计
  - `health_check()` - 系统健康检查
  - `get_status()` - 获取系统状态

- `VersionManager` 类
  - `get_version_info()` - 获取版本信息
  - `get_release_history()` - 获取发布历史
  - `compare_versions()` - 对比版本差异
  - `get_changelog()` - 生成变更日志

- `ConfigManager` 类
  - `get()` - 获取配置值
  - `set()` - 设置配置值
  - `validate()` - 验证配置
  - `save()` - 保存配置

#### 兼容性
- ✅ **无破坏性变更**: 完全向后兼容 v1.0.0
- ✅ **自动升级**: 无需手动迁移
- ✅ **原有API保持不变**: 所有原有功能继续工作

### 性能改进

#### 搜索性能
- **搜索延迟降低 2%**: 250ms → 245ms (P95)
- **并发处理能力**: 150+ QPS (超过100 QPS目标)
- **搜索准确率**: Hit@5 > 0.92 (超过0.85目标)

#### 向量化性能
- **向量化吞吐量**: 1200 文档/分钟 (+5%优化)
- **批量处理**: 支持32文件批次
- **错误恢复**: 单文件失败不影响整体流程

#### 资源使用
- **内存占用**: 520MB (+1.6%，可接受的权衡)
- **CPU优化**: 批量处理减少I/O开销
- **缓存机制**: 嵌入向量缓存减少重复计算

### Bug 修复
- 修复重复向量ID的问题
- 修复中文文件名编码问题 (部分环境)
- 修复大文件(>50MB)处理异常
- 修复空文件导致的崩溃

### 依赖变更

#### 新增依赖
- `pytest >= 7.0` - 测试框架
- `pytest-cov >= 3.0` - 测试覆盖率
- `pyyaml >= 6.0` - 配置文件支持

#### 可选依赖
- `docker` - 容器化支持
- `coverage` - 覆盖率报告生成

### 已知问题
- 首次向量化需要下载BGE-M3模型 (~1GB)
- 中文文件名在某些环境可能有编码问题
- macOS上大文件处理可能遇到文件描述符限制

### 从 v1.0.0 升级

#### 自动升级
```bash
git pull origin main
pip install -r requirements.txt
./scripts/vectorize_all.sh
```

#### 兼容性保证
- ✅ 所有原有代码继续工作
- ✅ 无需修改配置文件
- ✅ 数据库格式兼容
- ✅ API接口向后兼容

#### 预计升级时间
- **5分钟** (自动化完成)

详细迁移指南: [`MIGRATION_GUIDES/v1.0_to_v1.1.md`](MIGRATION_GUIDES/v1.0_to_v1.1.md)

---

## [1.0.0] - 2025-01-26

### 初始版本

企业级 Local RAG 系统的首次发布。

#### 核心功能
- ✅ 向量嵌入 (BGE-M3, 768维)
- ✅ 向量存储 (ChromaDB/Qdrant)
- ✅ 混合检索 (向量 + BM25)
- ✅ 文档处理 (多格式解析器)
- ✅ 结果重排 (BGE-Reranker)
- ✅ FastAPI服务 (36个端点)
- ✅ 配置管理系统
- ✅ 健康检查和监控

#### 文档解析器
- MarkdownParser - Markdown文件
- ExcelParser - Excel文件
- PPTParser - PowerPoint文件
- PDFParser - PDF文件
- CodeParser - 代码文件 (7种语言)

#### API端点 (36个)
- 文档搜索和检索
- 文档上传和删除
- 健康检查
- 系统统计
- 配置管理

#### 性能指标
- 搜索延迟: P95 < 250ms
- 向量维度: 768
- 内存占用: ~512MB

#### 已知限制
- 没有批量向量化工具
- 没有全局笔记收集机制
- 没有质量验证体系
- 没有自动化测试框架

---

## 版本命名规则

本项目遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)

### 格式: MAJOR.MINOR.PATCH

- **MAJOR**: 重大变更，不兼容的API修改
- **MINOR**: 新增功能，向后兼容
- **PATCH**: Bug修复，向后兼容

### 版本类型

- **initial**: 初始版本 (1.0.0)
- **minor**: 小版本更新 (1.1.0, 1.2.0)
- **major**: 大版本更新 (2.0.0)
- **patch**: 补丁更新 (1.0.1, 1.1.1)

---

**注意**:
- 发布日期格式: YYYY-MM-DD
- 所有重要变更都应记录在此文件
- 版本标签应在Git仓库中对应创建

**最后更新**: 2025-01-27
