#!/usr/bin/env python3
"""
全局笔记向量化模块
执行文件的向量化处理，包括文档解析、分块、嵌入和存储
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import traceback

# 添加src路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.vectorization.utils import (
    save_json_report,
    generate_timestamp,
    generate_report_filename,
    ensure_directory_exists,
    format_bytes,
    print_section_header,
    print_subsection,
    print_progress
)

# 导入RAG系统组件
from src.store.embedding_service import EmbeddingService
from src.store.vector_stores.chroma_store import ChromaVectorStore
from src.ingest.document_processor import DocumentProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GlobalNotesVectorizer:
    """
    全局笔记向量化处理器

    功能：
    - 加载收集的笔记文件列表
    - 处理文档（解析、分块）
    - 生成向量嵌入
    - 存储到向量数据库
    - 生成详细的处理日志
    """

    def __init__(self, collection_report_path: str, output_dir: str = "logs"):
        """
        初始化向量化处理器

        Args:
            collection_report_path: 收集报告的路径
            output_dir: 日志输出目录
        """
        self.collection_report_path = collection_report_path
        self.output_dir = output_dir
        ensure_directory_exists(output_dir)

        # 初始化RAG系统组件
        logger.info("初始化RAG系统组件...")
        self.embedding_service = EmbeddingService()
        self.vector_store = ChromaVectorStore()
        self.document_processor = DocumentProcessor()

        # 处理统计数据
        self.stats = {
            "timestamp": generate_timestamp(),
            "total_files": 0,
            "successfully_processed": 0,
            "failed_files": [],
            "total_chunks": 0,
            "total_vectors_generated": 0,
            "total_vectors_stored": 0,
            "total_size_bytes": 0,
            "embedding_time_seconds": 0.0,
            "storage_time_seconds": 0.0,
            "errors": [],
            "skipped": [],
            "processing_log": []
        }

        # 文件列表
        self.files_to_process = []

    def load_collection_report(self) -> bool:
        """
        加载收集报告并获取要处理的文件列表

        Returns:
            是否成功加载
        """
        try:
            logger.info(f"加载收集报告: {self.collection_report_path}")

            with open(self.collection_report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)

            self.files_to_process = report.get("files", [])
            self.stats["total_files"] = len(self.files_to_process)

            logger.info(f"✅ 加载完成: {self.stats['total_files']} 个文件")
            return True

        except Exception as e:
            error_msg = f"加载收集报告失败: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)
            return False

    def process_file(self, file_info: Dict[str, Any], file_idx: int) -> Dict[str, Any]:
        """
        处理单个文件

        Args:
            file_info: 文件元数据
            file_idx: 文件索引

        Returns:
            处理结果
        """
        file_path = file_info["path"]
        file_id = file_info["id"]
        filename = file_info["filename"]

        result = {
            "file_id": file_id,
            "filename": filename,
            "path": file_path,
            "status": "pending",
            "chunks": 0,
            "vectors": 0,
            "error": None,
            "timestamp": generate_timestamp()
        }

        try:
            # 1. 检查文件是否存在
            if not os.path.exists(file_path):
                error_msg = f"文件不存在: {file_path}"
                logger.warning(error_msg)
                result["status"] = "skipped"
                result["error"] = error_msg
                self.stats["skipped"].append(error_msg)
                return result

            # 2. 处理文档
            logger.debug(f"处理文件: {filename}")
            documents = self.document_processor.process_file(file_path)

            if not documents:
                error_msg = f"文档解析失败: {filename}"
                logger.warning(error_msg)
                result["status"] = "failed"
                result["error"] = error_msg
                self.stats["failed_files"].append(filename)
                self.stats["errors"].append(error_msg)
                return result

            result["chunks"] = len(documents)
            self.stats["total_chunks"] += len(documents)

            # 3. 生成向量嵌入
            logger.debug(f"生成向量: {len(documents)} 个分块")
            import time
            embed_start = time.time()

            # 批量处理文本
            texts = [doc.page_content for doc in documents]
            embeddings = self.embedding_service.embed_texts(texts)

            embed_time = time.time() - embed_start
            self.stats["embedding_time_seconds"] += embed_time

            if not embeddings or len(embeddings) != len(documents):
                error_msg = f"向量生成失败: {filename}"
                logger.error(error_msg)
                result["status"] = "failed"
                result["error"] = error_msg
                self.stats["failed_files"].append(filename)
                self.stats["errors"].append(error_msg)
                return result

            result["vectors"] = len(embeddings)
            self.stats["total_vectors_generated"] += len(embeddings)

            # 4. 存储向量
            logger.debug(f"存储向量: {len(embeddings)} 个")
            store_start = time.time()

            # 为每个向量准备元数据
            metadatas = []
            ids = []
            for chunk_idx, doc in enumerate(documents):
                chunk_id = f"{file_id}_chunk_{chunk_idx:03d}"
                ids.append(chunk_id)

                metadata = {
                    "file_id": file_id,
                    "filename": filename,
                    "chunk_index": chunk_idx,
                    "file_path": file_path,
                    "file_format": file_info["format"],
                    "chunk_text": doc.page_content[:500],  # 前500个字符用于调试
                    "processed_at": generate_timestamp()
                }
                metadatas.append(metadata)

            # 存储到向量数据库
            self.vector_store.add_documents(
                documents=[doc.page_content for doc in documents],
                embeddings=embeddings,
                ids=ids,
                metadatas=metadatas
            )

            store_time = time.time() - store_start
            self.stats["storage_time_seconds"] += store_time

            self.stats["total_vectors_stored"] += len(embeddings)

            # 5. 更新状态
            result["status"] = "success"
            result["embed_time"] = embed_time
            result["store_time"] = store_time

            logger.info(f"  ✅ {filename}: {len(documents)} 个分块, {len(embeddings)} 个向量")

            return result

        except Exception as e:
            error_msg = f"处理文件异常 {filename}: {e}"
            logger.error(error_msg)
            logger.debug(traceback.format_exc())
            result["status"] = "failed"
            result["error"] = error_msg
            self.stats["failed_files"].append(filename)
            self.stats["errors"].append(error_msg)
            return result

    def vectorize_all(self) -> bool:
        """
        向量化所有文件

        Returns:
            是否全部成功
        """
        logger.info("=" * 70)
        logger.info("🚀 开始全局笔记向量化")
        logger.info("=" * 70)

        if not self.files_to_process:
            logger.error("没有要处理的文件")
            return False

        logger.info(f"\n📝 要处理的文件: {len(self.files_to_process)}")

        # 处理每个文件
        for idx, file_info in enumerate(self.files_to_process):
            # 进度条
            print_progress(idx, len(self.files_to_process), prefix="向量化进度")

            # 处理文件
            result = self.process_file(file_info, idx)
            self.stats["processing_log"].append(result)

            # 更新统计
            if result["status"] == "success":
                self.stats["successfully_processed"] += 1
                self.stats["total_size_bytes"] += file_info.get("size_bytes", 0)

        # 完成进度条
        print_progress(len(self.files_to_process), len(self.files_to_process), prefix="向量化进度")

        logger.info(f"\n✅ 向量化完成")
        logger.info(f"  成功: {self.stats['successfully_processed']}/{self.stats['total_files']}")
        logger.info(f"  总分块数: {self.stats['total_chunks']}")
        logger.info(f"  总向量数: {self.stats['total_vectors_stored']}")

        return self.stats["successfully_processed"] == self.stats["total_files"]

    def generate_report(self) -> Dict[str, Any]:
        """
        生成详细的向量化报告

        Returns:
            报告字典
        """
        # 统计成功率
        success_rate = (
            self.stats["successfully_processed"] / self.stats["total_files"] * 100
            if self.stats["total_files"] > 0 else 0
        )

        # 计算平均处理时间
        avg_embed_time = (
            self.stats["embedding_time_seconds"] / self.stats["total_chunks"]
            if self.stats["total_chunks"] > 0 else 0
        )

        avg_store_time = (
            self.stats["storage_time_seconds"] / self.stats["total_vectors_stored"]
            if self.stats["total_vectors_stored"] > 0 else 0
        )

        summary = {
            "timestamp": self.stats["timestamp"],
            "total_files": self.stats["total_files"],
            "successfully_processed": self.stats["successfully_processed"],
            "failed_count": len(self.stats["failed_files"]),
            "skipped_count": len(self.stats["skipped"]),
            "success_rate": f"{success_rate:.2f}%",
            "total_chunks": self.stats["total_chunks"],
            "total_vectors_generated": self.stats["total_vectors_generated"],
            "total_vectors_stored": self.stats["total_vectors_stored"],
            "total_size_bytes": self.stats["total_size_bytes"],
            "total_size_human": format_bytes(self.stats["total_size_bytes"]),
            "embedding_time_seconds": round(self.stats["embedding_time_seconds"], 2),
            "storage_time_seconds": round(self.stats["storage_time_seconds"], 2),
            "avg_embed_time_ms": round(avg_embed_time * 1000, 2),
            "avg_store_time_ms": round(avg_store_time * 1000, 2),
            "failed_files": self.stats["failed_files"],
            "errors": self.stats["errors"][:10]  # 只保存前10个错误
        }

        report = {
            "metadata": {
                "report_type": "vectorization",
                "version": "1.0",
                "generated_at": generate_timestamp(),
                "generator": "GlobalNotesVectorizer"
            },
            "summary": summary,
            "processing_log": self.stats["processing_log"]
        }

        return report

    def save_report(self) -> str:
        """
        保存向量化报告

        Returns:
            保存的报告文件路径
        """
        report = self.generate_report()

        # 生成报告文件名
        report_filename = generate_report_filename("vectorization_report", "json")
        report_path = os.path.join(self.output_dir, report_filename)

        # 保存报告
        success = save_json_report(report, report_path)

        if success:
            logger.info(f"✅ 报告已保存: {report_path}")
            return report_path
        else:
            logger.error(f"❌ 报告保存失败: {report_path}")
            return None

    def print_summary(self):
        """
        打印向量化摘要
        """
        print_section_header("📊 向量化处理摘要", width=70)

        print(f"\n📈 处理统计:")
        print(f"  • 总文件数: {self.stats['total_files']}")
        print(f"  • 成功处理: {self.stats['successfully_processed']}")
        print(f"  • 失败: {len(self.stats['failed_files'])}")
        print(f"  • 跳过: {len(self.stats['skipped'])}")

        if self.stats['total_files'] > 0:
            success_rate = self.stats['successfully_processed'] / self.stats['total_files'] * 100
            print(f"  • 成功率: {success_rate:.1f}%")

        print(f"\n📊 向量统计:")
        print(f"  • 总分块数: {self.stats['total_chunks']}")
        print(f"  • 生成向量: {self.stats['total_vectors_generated']}")
        print(f"  • 存储向量: {self.stats['total_vectors_stored']}")

        print(f"\n⏱️  性能指标:")
        print(f"  • 嵌入耗时: {self.stats['embedding_time_seconds']:.2f}s")
        print(f"  • 存储耗时: {self.stats['storage_time_seconds']:.2f}s")
        print(f"  • 总耗时: {self.stats['embedding_time_seconds'] + self.stats['storage_time_seconds']:.2f}s")

        print(f"\n💾 数据统计:")
        print(f"  • 处理大小: {format_bytes(self.stats['total_size_bytes'])}")

        if self.stats['failed_files']:
            print(f"\n⚠️  失败的文件 ({len(self.stats['failed_files'])})")
            for filename in self.stats['failed_files'][:5]:
                print(f"  • {filename}")
            if len(self.stats['failed_files']) > 5:
                print(f"  ... 及 {len(self.stats['failed_files']) - 5} 个更多")

        if self.stats['errors']:
            print(f"\n❌ 错误信息 ({len(self.stats['errors'])})")
            for error in self.stats['errors'][:3]:
                print(f"  • {error}")

        print(f"\n✅ 向量化准备完成")
        print_section_header("", width=70)


def main():
    """
    主函数：执行向量化处理
    """
    # 获取收集报告路径
    collection_report = "logs/collection_report_latest.json"

    # 如果没有指定的最新报告，查找最新的收集报告
    if not os.path.exists(collection_report):
        logs_dir = "logs"
        if os.path.exists(logs_dir):
            reports = [f for f in os.listdir(logs_dir) if f.startswith("collection_report") and f.endswith(".json")]
            if reports:
                reports.sort(reverse=True)
                collection_report = os.path.join(logs_dir, reports[0])

    if not os.path.exists(collection_report):
        logger.error(f"❌ 找不到收集报告: {collection_report}")
        return {
            "success": False,
            "error": "找不到收集报告"
        }

    try:
        # 创建向量化处理器
        vectorizer = GlobalNotesVectorizer(collection_report, output_dir="logs")

        # 加载收集报告
        if not vectorizer.load_collection_report():
            return {
                "success": False,
                "error": "加载收集报告失败"
            }

        # 执行向量化
        success = vectorizer.vectorize_all()

        # 保存报告
        report_path = vectorizer.save_report()

        # 打印摘要
        vectorizer.print_summary()

        return {
            "success": success,
            "files_processed": vectorizer.stats["successfully_processed"],
            "total_vectors": vectorizer.stats["total_vectors_stored"],
            "report_path": report_path,
            "stats": vectorizer.stats
        }

    except Exception as e:
        logger.error(f"❌ 向量化失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    result = main()

    if result.get("success"):
        print(f"\n🎉 向量化成功！")
        print(f"   处理文件: {result['files_processed']}")
        print(f"   生成向量: {result['total_vectors']}")
        print(f"   报告位置: {result['report_path']}")
        sys.exit(0)
    else:
        print(f"\n❌ 向量化失败: {result.get('error')}")
        sys.exit(1)
