---
type: 日报
date: 2026-05-09
week: 19
project: Loki知识库RAG
tags:
  - Loki日报
  - daily_pipeline
  - week19
  - chunk增量+17579
  - 耗时48分钟
  - BM25_72991条
  - 注意
  - 有失败
related:
  - "[[2026-05-08-loki-daily]]"
---

## 全景总结

2026-05-09 02:00 launchd 自动跑 daily pipeline 用时 48.4 分钟，wrapper exit=0，整体状态 🟡 注意。文档库 11101 (+19)，chunk 库 61354 (+17579)，DDL 库 536 (+2)，BM25 索引 72991 条 rebuild (75.4s，cache 命中 75%)。RSS 峰值 5578MB / 18432MB 上限。本日处理 docs 成功 32/失败 0/content跳过 1468，chunks 文件 1337/失败 161/新增 chunk 17712，DDL 成功 2/失败 0。主要异常：解析失败(.pdf): No module named 'pdfminer' ×161。

## 核心索引标签

#Loki日报 #daily_pipeline #week19 #chunk增量+17579 #耗时48分钟 #BM25_72991条 #注意

---

## 一、健康总览

**整体状态**：🟡 注意

- ✅ wrapper exit=0
- ✅ RSS 峰值 5578MB / 18432MB (30%)
- ⚠️ 失败 161 个 (docs=0 chunks=161 ddl=0)
- ✅ 耗时 48.4 分钟
- ✅ BM25 cache 命中 75%

## 二、运行结果对比

| 指标 | 当日 | 前日 | 增量 |
|---|---|---|---|
| docs_total | 11101 | 11082 | +19 |
| chunks_total | 61354 | 43775 | +17579 |
| ddl_total | 536 | 534 | +2 |
| bm25_count | 72991 | 55391 | +17600 |
| duration_min | 48.4 | 169.0 | - |

## 三、阶段细节

### Part 1 文档向量化
- 库总量: **11101**
- 本次成功: 32
- 失败: 0
- content 重复跳过: 1468

### Part 2 长文档分块
- 库总量: **61354**
- 本次处理文件: 1337
- 失败: 161
- 新增 chunk: 17712

### Part 3 DDL
- 库总量: **536**
- 本次成功: 2
- 失败: 0

### BM25 索引 rebuild
- 总条数: **72991**
- 耗时: 75.4s
- cache 命中: 75%

## 四、错误聚合（按类型）

### 解析失败(.pdf): No module named 'pdfminer' (×161)
- finebi6.0.pdf
- 盈阳-0405.pdf
- 供应链业务Q3小结内容.pdf
- 能链贷产品 (2).pdf
- 集装箱运力-0308.pdf

## 五、警告

- --max-files=1500 触发：本次只处理前 1500 个，剩余 10001 个待下次跑
- --max-files=1500 触发 (chunks)：本次只处理前 1500 个，剩余 5868 个待下次跑

## 六、原始日志

- wrapper: `code/scripts/logs/wrapper_20260509_020002.log`
- loki: `code/scripts/logs/loki_20260509_020012.log`

---

*本报告由 `code/scripts/loki_daily_report.py` 自动生成*

<!-- stats: docs_total=11101 chunks_total=61354 ddl_total=536 bm25_count=72991 duration_min=48.4 wrapper_exit=0 -->
