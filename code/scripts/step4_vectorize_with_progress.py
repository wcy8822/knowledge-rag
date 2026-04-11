#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步骤 4: 执行实际向量化 (含 1 分钟进度报告)

执行完整的向量化流程:
1. 加载收集的文件清单
2. 初始化 BGE-M3 模型
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

from src.vectorization.vectorize_global_notes import GlobalNotesVectorizer
from src.vectorization.collect_notes import NotesCollector

def create_progress_reporter(start_time):
    """创建每分钟报告进度的线程"""
    def progress_reporter():
        """每 60 秒报告一次进度"""
        file_count = 0
        while True:
            time.sleep(60)
            elapsed = time.time() - start_time
            elapsed_min = elapsed / 60
            print(f"⏱️  [{elapsed_min:05.2f}] 向量化正在进行中... (已耗时: {int(elapsed)} 秒, 已处理文件: ~{file_count})")
            sys.stdout.flush()

    reporter = Thread(target=progress_reporter, daemon=True)
    reporter.start()
    return reporter

def main():
    print("=" * 80)
    print("🚀 步骤 4: 执行实际向量化")
    print("=" * 80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    start_time = time.time()

    # 启动进度报告线程
    reporter = create_progress_reporter(start_time)

    try:
        # 1. 加载收集报告
        print("📋 加载文件收集报告...")
        collection_report_files = list(Path('/Users/didi/Downloads/panth/logs').glob('collection_report_*.json'))
        if not collection_report_files:
            print("❌ 找不到收集报告文件")
            return 1

        latest_collection = max(collection_report_files, key=os.path.getctime)
        print(f"✅ 使用报告: {latest_collection.name}")

        # 2. 执行向量化
        print("\n📥 初始化向量化器...")
        vectorizer = GlobalNotesVectorizer(
            db_path='/Users/didi/Downloads/panth/data/chroma',
            batch_size=32
        )

        print(f"🔄 执行向量化流程...")
        result = vectorizer.vectorize_all(str(latest_collection))

        # 3. 生成报告
        elapsed = time.time() - start_time

        print()
        print("=" * 80)
        print("✅ 向量化完成!")
        print("=" * 80)
        print(f"⏱️  总耗时: {elapsed/60:.2f} 分钟")
        print(f"📊 处理文件数: {result.get('total_documents', 0)}")
        print(f"✅ 成功向量化: {result.get('successful_documents', 0)}")
        if result.get('failed_documents', 0) > 0:
            print(f"⚠️  失败文件: {result.get('failed_documents', 0)}")
        print(f"📦 数据库位置: /Users/didi/Downloads/panth/data/chroma/")
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
