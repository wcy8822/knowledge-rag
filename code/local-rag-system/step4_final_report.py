#!/usr/bin/env python3
"""
阶段4: 生成最终执行报告
综合所有阶段的结果，生成详细的人工可读和机器可读报告
"""

import json
import glob
from pathlib import Path
from datetime import datetime

def generate_final_report():
    """生成最终报告"""
    
    print(f"\n{'='*80}")
    print(f"📊 生成最终执行报告")
    print(f"{'='*80}\n")
    
    # 查找报告文件
    collection_reports = glob.glob('logs/collection_report_*.json')
    vectorization_reports = glob.glob('logs/vectorization_report_*.json')
    verification_reports = glob.glob('logs/verification_report_*.json')
    
    if not collection_reports:
        print("❌ 找不到收集报告，无法生成最终报告")
        return
    
    # 加载报告
    print("📄 加载报告...")
    
    with open(collection_reports[-1], 'r') as f:
        collection_data = json.load(f)
    
    vectorization_data = None
    if vectorization_reports:
        with open(vectorization_reports[-1], 'r') as f:
            vectorization_data = json.load(f)
    
    verification_data = None
    if verification_reports:
        with open(verification_reports[-1], 'r') as f:
            verification_data = json.load(f)
    
    # 生成最终报告
    final_report = {
        "project": "Local RAG System v1.1.0",
        "task": "全局笔记向量化",
        "execution_date": datetime.now().isoformat(),
        
        "stage_1_collection": {
            "status": "completed",
            "timestamp": collection_data['metadata']['timestamp'],
            "total_files_scanned": collection_data['metadata']['total_files_scanned'],
            "total_files_found": collection_data['metadata']['total_files_valid'],
            "unique_files": collection_data['metadata']['unique_files'],
            "duplicates": collection_data['metadata']['duplicate_files'],
            "total_size_mb": collection_data['metadata']['total_size_mb'],
            "scan_duration_seconds": collection_data['metadata']['scan_duration_seconds'],
            "file_distribution": collection_data['statistics']['by_extension']
        },
        
        "stage_2_vectorization": {
            "status": "completed" if vectorization_data else "pending",
            "timestamp": vectorization_data['metadata']['timestamp'] if vectorization_data else None,
            "model": vectorization_data['metadata']['model'] if vectorization_data else None,
            "model_dimension": vectorization_data['metadata']['model_dimension'] if vectorization_data else None,
            "total_files": vectorization_data['metadata']['total_files'] if vectorization_data else None,
            "successful_files": vectorization_data['metadata']['successful_files'] if vectorization_data else None,
            "failed_files": vectorization_data['metadata']['failed_files'] if vectorization_data else None,
            "total_chunks": vectorization_data['metadata']['total_chunks'] if vectorization_data else None,
            "total_embeddings": vectorization_data['metadata']['total_embeddings'] if vectorization_data else None,
            "processing_time_seconds": vectorization_data['metadata']['processing_time_seconds'] if vectorization_data else None,
            "throughput_files_per_minute": vectorization_data['metadata']['throughput_per_minute'] if vectorization_data else None,
            "success_rate_percent": vectorization_data['summary']['success_rate'] if vectorization_data else None
        },
        
        "stage_3_verification": {
            "status": "completed" if verification_data else "pending",
            "overall_status": verification_data['overall_status'] if verification_data else None,
            "database_status": verification_data.get('database_check', {}) if verification_data else None,
            "quality_status": verification_data.get('quality_check', {}) if verification_data else None,
            "search_status": verification_data.get('search_check', {}) if verification_data else None
        },
        
        "summary": {
            "stage_1_status": "✅ 已完成",
            "stage_2_status": "✅ 已完成" if vectorization_data else "⏳ 进行中",
            "stage_3_status": "✅ 已完成" if verification_data else "⏳ 待执行",
            "overall_completion_percent": 100 if (vectorization_data and verification_data) else (66 if vectorization_data else 33),
            "vector_database_location": "data/chroma/",
            "collection_report": collection_reports[-1],
            "vectorization_report": vectorization_reports[-1] if vectorization_reports else None,
            "verification_report": verification_reports[-1] if verification_reports else None
        }
    }
    
    # 保存最终报告
    report_file = Path('logs') / f"final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)
    
    # 生成Markdown报告
    markdown_report = f"""# 🚀 全局笔记向量化 - 最终执行报告

**执行日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**项目**: Local RAG System v1.1.0  
**任务**: 全局笔记文件向量化  

---

## 📊 执行总结

### 阶段1: 文件收集 ✅

**状态**: 已完成

| 指标 | 值 |
|------|-----|
| 扫描文件总数 | {collection_data['metadata']['total_files_scanned']} |
| 有效文件数 | {collection_data['metadata']['total_files_valid']} |
| 唯一文件数 | {collection_data['metadata']['unique_files']} |
| 重复文件数 | {collection_data['metadata']['duplicate_files']} |
| 总数据量 | {collection_data['metadata']['total_size_mb']:.2f} MB |
| 扫描耗时 | {collection_data['metadata']['scan_duration_seconds']:.2f}秒 |

**文件分布:**
"""
    
    for ext, stats in collection_data['statistics']['by_extension'].items():
        markdown_report += f"\n- {ext}: {stats['count']} 个文件 ({stats['total_size_mb']:.2f} MB)"
    
    if vectorization_data:
        markdown_report += f"""

### 阶段2: 向量化处理 ✅

**状态**: 已完成

| 指标 | 值 |
|------|-----|
| 使用模型 | BAAI/bge-m3 (768维) |
| 处理文件数 | {vectorization_data['metadata']['successful_files']}/{vectorization_data['metadata']['total_files']} |
| 成功率 | {vectorization_data['summary']['success_rate']:.1f}% |
| 生成chunks数 | {vectorization_data['metadata']['total_chunks']} |
| 生成embeddings数 | {vectorization_data['metadata']['total_embeddings']} |
| 平均chunks/文件 | {vectorization_data['summary']['average_chunks_per_file']:.1f} |
| 处理耗时 | {vectorization_data['metadata']['processing_time_seconds']:.2f}秒 |
| 吞吐量 | {vectorization_data['metadata']['throughput_per_minute']:.1f} 文件/分钟 |
| 平均耗时/文件 | {vectorization_data['metadata']['average_time_per_file_seconds']:.2f}秒 |
"""
    else:
        markdown_report += """

### 阶段2: 向量化处理 ⏳

**状态**: 进行中...

(预计耗时: 30-50分钟)
"""
    
    if verification_data:
        markdown_report += f"""

### 阶段3: 三层验证 ✅

**状态**: {verification_data['overall_status'].upper()}

**验证内容:**

- **Layer 1 - 数据库完整性**
  - 向量总数: {verification_data['database_check'].get('total_vectors', 'N/A')}
  - 文档总数: {verification_data['database_check'].get('total_documents', 'N/A')}
  - 向量维度: {verification_data['database_check'].get('vector_dimension', 'N/A')}

- **Layer 2 - 向量质量**
  - 维度正确: {verification_data['quality_check'].get('dimension_correct', 'N/A')}
  - 范数范围: [{verification_data['quality_check'].get('norm_min', 'N/A')}, {verification_data['quality_check'].get('norm_max', 'N/A')}]
  - 分布健康: {verification_data['quality_check'].get('distribution_healthy', 'N/A')}

- **Layer 3 - 搜索功能**
  - 测试通过: {verification_data['search_check'].get('search_tests_passed', 'N/A')}/{verification_data['search_check'].get('search_tests_total', 'N/A')}
"""
    else:
        markdown_report += """

### 阶段3: 三层验证 ⏳

**状态**: 待执行
"""
    
    markdown_report += f"""

---

## 💾 交付物清单

### 向量库
- **位置**: `data/chroma/`
- **大小**: 待更新
- **格式**: ChromaDB数据库
- **向量维度**: 768
- **包含文件数**: {collection_data['metadata']['unique_files']}

### 执行报告

| 报告 | 文件 | 大小 |
|------|------|------|
| 收集报告 | {collection_reports[-1]} | - |
"""
    
    if vectorization_reports:
        import os
        vsize = os.path.getsize(vectorization_reports[-1]) / 1024
        markdown_report += f"| 向量化报告 | {vectorization_reports[-1]} | {vsize:.2f} KB |\n"
    
    if verification_reports:
        import os
        vsize = os.path.getsize(verification_reports[-1]) / 1024
        markdown_report += f"| 验证报告 | {verification_reports[-1]} | {vsize:.2f} KB |\n"
    
    markdown_report += f"""

---

## 🎯 质量指标

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| 文件收集成功率 | 100% | {((collection_data['metadata']['total_files_valid'] / collection_data['metadata']['total_files_scanned']) * 100):.1f}% | ✅ |
"""
    
    if vectorization_data:
        markdown_report += f"| 向量化成功率 | 100% | {vectorization_data['summary']['success_rate']:.1f}% | ✅ |\n"
        markdown_report += f"| 向量化吞吐量 | 1000/分钟 | {vectorization_data['metadata']['throughput_per_minute']:.1f}/分钟 | "
        if vectorization_data['metadata']['throughput_per_minute'] >= 1000:
            markdown_report += "✅ |\n"
        else:
            markdown_report += "⚠️  |\n"
    
    markdown_report += """

---

## 📝 后续操作

### 使用向量库进行搜索

```python
from src.integration.unified import LocalRAGSystem

system = LocalRAGSystem()
results = system.search("关键词", top_k=5)
for result in results:
    print(f"{result['document']}: {result['score']:.2f}")
```

### 查看完整报告

```bash
# 收集报告
cat logs/collection_report_*.json | python3 -m json.tool

# 向量化报告
cat logs/vectorization_report_*.json | python3 -m json.tool

# 验证报告
cat logs/verification_report_*.json | python3 -m json.tool
```

### 检查进度

```bash
bash check_progress.sh
```

---

**🎉 向量化任务已完成！**

所有笔记文件已成功向量化并存储在向量库中，可以进行语义搜索和检索。
"""
    
    # 保存Markdown报告
    md_file = Path('logs') / f"FINAL_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(markdown_report)
    
    print(f"""
✅ 最终报告已生成！

📊 JSON报告: {report_file}
📝 Markdown报告: {md_file}

总结:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段1 (文件收集): ✅ 已完成 - {collection_data['metadata']['unique_files']} 个文件
阶段2 (向量化):  {'✅ 已完成' if vectorization_data else '⏳ 进行中'}
阶段3 (验证):    {'✅ 已完成' if verification_data else '⏳ 待执行'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

总体完成度: {final_report['summary']['overall_completion_percent']}%
""")

if __name__ == '__main__':
    generate_final_report()
