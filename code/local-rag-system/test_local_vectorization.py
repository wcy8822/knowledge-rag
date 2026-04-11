#!/usr/bin/env python3
"""
本地RAG系统 - 笔记文件向量化测试脚本

功能：
1. 自动收集本地笔记文件（Markdown、TXT等）
2. 使用BGE-M3进行向量化
3. 存储到ChromaDB本地向量数据库
4. 执行混合搜索验证
"""

import sys
import os
from pathlib import Path
import logging
from typing import List, Dict, Any

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.config import config
from src.ingest.processor import DocumentProcessor
from src.store.embedding_service import EmbeddingService
from src.store.vector_stores.chroma_store import ChromaVectorStore
from src.search.hybrid_searcher import HybridSearcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LocalNotesVectorizer:
    """本地笔记向量化工具"""

    def __init__(self):
        self.processor = DocumentProcessor()
        self.embedding_service = EmbeddingService()
        self.vector_store = ChromaVectorStore()
        self.searcher = HybridSearcher()
        logger.info("✅ 初始化向量化系统")

    def collect_notes(self, notes_dir: str = None) -> List[str]:
        """
        收集本地笔记文件

        Args:
            notes_dir: 笔记文件目录，如果为None则使用默认位置

        Returns:
            笔记文件路径列表
        """
        if notes_dir is None:
            # 优先使用项目data/uploads目录，或用户指定的目录
            notes_dir = "./data/uploads"

            # 如果目录不存在，创建它
            Path(notes_dir).mkdir(parents=True, exist_ok=True)

        notes_path = Path(notes_dir)

        # 支持的文件格式
        supported_formats = ('*.md', '*.txt', '*.markdown', '*.docx', '*.pdf')

        # 收集所有笔记文件
        note_files = []
        for pattern in supported_formats:
            note_files.extend(notes_path.glob(pattern))
            note_files.extend(notes_path.glob(f'**/{pattern}'))  # 递归查找

        # 去重
        note_files = list(set(note_files))

        logger.info(f"📚 找到 {len(note_files)} 个笔记文件")
        for note in sorted(note_files):
            logger.info(f"   - {note}")

        return [str(f) for f in note_files]

    def vectorize_notes(self, notes_files: List[str]) -> Dict[str, Any]:
        """
        向量化笔记文件

        Args:
            notes_files: 笔记文件路径列表

        Returns:
            向量化结果统计
        """
        if not notes_files:
            logger.warning("⚠️  没有找到笔记文件")
            return {"status": "no_files", "count": 0}

        results = {
            "total_files": len(notes_files),
            "successfully_processed": 0,
            "failed_files": [],
            "total_chunks": 0,
            "documents": []
        }

        logger.info(f"\n🚀 开始向量化 {len(notes_files)} 个文件...")

        for i, note_file in enumerate(notes_files, 1):
            try:
                logger.info(f"\n[{i}/{len(notes_files)}] 处理: {Path(note_file).name}")

                # 处理文档
                document = self.processor.process_file(note_file)

                if document and document.chunks:
                    logger.info(f"   ✅ 解析成功，生成 {len(document.chunks)} 个chunks")

                    # 向量化chunks
                    for chunk in document.chunks:
                        # 计算向量
                        embedding = self.embedding_service.embed([chunk.text])[0]
                        chunk.embedding = embedding

                    # 存储到向量数据库
                    stored_ids = self.vector_store.add_documents(document.chunks)
                    logger.info(f"   💾 存储成功，ID: {stored_ids[:3]}...")

                    results["successfully_processed"] += 1
                    results["total_chunks"] += len(document.chunks)
                    results["documents"].append({
                        "file": Path(note_file).name,
                        "chunks": len(document.chunks),
                        "status": "success"
                    })
                else:
                    logger.warning(f"   ❌ 解析失败或无内容")
                    results["failed_files"].append(note_file)

            except Exception as e:
                logger.error(f"   ❌ 处理失败: {e}")
                results["failed_files"].append(note_file)

        logger.info(f"\n📊 向量化完成：")
        logger.info(f"   ✅ 成功处理: {results['successfully_processed']}/{len(notes_files)}")
        logger.info(f"   📄 总chunks数: {results['total_chunks']}")
        logger.info(f"   ❌ 失败文件: {len(results['failed_files'])}")

        return results

    def test_search(self, queries: List[str] = None) -> None:
        """
        测试搜索功能

        Args:
            queries: 测试查询列表
        """
        if queries is None:
            queries = [
                "关键概念",
                "重要内容",
                "最近更新",
                "工作总结",
                "项目进展"
            ]

        logger.info(f"\n🔍 测试搜索功能（共{len(queries)}个查询）...")

        # 初始化搜索器
        if not self.searcher.initialize():
            logger.error("❌ 搜索器初始化失败")
            return

        for query in queries:
            try:
                logger.info(f"\n📌 查询: {query}")

                # 执行混合搜索
                results = self.searcher.search(query, top_k=5)

                if results:
                    logger.info(f"   ✅ 找到 {len(results)} 个相关结果:")
                    for j, result in enumerate(results[:3], 1):  # 只显示前3个
                        score = result.get('score', 0)
                        text = result.get('text', '')[:100]
                        logger.info(f"      {j}. [相似度: {score:.3f}] {text}...")
                else:
                    logger.info(f"   ⚠️  未找到相关结果")

            except Exception as e:
                logger.error(f"   ❌ 搜索失败: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        stats = {
            "collection_count": len(self.vector_store.collection.get()["ids"]) if self.vector_store.collection else 0,
            "vector_db_type": "ChromaDB",
            "embedding_model": self.embedding_service.model_name,
            "device": self.embedding_service.device,
        }

        logger.info(f"\n📈 系统统计:")
        logger.info(f"   📦 向量数量: {stats['collection_count']}")
        logger.info(f"   🗄️  数据库: {stats['vector_db_type']}")
        logger.info(f"   🧠 嵌入模型: {stats['embedding_model']}")
        logger.info(f"   ⚙️  运行设备: {stats['device']}")

        return stats


def main():
    """主程序"""
    logger.info("=" * 60)
    logger.info("🎯 本地RAG系统 - 笔记向量化测试")
    logger.info("=" * 60)

    # 初始化向量化工具
    vectorizer = LocalNotesVectorizer()

    # 第1步：收集笔记文件
    logger.info("\n📂 第1步：收集笔记文件")
    logger.info("-" * 60)
    notes_files = vectorizer.collect_notes()

    if not notes_files:
        logger.warning("\n⚠️  未找到笔记文件")
        logger.info("💡 请将笔记文件（.md, .txt, .docx等）放入 ./data/uploads 目录")
        logger.info("   或运行: ./scripts/ingest.sh -i /your/notes/path")
        sys.exit(1)

    # 第2步：向量化笔记
    logger.info("\n🔄 第2步：向量化笔记文件")
    logger.info("-" * 60)
    results = vectorizer.vectorize_notes(notes_files)

    if results["total_chunks"] == 0:
        logger.warning("\n⚠️  未生成任何向量数据")
        sys.exit(1)

    # 第3步：系统统计
    logger.info("\n📊 第3步：系统统计")
    logger.info("-" * 60)
    stats = vectorizer.get_stats()

    # 第4步：测试搜索
    logger.info("\n🔍 第4步：测试搜索功能")
    logger.info("-" * 60)
    vectorizer.test_search()

    # 成功信息
    logger.info("\n" + "=" * 60)
    logger.info("✅ 向量化测试完成！")
    logger.info("=" * 60)
    logger.info("\n📌 后续步骤:")
    logger.info("   1. 启动API服务: ./scripts/serve.sh")
    logger.info("   2. 访问Web界面: http://localhost:8000/docs")
    logger.info("   3. 执行搜索查询: POST /api/v1/search")
    logger.info("   4. 智能问答: POST /api/v1/search/ask")


if __name__ == "__main__":
    main()
