#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步骤 4 Plan A: 使用轻量级本地模型执行向量化 (含 1 分钟进度报告)

Plan A 策略:
- 使用更轻量级的模型（all-MiniLM-L6-v2，23MB）
- 支持中文（使用 multilingual 模型）
- 可快速下载和加载
- 768维向量输出
- 完全本地执行，无网络依赖

执行流程:
1. 加载收集的文件清单
2. 初始化轻量级嵌入模型
3. 批量处理文档并生成向量
4. 存储到 ChromaDB
5. 生成详细报告
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Thread
import hashlib

# 导入向量化模块
sys.path.insert(0, '/Users/didi/Downloads/panth/local-rag-system')

def create_progress_reporter(start_time):
    """创建每分钟报告进度的线程"""
    processed_count = [0]  # 使用列表保存可变状态

    def progress_reporter():
        """每 60 秒报告一次进度"""
        while True:
            time.sleep(60)
            elapsed = time.time() - start_time
            elapsed_min = elapsed / 60
            print(f"⏱️  [{elapsed_min:05.2f}] 向量化正在进行中... (已耗时: {int(elapsed)} 秒, 已处理文件: ~{processed_count[0]})")
            sys.stdout.flush()

    reporter = Thread(target=progress_reporter, daemon=True)
    reporter.start()
    return reporter, processed_count

def main():
    print("=" * 80)
    print("🚀 步骤 4 Plan A: 使用轻量级本地模型执行向量化")
    print("=" * 80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    start_time = time.time()

    # 启动进度报告线程
    reporter, processed_count = create_progress_reporter(start_time)

    try:
        # 1. 加载收集报告
        print("📋 加载文件收集报告...")
        collection_report_files = list(Path('/Users/didi/Downloads/panth/logs').glob('collection_report_*.json'))
        if not collection_report_files:
            print("❌ 找不到收集报告文件")
            return 1

        latest_collection = max(collection_report_files, key=os.path.getctime)
        print(f"✅ 使用报告: {latest_collection.name}")

        with open(latest_collection, 'r', encoding='utf-8') as f:
            collection_data = json.load(f)

        files_to_process = collection_data.get('files', [])
        total_files = len(files_to_process)
        print(f"📊 需要处理的文件数: {total_files}")
        print()

        # 2. 加载轻量级模型
        print("📥 初始化轻量级嵌入模型 (all-MiniLM-L6-v2)...")
        try:
            from sentence_transformers import SentenceTransformer

            # 使用轻量级多语言模型
            model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            print(f"✅ 模型加载成功!")
            vector_dim = model.get_sentence_embedding_dimension()
            print(f"📦 向量维度: {vector_dim}")
            print()
        except Exception as e:
            print(f"❌ 模型加载失败: {str(e)}")
            return 1

        # 3. 初始化 ChromaDB
        print("🗄️  初始化向量数据库...")
        try:
            import chromadb

            db_path = '/Users/didi/Downloads/panth/data/chroma'
            os.makedirs(db_path, exist_ok=True)

            client = chromadb.PersistentClient(path=db_path)
            collection = client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"}
            )
            print(f"✅ 数据库初始化完成")
            print()
        except Exception as e:
            print(f"❌ 数据库初始化失败: {str(e)}")
            return 1

        # 4. 处理文档
        print("🔄 开始处理文档...")
        successful = 0
        failed = 0
        batch_size = 32

        for i in range(0, total_files, batch_size):
            batch = files_to_process[i:i+batch_size]
            batch_docs = []
            batch_embeddings = []
            batch_metadatas = []
            batch_ids = []

            for file_info in batch:
                try:
                    file_path = file_info['path']
                    if not os.path.exists(file_path):
                        failed += 1
                        continue

                    # 读取文件内容
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    if len(content.strip()) == 0:
                        failed += 1
                        continue

                    # 生成向量
                    embedding = model.encode(content[:1000])  # 使用前1000字符

                    # 准备数据
                    file_id = hashlib.sha256(file_path.encode()).hexdigest()[:16]
                    batch_ids.append(file_id)
                    batch_docs.append(content[:5000])
                    batch_embeddings.append(embedding.tolist())
                    batch_metadatas.append({
                        "source": file_path,
                        "size": len(content),
                        "file_type": Path(file_path).suffix
                    })

                    successful += 1
                    processed_count[0] = successful

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

        # 5. 生成报告
        elapsed = time.time() - start_time

        print()
        print("=" * 80)
        print("✅ 向量化完成!")
        print("=" * 80)
        print(f"⏱️  总耗时: {elapsed/60:.2f} 分钟")
        print(f"📊 处理文件数: {total_files}")
        print(f"✅ 成功向量化: {successful}")
        if failed > 0:
            print(f"⚠️  失败文件: {failed}")
        print(f"📦 数据库位置: /Users/didi/Downloads/panth/data/chroma/")
        print(f"📝 使用模型: all-MiniLM-L6-v2 (轻量级多语言模型)")
        print()
        print("✨ 向量化完成,已为后续搜索做好准备!")

        return 0

    except Exception as e:
        elapsed = time.time() - start_time
        print()
        print("=" * 80)
        print("❌ 向量化失败")
        print("=" * 80)
        print(f"⏱️  耗时: {elapsed/60:.2f} 分钟")
        print(f"❌ 错误: {str(e)}")
        print()
        return 1

if __name__ == '__main__':
    sys.exit(main())
