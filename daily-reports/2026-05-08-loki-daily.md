---
type: 日报
date: 2026-05-08
week: 19
project: Loki知识库RAG
tags:
  - Loki日报
  - daily_pipeline
  - week19
  - 首日
  - 耗时169分钟
  - BM25_55391条
  - 健康
related:
  - "[[2026-05-07-loki-daily]]"
---

## 全景总结

2026-05-08 02:00 launchd 自动跑 daily pipeline 用时 169.0 分钟，wrapper exit=0，整体状态 🟢 健康。文档库 11082 (N/A)，chunk 库 43775 (N/A)，DDL 库 534 (N/A)，BM25 索引 55391 条 rebuild (163.3s，cache 命中 0%)。RSS 峰值 8270MB / 18432MB 上限。本日处理 docs 成功 57/失败 0/content跳过 1443，chunks 文件 1500/失败 0/新增 chunk 71693，DDL 成功 14/失败 0。

## 核心索引标签

#Loki日报 #daily_pipeline #week19 #首日 #耗时169分钟 #BM25_55391条 #健康

---

## 一、健康总览

**整体状态**：🟢 健康

- ✅ wrapper exit=0
- ✅ RSS 峰值 8270MB / 18432MB (44%)
- ✅ 失败 0
- ⚠️ 耗时 169.0 分钟 (超 60 分钟)
- ⚠️ BM25 cache 命中 0% (低于 50%)

## 二、运行结果对比

| 指标 | 当日 | 前日 | 增量 |
|---|---|---|---|
| docs_total | 11082 | N/A | N/A |
| chunks_total | 43775 | N/A | N/A |
| ddl_total | 534 | N/A | N/A |
| bm25_count | 55391 | N/A | N/A |
| duration_min | 169.0 | N/A | - |

## 三、阶段细节

### Part 1 文档向量化
- 库总量: **11082**
- 本次成功: 57
- 失败: 0
- content 重复跳过: 1443

### Part 2 长文档分块
- 库总量: **43775**
- 本次处理文件: 1500
- 失败: 0
- 新增 chunk: 71693

### Part 3 DDL
- 库总量: **534**
- 本次成功: 14
- 失败: 0

### BM25 索引 rebuild
- 总条数: **55391**
- 耗时: 163.3s
- cache 命中: 0%

## 四、错误聚合

无报错 ✅

## 五、警告

- --max-files=1500 触发：本次只处理前 1500 个，剩余 9953 个待下次跑
- --max-files=1500 触发 (chunks)：本次只处理前 1500 个，剩余 8186 个待下次跑

## 六、原始日志

- wrapper: `code/scripts/logs/wrapper_20260508_020005.log`
- loki: `code/scripts/logs/loki_20260508_020016.log`

---

*本报告由 `code/scripts/loki_daily_report.py` 自动生成*

<!-- stats: docs_total=11082 chunks_total=43775 ddl_total=534 bm25_count=55391 duration_min=169.0 wrapper_exit=0 -->
