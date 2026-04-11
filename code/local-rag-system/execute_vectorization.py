#!/usr/bin/env python3
"""
全局笔记向量化执行脚本
完整的端到端向量化流程: 收集 → 向量化 → 验证 → 报告
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# 添加src路径
sys.path.insert(0, str(Path(__file__).parent))

from src.vectorization.collect_notes import NotesCollector
from src.vectorization.vectorize_global_notes import GlobalNotesVectorizer
from src.vectorization.verify_vectorization import VectorizationVerifier
from src.integration.unified import LocalRAGSystem

def print_header(text):
    """打印部分标题"""
    print(f"\n{'='*80}")
    print(f"🚀 {text}")
    print(f"{'='*80}\n")

def print_step(num, text):
    """打印步骤"""
    print(f"\n{'─'*80}")
    print(f"📍 第{num}步: {text}")
    print(f"{'─'*80}\n")

def main():
    """主执行函数"""
    
    start_time = datetime.now()
    print_header("全局笔记向量化执行 v1.1.0")
    
    # 配置
    notes_dir = "/Users/didi/Downloads/panth"
    work_dir = Path(__file__).parent
    
    print(f"📁 笔记目录: {notes_dir}")
    print(f"📁 工作目录: {work_dir}")
    print(f"⏰ 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # ============ 第1步: 文件收集 ============
        print_step(1, "文件收集")
        collector = NotesCollector(
            base_dir=notes_dir,
            supported_formats=['.md', '.txt'],
            output_dir=str(work_dir / 'logs')
        )
        
        print("📂 开始扫描文件...")
        collection_report = collector.collect_all_notes()
        print(f"✅ 收集完成!")
        print(f"   - 总文件数: {collection_report['metadata']['total_files']}")
        print(f"   - 总大小: {collection_report['metadata']['total_size_mb']:.2f} MB")
        print(f"   - 唯一文件: {len(collection_report['files'])}")
        print(f"   - 耗时: {collection_report['metadata']['scan_duration_seconds']:.2f}秒")
        
        # ============ 第2步: 向量化处理 ============
        print_step(2, "向量化处理 (使用BGE-M3)")
        
        # 确保有收集报告
        if not collection_report or 'files' not in collection_report:
            print("❌ 收集失败，无法继续")
            return False
        
        vectorizer = GlobalNotesVectorizer(
            model_name='BAAI/bge-m3',
            output_dir=str(work_dir / 'logs'),
            batch_size=32,
            chunk_size=750,
            chunk_overlap_ratio=0.15
        )
        
        print(f"🤖 使用模型: BAAI/bge-m3 (768维)")
        print(f"⚙️  批处理大小: 32")
        print(f"📄 文档分块: 750 tokens + 15% 重叠")
        print("\n⏳ 正在处理...这可能需要较长时间...\n")
        
        vectorization_report = vectorizer.vectorize_all(collection_report)
        
        print(f"✅ 向量化完成!")
        print(f"   - 处理文件: {vectorization_report['metadata']['successful_files']}")
        print(f"   - 失败文件: {vectorization_report['metadata']['failed_files']}")
        print(f"   - 总chunks: {vectorization_report['metadata']['total_chunks']}")
        print(f"   - 总embeddings: {vectorization_report['metadata']['total_embeddings']}")
        print(f"   - 耗时: {vectorization_report['metadata']['processing_time_seconds']:.2f}秒")
        print(f"   - 吞吐量: {vectorization_report['metadata']['throughput_per_minute']:.1f} 文件/分钟")
        
        # ============ 第3步: 三层验证 ============
        print_step(3, "三层验证")
        
        verifier = VectorizationVerifier(
            vector_store_path=str(work_dir / 'data' / 'chroma'),
            output_dir=str(work_dir / 'logs')
        )
        
        print("🔍 Layer 1: 向量数据库完整性检查...")
        layer1 = verifier.check_vector_database()
        print(f"   ✅ 向量总数: {layer1['total_vectors']}")
        print(f"   ✅ 文档总数: {layer1['total_documents']}")
        print(f"   ✅ 向量维度: {layer1['vector_dimension']}")
        
        print("\n🔍 Layer 2: 向量质量验证...")
        layer2 = verifier.check_vector_quality()
        print(f"   ✅ 维度正确: {layer2['dimension_correct']}")
        print(f"   ✅ 范数范围: [{layer2['norm_min']:.2f}, {layer2['norm_max']:.2f}]")
        print(f"   ✅ 分布健康: {layer2['distribution_healthy']}")
        
        print("\n🔍 Layer 3: 搜索功能测试...")
        layer3 = verifier.test_search_functionality()
        print(f"   ✅ 测试通过: {layer3['search_tests_passed']}/{layer3['search_tests_total']}")
        
        verification_report = verifier.verify_all()
        print(f"\n✅ 验证完成! 状态: {verification_report['overall_status'].upper()}")
        
        # ============ 第4步: 生成最终报告 ============
        print_step(4, "生成执行报告")
        
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        
        summary = {
            "project": "Local RAG System v1.1.0",
            "execution_date": end_time.isoformat(),
            "total_duration_seconds": total_duration,
            "stage_results": {
                "collection": collection_report['metadata'],
                "vectorization": vectorization_report['metadata'],
                "verification": {
                    "overall_status": verification_report['overall_status'],
                    "database_check": layer1,
                    "quality_check": layer2,
                    "search_check": layer3
                }
            }
        }
        
        # 保存总结
        summary_file = work_dir / 'logs' / f"execution_summary_{end_time.strftime('%Y%m%d_%H%M%S')}.json"
        import json
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"📊 执行总结已保存: {summary_file}")
        
        # ============ 第5步: 显示最终统计 ============
        print_step(5, "最终统计")
        
        print(f"""
╔════════════════════════════════════════════════════════════╗
║                   ✅ 向量化流程完成                         ║
╠════════════════════════════════════════════════════════════╣
║  📊 收集阶段:                                              ║
║     • 扫描文件: {collection_report['metadata']['total_files']} 个                              ║
║     • 总数据量: {collection_report['metadata']['total_size_mb']:.2f} MB                              ║
║     • 唯一文件: {len(collection_report['files'])} 个                              ║
║                                                            ║
║  🤖 向量化阶段:                                            ║
║     • 处理文件: {vectorization_report['metadata']['successful_files']} 个                              ║
║     • 生成chunks: {vectorization_report['metadata']['total_chunks']} 个                              ║
║     • 生成embeddings: {vectorization_report['metadata']['total_embeddings']} 个                              ║
║     • 吞吐量: {vectorization_report['metadata']['throughput_per_minute']:.1f} 文件/分钟                      ║
║                                                            ║
║  ✅ 验证阶段:                                              ║
║     • 整体状态: {verification_report['overall_status'].upper()}                              ║
║     • 向量总数: {layer1['total_vectors']} 个                              ║
║     • 搜索测试: {layer3['search_tests_passed']}/{layer3['search_tests_total']} 通过                          ║
║                                                            ║
║  ⏱️  总耗时: {total_duration:.1f} 秒                                 ║
╚════════════════════════════════════════════════════════════╝
""")
        
        # ============ 第6步: 生成可用信息 ============
        print_step(6, "可用资源")
        
        print(f"""
📁 向量库位置:
   {work_dir / 'data' / 'chroma'}

📄 执行日志:
   • 收集报告: {work_dir / 'logs' / 'collection_report_*.json'}
   • 向量化报告: {work_dir / 'logs' / 'vectorization_report_*.json'}
   • 验证报告: {work_dir / 'logs' / 'verification_report_*.json'}
   • 执行总结: {work_dir / 'logs' / 'execution_summary_*.json'}

🔍 下一步操作:
   1. 使用LocalRAGSystem进行搜索:
      from src.integration.unified import LocalRAGSystem
      system = LocalRAGSystem()
      results = system.search("查询关键词", top_k=5)
   
   2. 查看详细报告:
      cat logs/execution_summary_*.json
      
   3. 验证向量库:
      python3 -c "import chromadb; client = chromadb.PersistentClient('data/chroma'); print(client.list_collections())"
""")
        
        print("\n🎉 向量化任务完全完成!\n")
        return True
        
    except Exception as e:
        print(f"\n❌ 执行出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
