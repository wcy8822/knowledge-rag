#!/usr/bin/env python3
"""
阶段2: 向量化处理
使用BGE-M3模型对收集的笔记文件进行向量化处理
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import sys

# 导入必要的库
try:
    from sentence_transformers import SentenceTransformer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️  sentence-transformers未安装，将尝试安装...")

def load_collection_report(report_file: str) -> Dict[str, Any]:
    """加载收集报告"""
    with open(report_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def chunk_document(text: str, chunk_size: int = 750, overlap_ratio: float = 0.15) -> List[str]:
    """
    将文档文本分块
    
    Args:
        text: 文档文本
        chunk_size: 每块中的单词数（近似）
        overlap_ratio: 块之间的重叠比例
    
    Returns:
        文本块列表
    """
    words = text.split()
    overlap_words = int(chunk_size * overlap_ratio)
    step_size = chunk_size - overlap_words
    
    chunks = []
    for i in range(0, len(words), step_size):
        chunk = ' '.join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    
    return chunks

def vectorize_notes(report_file: str, output_dir: str = 'logs') -> Dict[str, Any]:
    """向量化所有笔记文件"""
    
    print(f"\n{'='*80}")
    print(f"🚀 阶段2: 向量化处理 (BGE-M3)")
    print(f"{'='*80}\n")
    
    # 检查sentence-transformers
    if not TRANSFORMERS_AVAILABLE:
        print("❌ sentence-transformers不可用，无法继续向量化")
        print("请运行: pip install sentence-transformers")
        return {
            "status": "error",
            "message": "sentence-transformers not available"
        }
    
    start_time = time.time()
    
    # 加载收集报告
    print(f"📄 加载收集报告: {report_file}")
    collection_report = load_collection_report(report_file)
    files = collection_report['files']
    
    print(f"📊 准备处理 {len(files)} 个文件")
    print(f"   总大小: {collection_report['metadata']['total_size_mb']:.2f} MB\n")
    
    # 初始化模型
    print(f"🤖 加载BGE-M3模型...")
    print(f"   模型: BAAI/bge-m3")
    print(f"   维度: 768")
    
    try:
        model = SentenceTransformer('BAAI/bge-m3')
        print(f"   ✅ 模型加载完成\n")
    except Exception as e:
        print(f"   ❌ 模型加载失败: {e}")
        return {
            "status": "error",
            "message": f"Failed to load model: {e}"
        }
    
    # 处理文件
    vectorization_results = []
    successful_files = 0
    failed_files = 0
    total_chunks = 0
    total_embeddings = 0
    errors = []
    
    print(f"⏳ 开始处理文件...\n")
    
    for idx, file_info in enumerate(files, 1):
        file_path = file_info['path']
        
        try:
            # 读取文件
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            
            if not text.strip():
                raise Exception("文件为空")
            
            # 分块
            chunks = chunk_document(text, chunk_size=750, overlap_ratio=0.15)
            
            if not chunks:
                raise Exception("无法生成chunks")
            
            # 生成向量（不实际存储，只计算）
            embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
            
            # 记录结果
            result = {
                'file': file_path,
                'file_name': file_info['name'],
                'file_size': file_info['size'],
                'chunks': len(chunks),
                'embeddings': len(embeddings),
                'status': 'success'
            }
            vectorization_results.append(result)
            
            successful_files += 1
            total_chunks += len(chunks)
            total_embeddings += len(embeddings)
            
            # 每50个文件显示一次进度
            if idx % 50 == 0:
                print(f"   ✅ 已处理 {idx}/{len(files)} 个文件 "
                      f"({idx*100//len(files)}%) "
                      f"- {total_chunks} chunks, {total_embeddings} embeddings")
        
        except Exception as e:
            failed_files += 1
            error_info = {
                'file': file_path,
                'error': str(e)
            }
            errors.append(error_info)
            print(f"   ❌ 文件处理失败: {file_info['name'][:50]} - {e}")
    
    vectorization_time = time.time() - start_time
    
    # 生成报告
    report = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "model": "BAAI/bge-m3",
            "model_dimension": 768,
            "total_files": len(files),
            "successful_files": successful_files,
            "failed_files": failed_files,
            "total_chunks": total_chunks,
            "total_embeddings": total_embeddings,
            "processing_time_seconds": round(vectorization_time, 2),
            "average_time_per_file_seconds": round(vectorization_time / len(files), 2) if files else 0,
            "throughput_per_minute": round(len(files) / (vectorization_time / 60), 1) if vectorization_time > 0 else 0
        },
        "results": vectorization_results[:100],  # 只保存前100个的详细结果以节省空间
        "errors": errors,
        "summary": {
            "total_chunks": total_chunks,
            "average_chunks_per_file": round(total_chunks / successful_files, 1) if successful_files > 0 else 0,
            "total_embeddings": total_embeddings,
            "success_rate": round(successful_files * 100 / len(files), 1) if files else 0
        }
    }
    
    # 保存报告
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    report_file = output_path / f"vectorization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 向量化完成!\n")
    print(f"""
╔════════════════════════════════════════════════════════════╗
║                   🤖 向量化处理结果                         ║
╠════════════════════════════════════════════════════════════╣
║  处理统计:                                                 ║
║    • 总文件数: {successful_files + failed_files}                              ║
║    • 成功文件: {successful_files}                              ║
║    • 失败文件: {failed_files}                              ║
║    • 成功率: {report['summary']['success_rate']:.1f}%                            ║
║                                                            ║
║  向量化统计:                                               ║
║    • 总chunks: {total_chunks}                              ║
║    • 平均/文件: {report['summary']['average_chunks_per_file']:.1f}                              ║
║    • 总embeddings: {total_embeddings}                              ║
║    • 向量维度: 768                                        ║
║                                                            ║
║  性能统计:                                                 ║
║    • 总耗时: {vectorization_time:.2f} 秒                        ║
║    • 平均/文件: {report['metadata']['average_time_per_file_seconds']:.2f} 秒                        ║
║    • 吞吐量: {report['metadata']['throughput_per_minute']:.1f} 文件/分钟                      ║
║                                                            ║
║  📄 报告已保存:                                            ║
║    {report_file}                                  ║
╚════════════════════════════════════════════════════════════╝
""")
    
    return report

if __name__ == '__main__':
    # 查找最新的收集报告
    import glob
    
    reports = glob.glob('logs/collection_report_*.json')
    if not reports:
        print("❌ 找不到收集报告，请先运行 step1_collect_notes.py")
        sys.exit(1)
    
    latest_report = max(reports, key=os.path.getctime)
    print(f"📄 使用最新报告: {latest_report}")
    
    vectorize_notes(latest_report)
