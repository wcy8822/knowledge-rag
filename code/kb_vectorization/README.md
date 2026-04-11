# 本地知识库全量向量化自动化系统

**版本**: v1.0
**日期**: 2026-03-01
**核心原则**: 数据绝不上云，所有内容100%本地处理

---

## 项目简介

在 M3 Mac (16GB 内存) 本地环境，构建一套全自动、可复用、安全可控的本地知识库向量化体系，实现海量文档的本地向量化、存储、检索和 AI 调用，同时确保所有数据绝不上传云端。

### 核心特性

| 特性 | 说明 |
|------|------|
| 🏠 本地优先 | 所有数据存储在本地，不上传云端 |
| 🔐 安全可控 | 仅本机可访问，数据脱敏处理 |
| ⚡ 高效处理 | 分批次向量化，内存峰值 ≤ 12GB |
| 🔄 自动更新 | 文件变化自动检测和更新 |
| 🔍 智能检索 | 支持关键词、向量、混合检索 |
| 🌐 通用接口 | REST API，支持多 AI 调用 |

---

## 目录结构

```
kb_vectorization/
├── README.md                      # 项目说明
├── requirements.txt               # Python 依赖
│
├── config/                       # 配置目录
│   └── config.yaml              # 主配置文件
│
├── core/                        # 核心模块
│   ├── base.py                  # 基类定义
│   ├── config.py                # 配置加载
│   ├── utils.py                 # 工具函数
│   ├── scanner.py               # 文件扫描
│   ├── vectorizer.py            # 向量化
│   ├── storage.py               # 向量存储
│   ├── retriever.py             # 检索
│   └── updater.py               # 自动更新
│
├── api/                         # API 层
│   ├── server.py                # API 服务
│   ├── schemas.py               # 数据模型
│   └── middleware.py            # 中间件
│
├── logs/                        # 日志目录
├── data/                        # 数据目录
│   ├── vector_db/               # 向量库
│   └── stats/                   # 统计数据
│
├── scripts/                     # 脚本目录
│   ├── install.sh               # 安装脚本
│   ├── scan.sh                  # 扫描脚本
│   ├── vectorize.sh             # 向量化脚本
│   ├── start_api.sh             # 启动 API
│   ├── stop_api.sh              # 停止 API
│   └── check_status.sh          # 状态检查
│
└── docs/                        # 文档目录
    ├── 01_需求规格说明书.md
    ├── 02_系统架构设计.md
    ├── 03_API接口文档.md
    ├── 04_用户操作手册.md
    ├── 05_安全说明文档.md
    └── 06_部署与运维指南.md
```

---

## 快速开始

### 1. 安装

```bash
# 克隆项目（如果需要）
# cd /path/to/project

# 运行安装脚本
cd /Users/didi/Downloads/panth/kb_vectorization
./scripts/install.sh
```

### 2. 配置

编辑 `config/config.yaml` 文件，配置扫描目录等参数：

```yaml
scan:
  directories:
    - "/Users/didi/knowledge_base_vectorization"
    - "/Users/didi/Downloads/panth/docs"
```

### 3. 扫描文件

```bash
./scripts/scan.sh
```

### 4. 向量化

```bash
# 正常模式（大批次）
./scripts/vectorize.sh

# MVP 模式（小批次测试）
./scripts/vectorize.sh --mvp
```

### 5. 启动 API 服务

```bash
# 前台运行
./scripts/start_api.sh

# 后台运行
./scripts/start_api.sh --daemon

# 带文件监控运行
./scripts/start_api.sh --daemon --monitor
```

### 6. 调用 API

```bash
# 健康检查
curl http://127.0.0.1:8000/api/v1/health

# 搜索文档
curl -X POST http://127.0.0.1:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "商户画像", "top_k": 5}'

# 获取统计信息
curl http://127.0.0.1:8000/api/v1/stats
```

---

## API 接口

### 健康检查

```http
GET /api/v1/health
```

### 搜索文档

```http
POST /api/v1/search
Content-Type: application/json

{
  "query": "搜索关键词",
  "top_k": 5,
  "search_type": "hybrid",
  "filters": {"category": "商户画像"}
}
```

### 扫描文件

```http
POST /api/v1/scan
Content-Type: application/json

{
  "directories": ["/path/to/directory"]
}
```

### 批量向量化

```http
POST /api/v1/vectorize
Content-Type: application/json

{
  "files": ["/path/to/file1.md", "/path/to/file2.sql"]
}
```

### 获取统计信息

```http
GET /api/v1/stats
```

---

## 配置说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `system.memory_limit` | 12 | 内存限制（GB） |
| `scan.directories` | [] | 扫描目录列表 |
| `vectorize.batch_size` | 500 | 批次大小 |
| `storage.type` | chroma | 向量库类型 |
| `api.port` | 8000 | API 端口 |
| `security.localhost_only` | true | 仅允许本机访问 |

---

## 安全原则

### 🔴 严禁上传云端

- 原始文档（MD/SQL/代码/表结构）
- 真实内容、业务数据、敏感信息
- 向量数据

### 🟢 允许 AI 参与

- 项目结构设计
- 程序框架
- 流程逻辑
- 代码编写
- 接口定义

---

## 性能指标

| 指标 | 目标值 |
|------|--------|
| 内存占用 | ≤ 12GB |
| 处理速度 | ≤ 30秒/文件 |
| API 响应 | ≤ 500ms |
| 支持文件数 | 10,000+ |

---

## 开发文档

- [需求规格说明书](docs/01_需求规格说明书.md)
- [系统架构设计](docs/02_系统架构设计.md)
- [API 接口文档](docs/03_API接口文档.md)
- [用户操作手册](docs/04_用户操作手册.md)
- [安全说明文档](docs/05_安全说明文档.md)
- [部署与运维指南](docs/06_部署与运维指南.md)

---

## 常见问题

### Q1: 如何切换向量库类型？

编辑 `config/config.yaml`：

```yaml
storage:
  type: "faiss"  # 或 "chroma"
```

### Q2: 如何添加新的文件类型支持？

1. 在 `core/vectorizer.py` 中继承 `FileParser`
2. 实现 `can_parse()` 和 `parse()` 方法
3. 在 `Vectorizer` 中注册新解析器

### Q3: 内存不足怎么办？

- 减小批次大小：`vectorize.batch_size`
- 使用 MVP 模式：`./scripts/vectorize.sh --mvp`
- 定期释放内存：系统会自动处理

---

## 许可证

本项目仅供个人学习使用。

---

**版本**: v1.0
**日期**: 2026-03-01
**核心**: 本地优先，数据不上云
