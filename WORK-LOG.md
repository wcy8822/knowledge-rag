# 知识库 RAG — 工作日志

## 2026-04-03

### 文件重组
- local-rag-system, kb_vectorization, knowledge_base_vectorization 归集
- 8 个向量化散落脚本归集到 code/scripts/
- BGE-M3 模型 + vectors 数据 symlink

### git init
- local-rag-system (118文件), kb_vectorization (74文件)

### 本地 LLM 扫描器
- deepseek-r1:8b → qwen2.5:7b 切换（速度提升 40%）
- 自动 tag 注入集成到扫描循环
- 188 个 Obsidian 笔记自动注入 tags/ai_topic/ai_domain
- 截止 302 文件已处理

## 2026-04-02
- 项目域创建

### RAG 实操完成 ✅
- ChromaDB collection: doc_knowledge_summaries, 495 条记录
- Embedding: all-MiniLM-L6-v2（内置，英文模型）
- 查询脚本: ~/.allin_ai_safe/scripts/rag-query.py
- 测试结果：overlap 搜索命中准确(0.69)，中文语义偏弱
- **待优化**：替换为 BGE-M3 中文 embedding 提升效果
- 数据路径: ~/Work/data/vectors/data/chroma-doc-knowledge/

### RAG 中文 embedding 升级 ✅
- BGE-M3 (1024维) 替代 all-MiniLM-L6-v2 (384维)
- ChromaDB 573 条记录重新 embedding
- 中文搜索质量大幅提升：
  - "商户画像宽表" 0.39→0.70 (+79%)
  - "油价预测模型" 0.37→0.69 (+86%)
  - "overlap 清洗" 0.53→0.62 (+17%)
- rag-query.py 更新为 BGE-M3 版本
- 存储: ~/Work/data/vectors/data/chroma-doc-knowledge-bge/

### 完整 RAG 自动管线 + LLM 问答 ✅
- **四步自动管线闭环**：
  1. qwen2.5:7b 扫描文档 → 生成摘要
  2. 摘要注入 Obsidian frontmatter (tags/topic/domain)
  3. 摘要导入 ChromaDB (BGE-M3 embedding)
  4. 每轮扫描自动触发 2+3
- **ask.py 问答工具**：问题→BGE-M3搜索→top5文档→qwen2.5总结→结构化回答
- 测试结果：
  - "overlap 处理逻辑" → 准确回答清洗流程+来源引用
  - "六边形宽表维度" → 识别到相关文档但知识不足时诚实说明
  - "油价预测算法" → 准确回答多项回归模型
- alias: `ask "问题"` / `rag "搜索"`
- 扫描器已处理 678 文件，持续增长

### RAG MCP Server ✅
- MCP server 代码：rag-mcp-server/server.py
- 三个 tool：search_knowledge / ask_knowledge / knowledge_stats
- 配置到 ~/.mcp.json，Claude Code 重启后自动加载
- 其他 AI 工具（OpenClaw/小龙虾）可通过 MCP 协议连接
- **核心理念**：RAG 不是给人手动用的，是给所有 AI 当知识后端

### 统一智能数据层 MCP Server v2 ✅
- 从 3 个 tool 扩展到 **8 个 tool**（+1 内部）
- 新增能力：
  - **query_mysql**: 自然语言→SQL查询（只读，安全限制）
  - **list_mysql_tables**: 数据库结构浏览
  - **read_notes**: Obsidian 笔记搜索和读取
  - **read_worklog**: 项目工作日志读取
  - **add_worklog**: 工作日志写入
- 设计文档: DESIGN-LOCAL-AI-DATA-LAYER.md
- **核心范式**: 所有本地数据通过一个 MCP Server 暴露给任何大模型

### NL2SQL 集成到 MCP Server ✅
- 305 表 7762 字段全量 schema 提取 → mysql-schema.json (1.3MB)
- 22 张核心业务表精选 → nl2sql-context.md (53KB)
- 加入业务知识（brand_level/is_overlap/poi 映射等）
- 加入 SQL 查询模式示例（KA/重叠站/拜访/利润）
- 测试结果：
  - "KA站点有多少" → KA:5030 CKA:3736 ✅ 完美命中
  - "最近一周拜访" → 语法正确 ✅
  - "省区重叠站" → 字段名错误（需继续优化 context）
- MCP server 现在 9 个 tool（新增 nl2sql）

### OpenClaw MCP 对接
- OpenClaw 通过 mcporter skill 支持 MCP（已安装 mcporter）
- 配置文件已创建: ~/.openclaw/mcporter.json + openclaw.json
- MCP server stdio 协议验证通过（9 tool 全部正确返回）
- mcporter 连接超时问题待调优（可能需要 HTTP transport 层）
- Claude Code 的 ~/.mcp.json 已配置完成

---

## 2026-04-04 ~ 2026-04-05

### 橙化率模型共识 ✅

**定义锚定（不可更改的基础公式）：**
- 橙化率 = DD纯汽油消费量 / 全国汽油消费量，**只看汽油，不含加气**
- 加气站通过 `gas_flag=1` 识别剔除（241个站，日均2.8万单）
- 分子公式：`(日均总订单 - 3万加气) × 30天 × 30升/单 / 1360升/吨 / 10000`
- 每单均量：**30升**（用户确认）；汽油密度：**1360升/吨**

**订单基点（共识数字）：**
| 年份 | 日均总单 | 纯汽油单 | DD月消费 |
|------|---------|---------|---------|
| 2024 | 50万 | 47万 | 31.1万吨 |
| 2025 | 43万 | 40万 | 26.5万吨（实测36万单→23.9万吨） |
| 2026 | 35万 | 32万 | 21.2万吨 |

**分母：全国汽油消费递减（共识）：**
- 2024基准：1350万吨/月
- 年降 **7.5%**（NEV渗透，非10%，用户采纳建议）
- 2025：1249万吨 | 2026：1155万吨

**全国橙化率基点：**
- 2024：2.30% | 2025：1.91%（模型实算） | 2026：1.83%
- 用户记忆中的5%是**高渗透省份/城市口径**（天津/北京/广东等），非全国

### L4 引力模型 v3 共识版本 ✅
文件：`/Users/didi/Work/projects/fgw-油价预测/code/macro-data-pipeline/l4_gravity_model_v3.py`

**核心改造（本次会话完成）：**
1. 分子从硬编码29万吨 → **公式驱动**，从 order_cnt_30d 自动推算
2. gas_flag=0 过滤，剔除241个加气站
3. 订单量信号加入吸引力模型（log boost），高单量站分到更多分母
4. 软压缩：分段策略，站点橙化率自然收敛，无硬截断痕迹
5. 城市DD守恒：压缩后反算确保每城市DD总量不变
6. 高区间正态化：>15%的站做正态重分布（center=18%, std=4%）
7. 分母支持年份参数：`python3 l4_gravity_model_v3.py 2025`

**共识结果（year=2025）：**
- 全国橙化率：1.91%
- 站点中位数：6.73%，最大：31.8%，P95：21.3%
- DD总量守恒验证：23.9万吨 ✅
- 17,482纯汽油站，15,849有订单站

**待做（土豆）：**
- 区县层级（国→省→市→区县→站五级聚合）
- 时序维度（2024/2025/2026三年对比）
- 曲线集（需结合高德地图，站地址→区县映射）

### Loki 本地知识向量化体系 ✅
**命名共识：** 本地知识向量化系统统一称为 **Loki**（Local Knowledge Index）

**架构：**
- 流水线：`code/scripts/loki_pipeline.py`
- 守护脚本：`code/scripts/loki_watchdog.sh`
- 系统服务：`~/Library/LaunchAgents/com.didi.loki.plist`（launchd，开机自启，崩溃自动重启）
- 日志目录：`code/scripts/logs/`
- 状态文件：`code/scripts/logs/loki_state.json`（断点续跑依据）

**覆盖范围：**
| 数据源 | 数量 | 集合名 |
|--------|------|--------|
| Obsidian MD笔记 | 3,277个 | doc_knowledge_bge_m3 |
| PDF文档 | 243个 | doc_knowledge_bge_m3 |
| Office文档(docx/xlsx/pptx) | 387个 | doc_knowledge_bge_m3 |
| MySQL DDL（所有表结构+字段注释） | 全量 | ddl_schema_bge_m3 |

**技术参数：**
- Embedding：BGE-M3（1024维，本地MPS加速，无网络请求）
- ChromaDB路径：`/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge`
- 每轮完成后间隔1小时增量扫描
- 每批8个文件，单文件失败不中断全局

**启动状态（2026-04-05 00:40）：**
- launchd 服务已注册运行，PID 69338（watchdog）+ 69731（pipeline）
- 进行中：4251个文件待处理，已完成200+条
- 预计：睡一觉后全部完成

## 2026-04-10
- Loki Phase 2 chunk 推进到 71.9%（1717/2387），大文件归档+跳过qwen后速度提升10x
- loki_search.py 改造为人类可读输出，建立 `loki` shell alias
- knowledge-rag MCP 升级为三集合 merge ranking（summaries+chunks+ddl）
- mysql-mcp-server 独立部署：6工具+config.yaml+审计日志，注册到 ~/.mcp.json
- 商户画像核心表层级修正：经营表+拜访表是管道一源头，字段反查法沉淀为方法论
- 3张核心表DDL补入向量库
- 系统诊断：vpnagentd(88%CPU) killed，Swap 22GB 分析，kernel_task 热保护识别

## 2026-04-11
- Phase 2 chunk 全部完成（649/649，38035 chunks，555分钟，零失败）
- 跑 Benchmark 发现当前评测方式有缺陷（测文件召回≠测问题回答）
- 诊断"橙化率"搜索 miss 根因：BGE-M3 对私有术语无向量表示，权重调整无效
- 设计 Phase 3 Hybrid Search（BM25+向量+RRF）作为长期解法
- MCP server 权重临时调整为 summaries 0.5 / chunks 0.3
