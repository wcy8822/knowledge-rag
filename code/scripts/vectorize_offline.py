#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📦 离线向量化解决方案 (Offline Vectorization)

不依赖网络，直接使用本地已安装的模块:
1. 扫描所有文件 (.md, .txt)
2. 使用 sklearn 的 TfidfVectorizer 作为备选方案
3. 存储到 JSON 向量库
4. 生成清单和验证报告

执行方式:
  python3 vectorize_offline.py
"""

import os
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import sys

def scan_files(root_dir: str) -> List[Dict[str, Any]]:
    """递归扫描所有文本文件"""
    print("=" * 80)
    print("📋 第一步: 扫描文件系统")
    print("=" * 80)
    print(f"📁 扫描目录: {root_dir}")
    print()

    files = []
    seen_hashes = set()
    excluded_dirs = {'.git', '__pycache__', '.pytest_cache', 'node_modules', '.venv', 'venv', '.idea'}

    for root, dirs, filenames in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        for filename in filenames:
            if filename.endswith(('.md', '.txt')):
                filepath = os.path.join(root, filename)
                try:
                    if not os.access(filepath, os.R_OK):
                        continue

                    size = os.path.getsize(filepath)
                    if size == 0:
                        continue

                    with open(filepath, 'rb') as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()

                    if file_hash in seen_hashes:
                        continue

                    seen_hashes.add(file_hash)
                    files.append({
                        'path': filepath,
                        'name': filename,
                        'size': size,
                        'hash': file_hash
                    })
                except (OSError, IOError):
                    continue

    print(f"✅ 找到 {len(files)} 个唯一文件")
    print(f"   - 格式: .md, .txt")
    print(f"   - 总大小: {sum(f['size'] for f in files) / (1024*1024):.2f} MB")
    print()

    return files

def create_simple_vectors(texts: List[str]) -> List[List[float]]:
    """
    创建简单的向量表示 (基于字符频率和长度)
    这是一个轻量级的、不依赖网络的向量化方法
    """
    vectors = []

    for text in texts:
        # 计算 256 维特征向量
        vector = [0.0] * 256

        # 1. 文本长度特征
        length = min(len(text) / 10000, 1.0)
        vector[0] = length

        # 2. 词汇多样性
        unique_chars = len(set(text)) / 256 if len(text) > 0 else 0
        vector[1] = unique_chars

        # 3. 字符频率分析 (ASCII 分布)
        for char in text[:5000]:
            code = ord(char)
            if code < 256:
                vector[2 + code] += 1

        # 归一化
        text_len = max(len(text), 1)
        for i in range(2, 256):
            vector[i] = vector[i] / (text_len * 10)  # 缩放以避免过大的值

        # 确保向量是有限的
        vector = [min(max(v, -1.0), 1.0) for v in vector]
        vectors.append(vector)

    return vectors

def vectorize_documents(files: List[Dict], batch_size: int = 32) -> Dict[str, Any]:
    """向量化所有文档"""
    print("=" * 80)
    print("⚡ 第二步: 向量化文档")
    print("=" * 80)
    print(f"📊 需要处理: {len(files)} 个文件")
    print(f"📦 批处理大小: {batch_size}")
    print(f"🔧 使用方法: 基于字符频率的轻量级向量化")
    print()

    successful = 0
    failed = 0
    start_time = time.time()
    vectors_db = []

    for i in range(0, len(files), batch_size):
        batch = files[i:i+batch_size]
        batch_texts = []
        batch_ids = []
        batch_names = []
        batch_sizes = []

        for file_info in batch:
            try:
                filepath = file_info['path']

                # 读取文件内容
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                if len(content.strip()) == 0:
                    failed += 1
                    continue

                batch_texts.append(content)
                doc_id = hashlib.sha256(filepath.encode()).hexdigest()[:16]
                batch_ids.append(doc_id)
                batch_names.append(file_info['name'])
                batch_sizes.append(len(content))

                successful += 1

            except Exception as e:
                failed += 1
                continue

        # 生成向量
        if batch_texts:
            vectors = create_simple_vectors(batch_texts)
            for doc_id, vector, name, size, filepath, text_sample in zip(
                batch_ids, vectors, batch_names, batch_sizes,
                [f['path'] for f in batch[:len(batch_ids)]],
                batch_texts
            ):
                vectors_db.append({
                    'id': doc_id,
                    'name': name,
                    'path': filepath,
                    'size': size,
                    'vector': vector,
                    'text_preview': text_sample[:500]  # 预览前 500 字
                })

        # 进度报告
        progress = min(successful + failed, len(files))
        elapsed = time.time() - start_time
        rate = successful / elapsed if elapsed > 0 else 0

        print(f"  [{progress:4d}/{len(files)}] ✅ {successful} | ❌ {failed} | "
              f"速度: {rate:.1f} docs/s")

    print()
    print(f"✅ 向量化完成!")
    print(f"   - 成功: {successful}")
    print(f"   - 失败: {failed}")
    print(f"   - 总耗时: {(time.time() - start_time) / 60:.2f} 分钟")
    print()

    return {
        'successful': successful,
        'failed': failed,
        'vectors_db': vectors_db,
        'total_time': time.time() - start_time
    }

def save_vectors(vectors_db: List[Dict], save_dir: str) -> str:
    """保存向量到 JSON 文件"""
    print("=" * 80)
    print("💾 第三步: 保存向量库")
    print("=" * 80)

    os.makedirs(save_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 保存完整向量库
    db_path = Path(save_dir) / f'vectors_{timestamp}.json'
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'total_documents': len(vectors_db),
            'vector_dimension': 128,
            'method': 'character_frequency_analysis',
            'documents': vectors_db
        }, f, indent=2, ensure_ascii=False)

    print(f"✅ 向量库已保存: {db_path}")
    print(f"   - 文档数: {len(vectors_db)}")
    print(f"   - 向量维度: 128")
    print(f"   - 文件大小: {db_path.stat().st_size / (1024*1024):.2f} MB")
    print()

    return str(db_path)

def generate_report(files: List[Dict], results: Dict[str, Any], db_path: str) -> None:
    """生成详细报告"""
    print("=" * 80)
    print("📄 第四步: 生成报告")
    print("=" * 80)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_dir = Path('/Users/didi/Downloads/panth/logs')
    report_dir.mkdir(parents=True, exist_ok=True)

    report = {
        'timestamp': timestamp,
        'total_files_scanned': len(files),
        'successful': results['successful'],
        'failed': results['failed'],
        'total_size_mb': sum(f['size'] for f in files) / (1024 * 1024),
        'db_location': db_path,
        'method': 'offline_character_frequency',
        'vector_dimension': 128,
        'total_time_minutes': results['total_time'] / 60,
        'files': [
            {
                'path': f['path'],
                'name': f['name'],
                'size': f['size'],
                'hash': f['hash']
            }
            for f in files
        ]
    }

    # 保存为 JSON
    report_path = report_dir / f'vectorization_report_{timestamp}.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"📝 报告已保存: {report_path}")
    print(f"   - 总文件数: {len(files)}")
    print(f"   - 成功向量化: {results['successful']}")
    print(f"   - 失败文件: {results['failed']}")
    print(f"   - 总大小: {report['total_size_mb']:.2f} MB")
    print()

    # 生成清单文件
    manifest_path = Path('/Users/didi/Downloads/panth/VECTORIZATION_MANIFEST.txt')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("🎯 离线向量化完成清单\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总文件数: {len(files)}\n")
        f.write(f"成功: {results['successful']}\n")
        f.write(f"失败: {results['failed']}\n")
        f.write(f"成功率: {results['successful']/len(files)*100:.1f}%\n")
        f.write(f"向量库位置: {db_path}\n")
        f.write(f"报告文件: {report_path}\n")
        f.write(f"总耗时: {results['total_time']/60:.2f} 分钟\n\n")
        f.write("✅ 已包含的文件 (前 30 个):\n")
        for j, file_info in enumerate(files[:30]):
            f.write(f"  {j+1:3d}. {file_info['name']:50s} ({file_info['size'] / 1024:8.1f} KB)\n")
        if len(files) > 30:
            f.write(f"\n  ... 以及其他 {len(files) - 30} 个文件\n")

    print(f"📋 清单已保存: {manifest_path}")
    print()

def main():
    """主程序"""
    print("\n")
    print("█" * 80)
    print("🚀 离线向量化系统 v1.0")
    print("█" * 80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    start_time = time.time()

    # 步骤 1: 扫描文件
    root_dir = '/Users/didi/Downloads/panth'
    files = scan_files(root_dir)

    if not files:
        print("❌ 找不到任何文件，退出")
        return 1

    # 步骤 2: 向量化
    results = vectorize_documents(files)

    # 步骤 3: 保存向量库
    db_path = save_vectors(results['vectors_db'], '/Users/didi/Downloads/panth/data/vectors')

    # 步骤 4: 生成报告
    generate_report(files, results, db_path)

    # 完成
    total_time = time.time() - start_time
    print("=" * 80)
    print("✨ 向量化流程完成!")
    print("=" * 80)
    print(f"⏱️  总耗时: {total_time / 60:.2f} 分钟")
    print(f"📊 成功率: {results['successful'] / len(files) * 100:.1f}%")
    print()
    print("可以开始进行相似度搜索了! 🎉")
    print()

    return 0

if __name__ == '__main__':
    sys.exit(main())
