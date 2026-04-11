#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📦 一体化向量化解决方案 (One-Shot Vectorization)

直接执行完整的向量化流程:
1. 扫描所有文件 (.md, .txt)
2. 使用轻量级模型 (all-MiniLM-L6-v2, 23 MB)
3. 存储到 ChromaDB 本地向量库
4. 生成清单和验证报告

执行方式:
  python3 vectorize_all_in_one.py
"""

import os
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

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
        # 过滤排除目录
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        for filename in filenames:
            if filename.endswith(('.md', '.txt')):
                filepath = os.path.join(root, filename)
                try:
                    # 检查文件是否可读
                    if not os.access(filepath, os.R_OK):
                        continue

                    # 获取文件大小
                    size = os.path.getsize(filepath)
                    if size == 0:
                        continue

                    # SHA256 去重
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

def load_model():
    """加载轻量级嵌入模型"""
    print("=" * 80)
    print("🤖 第二步: 加载嵌入模型")
    print("=" * 80)
    print("📥 加载 all-MiniLM-L6-v2 (23 MB, 384维)")

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        dim = model.get_sentence_embedding_dimension()
        print(f"✅ 模型加载成功!")
        print(f"📦 向量维度: {dim}")
        print()
        return model
    except Exception as e:
        print(f"❌ 模型加载失败: {str(e)}")
        exit(1)

def init_vectordb(db_path: str):
    """初始化向量数据库"""
    print("=" * 80)
    print("🗄️  第三步: 初始化向量数据库")
    print("=" * 80)
    print(f"📁 数据库位置: {db_path}")

    try:
        import chromadb
        os.makedirs(db_path, exist_ok=True)

        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
        print(f"✅ 向量数据库初始化完成")
        print()
        return collection
    except Exception as e:
        print(f"❌ 数据库初始化失败: {str(e)}")
        exit(1)

def vectorize_documents(files: List[Dict], model, collection, batch_size: int = 32) -> Dict[str, int]:
    """向量化所有文档"""
    print("=" * 80)
    print("⚡ 第四步: 向量化文档")
    print("=" * 80)
    print(f"📊 需要处理: {len(files)} 个文件")
    print(f"📦 批处理大小: {batch_size}")
    print()

    successful = 0
    failed = 0
    start_time = time.time()

    for i in range(0, len(files), batch_size):
        batch = files[i:i+batch_size]
        batch_ids = []
        batch_embeddings = []
        batch_docs = []
        batch_metadatas = []

        for file_info in batch:
            try:
                filepath = file_info['path']

                # 读取文件内容
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                if len(content.strip()) == 0:
                    failed += 1
                    continue

                # 生成向量 (使用前 1000 字符)
                text_chunk = content[:1000]
                embedding = model.encode(text_chunk)

                # 准备数据库记录
                doc_id = hashlib.sha256(filepath.encode()).hexdigest()[:16]

                batch_ids.append(doc_id)
                batch_embeddings.append(embedding.tolist())
                batch_docs.append(content[:5000])  # 存储前 5000 字符
                batch_metadatas.append({
                    "source": filepath,
                    "size": len(content),
                    "type": Path(filepath).suffix,
                    "name": file_info['name']
                })

                successful += 1

            except Exception as e:
                failed += 1
                continue

        # 批量添加到数据库
        if batch_ids:
            try:
                collection.add(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    documents=batch_docs,
                    metadatas=batch_metadatas
                )
            except Exception as e:
                print(f"⚠️  批量添加失败: {str(e)}")

        # 进度报告
        progress = min(successful + failed, len(files))
        elapsed = time.time() - start_time
        rate = successful / elapsed if elapsed > 0 else 0
        eta = (len(files) - successful) / rate if rate > 0 else 0

        print(f"  [{progress:4d}/{len(files)}] ✅ {successful} | ❌ {failed} | "
              f"速度: {rate:.1f} docs/s | ETA: {eta/60:.1f}m")

    print()
    print(f"✅ 向量化完成!")
    print(f"   - 成功: {successful}")
    print(f"   - 失败: {failed}")
    print(f"   - 总耗时: {(time.time() - start_time) / 60:.2f} 分钟")
    print()

    return {'successful': successful, 'failed': failed}

def generate_report(files: List[Dict], results: Dict[str, int], db_path: str) -> None:
    """生成详细报告"""
    print("=" * 80)
    print("📄 第五步: 生成报告")
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
        'model': 'sentence-transformers/all-MiniLM-L6-v2',
        'vector_dimension': 384,
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
        f.write("🎯 向量化完成清单\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总文件数: {len(files)}\n")
        f.write(f"成功: {results['successful']}\n")
        f.write(f"失败: {results['failed']}\n")
        f.write(f"向量库位置: {db_path}\n")
        f.write(f"报告文件: {report_path}\n\n")
        f.write("✅ 已包含的文件:\n")
        for f in files[:20]:  # 显示前 20 个
            f.write(f"  - {f['name']} ({f['size'] / 1024:.1f} KB)\n")
        if len(files) > 20:
            f.write(f"  ... 以及其他 {len(files) - 20} 个文件\n")

    print(f"📋 清单已保存: {manifest_path}")
    print()

def main():
    """主程序"""
    print("\n")
    print("█" * 80)
    print("🚀 一体化向量化系统 v1.0")
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

    # 步骤 2: 加载模型
    model = load_model()

    # 步骤 3: 初始化数据库
    db_path = '/Users/didi/Downloads/panth/data/chroma'
    collection = init_vectordb(db_path)

    # 步骤 4: 向量化
    results = vectorize_documents(files, model, collection)

    # 步骤 5: 生成报告
    generate_report(files, results, db_path)

    # 完成
    total_time = time.time() - start_time
    print("=" * 80)
    print("✨ 向量化流程完成!")
    print("=" * 80)
    print(f"⏱️  总耗时: {total_time / 60:.2f} 分钟")
    print(f"📊 成功率: {results['successful'] / len(files) * 100:.1f}%")
    print()
    print("可以开始进行语义搜索了! 🎉")
    print()

    return 0

if __name__ == '__main__':
    exit(main())
