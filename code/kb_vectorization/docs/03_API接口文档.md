# 本地知识库全量向量化自动化系统 - API 接口文档

**项目名称**: 本地知识库全量向量化自动化系统
**版本**: v1.0
**制定日期**: 2026-03-01

---

## 文档版本历史

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-01 | 初始版本 | Claude |

---

## 1. 概述

### 1.1 基本信息

| 项目 | 说明 |
|------|------|
| 协议 | HTTP/1.1 |
| 数据格式 | JSON |
| 字符编码 | UTF-8 |
| 访问限制 | 仅本机 (127.0.0.1) |
| 默认端口 | 8000 |
| API 前缀 | `/api/v1` |

### 1.2 访问地址

```
http://127.0.0.1:8000
```

### 1.3 通用请求头

| 请求头 | 说明 | 示例 |
|--------|------|------|
| Content-Type | 请求体类型 | `application/json` |
| Accept | 响应体类型 | `application/json` |

### 1.4 通用响应格式

#### 成功响应

```json
{
  "success": true,
  "data": {},
  "message": "操作成功"
}
```

#### 错误响应

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "details": "详细信息"
  }
}
```

---

## 2. 基础接口

### 2.1 根路径

获取系统基本信息。

**请求**

```
GET /
```

**响应示例**

```json
{
  "name": "本地知识库向量化系统",
  "version": "1.0.0",
  "description": "本地知识库全量向量化自动化系统",
  "endpoints": {
    "search": "/api/v1/search",
    "scan": "/api/v1/scan",
    "vectorize": "/api/v1/vectorize",
    "stats": "/api/v1/stats",
    "health": "/api/v1/health"
  }
}
```

---

## 3. 健康检查

### 3.1 健康检查

检查系统健康状态。

**请求**

```
GET /api/v1/health
```

**响应示例**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600.5,
  "components": {
    "store": "ok",
    "vectors": 12345,
    "retriever": "ok",
    "memory": "ok"
  }
}
```

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 状态：healthy, degraded, error |
| version | string | 版本号 |
| uptime | number | 运行时长（秒） |
| components | object | 组件状态 |

---

## 4. 搜索接口

### 4.1 搜索文档

根据查询文本搜索相关文档。

**请求**

```
POST /api/v1/search
Content-Type: application/json
```

**请求体**

```json
{
  "query": "商户画像覆盖率计算方法",
  "top_k": 5,
  "search_type": "hybrid",
  "filters": {
    "category": "商户画像"
  }
}
```

**请求字段**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 查询文本 |
| top_k | number | 否 | 返回结果数，默认5，最大50 |
| search_type | string | 否 | 搜索类型：keyword, vector, hybrid，默认hybrid |
| filters | object | 否 | 过滤条件 |

**搜索类型说明**

| 类型 | 说明 |
|------|------|
| keyword | 关键词检索 |
| vector | 向量相似度检索 |
| hybrid | 混合检索（推荐） |

**响应示例**

```json
{
  "success": true,
  "query": "商户画像覆盖率计算方法",
  "type": "hybrid",
  "total": 3,
  "query_time": 0.123,
  "results": [
    {
      "id": "uuid-1",
      "file_path": "/docs/商户画像.md",
      "file_name": "商户画像.md",
      "category": "商户画像",
      "chunk_index": 3,
      "chunk_text": "覆盖率计算方法：...",
      "similarity": 0.92,
      "metadata": {
        "file_type": ".md",
        "chunk_size": 256
      }
    },
    {
      "id": "uuid-2",
      "file_path": "/docs/数据分析.md",
      "file_name": "数据分析.md",
      "category": "商户画像",
      "chunk_index": 7,
      "chunk_text": "覆盖率指标定义...",
      "similarity": 0.85,
      "metadata": {}
    }
  ],
  "message": "找到 3 个相关结果"
}
```

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| query | string | 查询文本 |
| type | string | 搜索类型 |
| total | number | 结果数量 |
| query_time | number | 查询耗时（秒） |
| results | array | 结果列表 |
| message | string | 附加消息 |

**结果项字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 向量ID |
| file_path | string | 文件路径 |
| file_name | string | 文件名 |
| category | string | 分类 |
| chunk_index | number | 块索引 |
| chunk_text | string | 块文本（预览，已脱敏） |
| similarity | number | 相似度（0-1） |
| metadata | object | 元数据 |

---

## 5. 扫描接口

### 5.1 扫描文件

扫描指定目录下的文件。

**请求**

```
POST /api/v1/scan
Content-Type: application/json
```

**请求体**

```json
{
  "directories": ["/path/to/directory1", "/path/to/directory2"]
}
```

**请求字段**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| directories | array | 否 | 扫描目录列表，不传则使用配置中的目录 |

**响应示例**

```json
{
  "success": true,
  "total_files": 156,
  "total_size": 5242880,
  "by_type": {
    ".md": 100,
    ".sql": 30,
    ".py": 26
  },
  "by_category": {
    "商户画像": 50,
    "技术配置": 20,
    "数据表映射": 40,
    "资讯": 46
  },
  "scan_time": 0.523,
  "message": "扫描完成，找到 156 个文件"
}
```

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| total_files | number | 总文件数 |
| total_size | number | 总大小（字节） |
| by_type | object | 按文件类型统计 |
| by_category | object | 按业务分类统计 |
| scan_time | number | 扫描耗时（秒） |
| message | string | 附加消息 |

---

## 6. 向量化接口

### 6.1 批量向量化

批量向量化文件。

**请求**

```
POST /api/v1/vectorize
Content-Type: application/json
```

**请求体**

```json
{
  "files": ["/path/to/file1.md", "/path/to/file2.sql"]
}
```

**请求字段**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| files | array | 是 | 文件路径列表 |

**响应示例**

```json
{
  "success": true,
  "processed_files": 95,
  "total_chunks": 380,
  "failed_files": 2,
  "duration": 25.6,
  "message": "处理完成，生成 380 个向量"
}
```

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| processed_files | number | 处理文件数 |
| total_chunks | number | 生成块数 |
| failed_files | number | 失败文件数 |
| duration | number | 处理耗时（秒） |
| message | string | 附加消息 |

---

## 7. 统计接口

### 7.1 获取统计信息

获取系统统计信息。

**请求**

```
GET /api/v1/stats
```

**响应示例**

```json
{
  "success": true,
  "stats": {
    "system": {
      "name": "本地知识库向量化系统",
      "version": "1.0.0",
      "uptime": 7200.5
    },
    "storage": {
      "type": "chroma",
      "collection_name": "kb_vectors",
      "total_vectors": 12345,
      "persist_directory": "./data/vector_db/chroma"
    },
    "config": {
      "scan_dirs": ["/path/to/docs"],
      "file_types": [".md", ".sql"],
      "batch_size": 500,
      "vector_dim": 384
    }
  }
}
```

**响应字段**

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| stats | object | 统计数据 |

---

## 8. 监控接口

### 8.1 启动文件监控

启动文件系统监控。

**请求**

```
POST /api/v1/monitor/start
```

**响应示例**

```json
{
  "success": true,
  "message": "文件监控已启动"
}
```

### 8.2 停止文件监控

停止文件系统监控。

**请求**

```
POST /api/v1/monitor/stop
```

**响应示例**

```json
{
  "success": true,
  "message": "文件监控已停止"
}
```

---

## 9. 错误代码

### 9.1 错误代码列表

| 代码 | HTTP 状态 | 说明 |
|------|----------|------|
| UNKNOWN | 500 | 未知错误 |
| INVALID_REQUEST | 400 | 无效请求 |
| METHOD_NOT_ALLOWED | 405 | 方法不支持 |
| NOT_FOUND | 404 | 资源不存在 |
| SEARCH_FAILED | 500 | 搜索失败 |
| INVALID_QUERY | 400 | 无效查询 |
| SCAN_FAILED | 500 | 扫描失败 |
| VECTORIZATION_FAILED | 500 | 向量化失败 |
| FORBIDDEN | 403 | 访问被拒绝 |
| RATE_LIMIT_EXCEEDED | 429 | 请求过于频繁 |

### 9.2 错误响应示例

```json
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "查询文本不能为空",
    "details": "query 字段不能为空"
  }
}
```

---

## 10. 使用示例

### 10.1 Python 调用

```python
import requests

# 配置
BASE_URL = "http://127.0.0.1:8000/api/v1"

# 搜索文档
response = requests.post(
    f"{BASE_URL}/search",
    json={
        "query": "商户画像",
        "top_k": 5,
        "search_type": "hybrid"
    }
)
result = response.json()

for item in result["results"]:
    print(f"{item['file_name']} (相似度: {item['similarity']:.2f})")
```

### 10.2 cURL 调用

```bash
# 健康检查
curl http://127.0.0.1:8000/api/v1/health

# 搜索文档
curl -X POST http://127.0.0.1:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "商户画像", "top_k": 5}'

# 扫描文件
curl -X POST http://127.0.0.1:8000/api/v1/scan \
  -H "Content-Type: application/json"

# 获取统计信息
curl http://127.0.0.1:8000/api/v1/stats
```

### 10.3 JavaScript/Node.js 调用

```javascript
const axios = require('axios');

const BASE_URL = 'http://127.0.0.1:8000/api/v1';

// 搜索文档
async function search(query) {
  const response = await axios.post(`${BASE_URL}/search`, {
    query: query,
    top_k: 5,
    search_type: 'hybrid'
  });

  return response.data;
}

// 使用示例
search('商户画像').then(result => {
  console.log(`找到 ${result.total} 个结果`);
  result.results.forEach(item => {
    console.log(`${item.file_name} (${item.similarity})`);
  });
});
```

---

## 11. AI 调用示例

### 11.1 OpenClaw 调用

```python
import requests

# 1. 先调用本地 API 检索相关文档
search_response = requests.post(
    "http://127.0.0.1:8000/api/v1/search",
    json={"query": "商户画像覆盖率计算方法", "top_k": 3}
)

results = search_response.json()["results"]

# 2. 将检索结果传递给 AI
context = "\n".join([
    f"文件: {r['file_name']}\n内容: {r['chunk_text']}\n"
    for r in results
])

prompt = f"""
根据以下文档内容回答问题：

文档内容：
{context}

问题：商户画像的覆盖率如何计算？
"""

# 3. 调用 AI 获取回答
ai_response = requests.post(
    "https://api.openclaw.com/v1/chat",
    json={"prompt": prompt}
)

print(ai_response.json()["answer"])
```

### 11.2 Claude 调用

```python
import anthropic

# 1. 检索相关文档
search_response = requests.post(
    "http://127.0.0.1:8000/api/v1/search",
    json={"query": "商户画像覆盖率计算方法", "top_k": 3}
)

results = search_response.json()["results"]

# 2. 构建上下文
context = "\n\n".join([
    f"【{r['file_name']}】\n{r['chunk_text']}"
    for r in results
])

# 3. 调用 Claude
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": f"根据以下文档回答问题：\n\n{context}\n\n问题：商户画像的覆盖率如何计算？"
        }
    ]
)

print(response.content[0].text)
```

---

## 12. 性能说明

### 12.1 响应时间

| 接口 | 预期响应时间 |
|------|------------|
| 健康检查 | < 10ms |
| 搜索 | < 500ms |
| 扫描 | 取决于文件数量 |
| 向量化 | 取决于文件数量 |
| 统计 | < 100ms |

### 12.2 速率限制

- 默认限制：100 请求/分钟
- 可在配置中调整

---

**文档结束**

*本文档由 Claude 在无人值守模式下自动生成*
*版本: v1.0 | 日期: 2026-03-01*
