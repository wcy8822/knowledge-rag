#!/usr/bin/env python3
"""
阶段1: 全局笔记文件收集
扫描所有笔记文件，生成详细的收集报告
"""

import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import time

def calculate_file_hash(file_path):
    """计算文件SHA256哈希"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def is_valid_file(file_path, max_size_mb=50):
    """验证文件是否有效"""
    try:
        if not file_path.exists():
            return False
        
        # 检查文件大小
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            return False
        
        # 尝试读取前几个字节检查是否是文本文件
        with open(file_path, 'rb') as f:
            first_bytes = f.read(512)
            # 检查是否包含过多的非文本字符
            try:
                first_bytes.decode('utf-8', errors='strict')
            except:
                return False
        
        return True
    except:
        return False

def collect_notes(base_dir="/Users/didi/Downloads/panth"):
    """收集所有笔记文件"""
    
    print(f"\n{'='*80}")
    print(f"🚀 阶段1: 全局笔记文件收集")
    print(f"{'='*80}\n")
    
    start_time = time.time()
    base_path = Path(base_dir)
    
    print(f"📁 扫描目录: {base_path}")
    print(f"📝 文件类型: .md, .txt\n")
    
    # 收集文件
    files = []
    file_hashes = {}
    duplicates = []
    by_extension = defaultdict(list)
    by_directory = defaultdict(list)
    
    total_files_scanned = 0
    total_files_valid = 0
    total_size = 0
    
    # 遍历所有文件
    for file_path in base_path.rglob('*'):
        if not file_path.is_file():
            continue
        
        total_files_scanned += 1
        
        # 只处理支持的格式
        if file_path.suffix.lower() not in ['.md', '.txt']:
            continue
        
        # 验证文件
        if not is_valid_file(file_path):
            print(f"⚠️  跳过无效文件: {file_path.relative_to(base_path)}")
            continue
        
        # 计算哈希
        try:
            file_hash = calculate_file_hash(file_path)
            file_size = file_path.stat().st_size
            
            # 检查重复
            if file_hash in file_hashes:
                duplicates.append({
                    'original': str(file_hashes[file_hash]['path']),
                    'duplicate': str(file_path),
                    'hash': file_hash
                })
                continue
            
            # 记录文件
            file_info = {
                'path': str(file_path),
                'relative_path': str(file_path.relative_to(base_path)),
                'name': file_path.name,
                'size': file_size,
                'size_kb': round(file_size / 1024, 2),
                'extension': file_path.suffix.lower(),
                'hash': file_hash,
                'modified_time': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
            }
            
            files.append(file_info)
            file_hashes[file_hash] = {'path': file_path}
            by_extension[file_path.suffix.lower()].append(file_info)
            
            # 按目录分类
            parent_dir = file_path.parent.relative_to(base_path)
            by_directory[str(parent_dir)].append(file_info)
            
            total_files_valid += 1
            total_size += file_size
            
            # 进度指示
            if total_files_valid % 100 == 0:
                print(f"   📄 已收集 {total_files_valid} 个文件...")
        
        except Exception as e:
            print(f"❌ 处理文件失败: {file_path} - {e}")
            continue
    
    scan_duration = time.time() - start_time
    
    # 生成报告
    report = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "scan_path": str(base_path),
            "total_files_scanned": total_files_scanned,
            "total_files_valid": total_files_valid,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "unique_files": len(files),
            "duplicate_files": len(duplicates),
            "scan_duration_seconds": round(scan_duration, 2)
        },
        "statistics": {
            "by_extension": {
                ext: {
                    "count": len(files_list),
                    "total_size_mb": round(sum(f['size'] for f in files_list) / (1024 * 1024), 2)
                }
                for ext, files_list in by_extension.items()
            },
            "by_directory": {
                dir_path: {
                    "count": len(files_list),
                    "total_size_mb": round(sum(f['size'] for f in files_list) / (1024 * 1024), 2)
                }
                for dir_path, files_list in by_directory.items()
            }
        },
        "files": sorted(files, key=lambda x: x['path']),
        "duplicates": duplicates
    }
    
    # 保存报告
    work_dir = Path(__file__).parent
    logs_dir = work_dir / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    report_file = logs_dir / f"collection_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # 显示结果
    print(f"\n✅ 扫描完成!\n")
    print(f"""
╔════════════════════════════════════════════════════════════╗
║                   📊 文件收集统计                          ║
╠════════════════════════════════════════════════════════════╣
║  扫描统计:                                                 ║
║    • 扫描文件总数: {report['metadata']['total_files_scanned']}                              ║
║    • 有效文件数: {report['metadata']['total_files_valid']}                              ║
║    • 唯一文件数: {report['metadata']['unique_files']}                              ║
║    • 重复文件: {report['metadata']['duplicate_files']}                              ║
║                                                            ║
║  大小统计:                                                 ║
║    • 总数据量: {report['metadata']['total_size_mb']:.2f} MB                          ║
║    • 扫描耗时: {report['metadata']['scan_duration_seconds']:.2f} 秒                     ║
║                                                            ║
║  格式分布:                                                 ║
""")
    
    for ext, stats in report['statistics']['by_extension'].items():
        print(f"║    • {ext:<5} {stats['count']:>4} 个文件  ({stats['total_size_mb']:>8.2f} MB)     ║")
    
    print(f"""║                                                            ║
║  📄 详细报告已保存:                                        ║
║    {report_file}                                  ║
╚════════════════════════════════════════════════════════════╝
""")
    
    return report

if __name__ == '__main__':
    report = collect_notes()
    
    # 显示部分文件清单
    print(f"\n📋 文件清单 (前20个):\n")
    for i, file_info in enumerate(report['files'][:20], 1):
        print(f"{i:3}. {file_info['relative_path']:<60} ({file_info['size_kb']:>8} KB)")
    
    if len(report['files']) > 20:
        print(f"\n    ... 还有 {len(report['files']) - 20} 个文件 ...")
    
    print(f"\n💾 报告位置: logs/collection_report_*.json")
    print(f"🎯 共收集 {report['metadata']['unique_files']} 个有效文件，总大小 {report['metadata']['total_size_mb']:.2f} MB\n")
