#!/usr/bin/env python3
"""
Local RAG 系统统一接口

这个模块提供了融合后的统一入口。
对外暴露一个简洁的 LocalRAGSystem 类，隐藏所有的复杂性。

使用示例：
    system = LocalRAGSystem(version="1.1.0")

    # 完整的向量化流程
    system.run_complete_pipeline()

    # 搜索
    results = system.search("工作总结")

    # 获取统计信息
    stats = system.get_stats()
"""

import os
import sys
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 导入原有RAG系统组件
from src.store.embedding_service import EmbeddingService
from src.store.vector_stores.chroma_store import ChromaVectorStore
from src.search.hybrid_searcher import HybridSearcher

# 导入新增向量化模块
from src.vectorization.collect_notes import NotesCollector
from src.vectorization.vectorize_global_notes import GlobalNotesVectorizer
from src.vectorization.verify_vectorization import VectorizationVerifier
from src.vectorization.utils import generate_timestamp

# 导入版本管理
from src.integration.version import VersionManager
from src.integration.config import ConfigManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LocalRAGSystem:
    """
    融合后的本地RAG系统

    整合了以下组件：
    - 原有RAG系统: 向量嵌入、向量存储、混合检索、API服务
    - 新增模块: 笔记收集、批量向量化、质量验证
    - 管理系统: 版本管理、配置管理、状态追踪

    这是用户与整个系统交互的唯一入口。
    """

    def __init__(self, version: str = "1.1.0", config_path: Optional[str] = None):
        """
        初始化融合后的RAG系统

        Args:
            version: 系统版本号
            config_path: 配置文件路径
        """
        self.version = version
        self.startup_time = generate_timestamp()
        self.config_manager = ConfigManager(config_path)

        logger.info(f"初始化 Local RAG System v{version}")

        # 初始化原有RAG系统的核心组件
        logger.info("  初始化向量存储...")
        self.embedding_service = EmbeddingService()
        self.vector_store = ChromaVectorStore()
        self.searcher = HybridSearcher()

        # 初始化新增的向量化模块
        logger.info("  初始化向量化模块...")
        self.collector = NotesCollector()
        self.vectorizer = GlobalNotesVectorizer()
        self.verifier = VectorizationVerifier()

        # 版本管理器
        self.version_manager = VersionManager()

        # 执行状态
        self.state = {
            "initialized_at": self.startup_time,
            "version": version,
            "components_ready": True,
            "last_vectorization": None,
            "last_search": None,
        }

        logger.info(f"✅ Local RAG System v{version} 初始化完成")

    # ==================== 完整流程 ====================

    def run_complete_pipeline(self, output_dir: str = "logs") -> Dict[str, Any]:
        """
        执行完整的向量化流程

        阶段1: 收集笔记文件
        阶段2: 向量化处理
        阶段3: 验证结果

        Args:
            output_dir: 输出目录

        Returns:
            执行结果字典
        """
        logger.info("=" * 70)
        logger.info("🚀 开始完整向量化流程")
        logger.info("=" * 70)

        result = {
            "success": False,
            "version": self.version,
            "timestamp": generate_timestamp(),
            "stages": {}
        }

        try:
            # 阶段1: 收集
            logger.info("\n📋 阶段1: 收集笔记文件")
            collect_result = self.collect_notes(output_dir)
            result["stages"]["collection"] = collect_result

            if not collect_result["success"]:
                logger.error("❌ 收集阶段失败")
                return result

            # 阶段2: 向量化
            logger.info("\n🔮 阶段2: 向量化处理")
            collection_report = collect_result.get("report_path")
            vectorize_result = self.vectorize_notes(collection_report, output_dir)
            result["stages"]["vectorization"] = vectorize_result

            if not vectorize_result["success"]:
                logger.error("❌ 向量化阶段失败")
                return result

            # 阶段3: 验证
            logger.info("\n✅ 阶段3: 验证结果")
            verify_result = self.verify_notes(output_dir)
            result["stages"]["verification"] = verify_result

            # 更新状态
            self.state["last_vectorization"] = generate_timestamp()
            result["success"] = verify_result.get("success", False)

            logger.info("\n" + "=" * 70)
            logger.info("🎉 完整流程执行完成")
            logger.info("=" * 70)

            return result

        except Exception as e:
            logger.error(f"❌ 流程执行失败: {e}")
            import traceback
            traceback.print_exc()
            return result

    # ==================== 阶段1: 收集 ====================

    def collect_notes(self, output_dir: str = "logs") -> Dict[str, Any]:
        """
        收集全局笔记文件

        Returns:
            收集结果
        """
        try:
            files = self.collector.collect_all_notes()
            report_path = self.collector.save_report()
            self.collector.print_summary()

            return {
                "success": True,
                "files_collected": len(files),
                "report_path": report_path
            }
        except Exception as e:
            logger.error(f"❌ 收集失败: {e}")
            return {"success": False, "error": str(e)}

    # ==================== 阶段2: 向量化 ====================

    def vectorize_notes(self, collection_report: str, output_dir: str = "logs") -> Dict[str, Any]:
        """
        批量向量化笔记

        Args:
            collection_report: 收集报告路径
            output_dir: 输出目录

        Returns:
            向量化结果
        """
        try:
            # 加载收集报告
            if not self.vectorizer.load_collection_report(collection_report):
                return {"success": False, "error": "无法加载收集报告"}

            # 执行向量化
            success = self.vectorizer.vectorize_all()
            report_path = self.vectorizer.save_report()
            self.vectorizer.print_summary()

            return {
                "success": success,
                "files_processed": self.vectorizer.stats["successfully_processed"],
                "vectors_generated": self.vectorizer.stats["total_vectors_generated"],
                "report_path": report_path
            }
        except Exception as e:
            logger.error(f"❌ 向量化失败: {e}")
            return {"success": False, "error": str(e)}

    # ==================== 阶段3: 验证 ====================

    def verify_notes(self, output_dir: str = "logs") -> Dict[str, Any]:
        """
        验证向量化结果

        Returns:
            验证结果
        """
        try:
            checks = self.verifier.verify_all()
            report = self.verifier.generate_report(checks)
            report_path = self.verifier.save_report(report)
            self.verifier.print_summary(report)

            return {
                "success": report["summary"]["overall_status"] == "passed",
                "checks_passed": report["summary"]["checks_passed"],
                "total_vectors": report["summary"]["total_vectors"],
                "report_path": report_path
            }
        except Exception as e:
            logger.error(f"❌ 验证失败: {e}")
            return {"success": False, "error": str(e)}

    # ==================== 搜索功能 ====================

    def search(
        self,
        query: str,
        top_k: int = 5,
        rerank: bool = True,
        return_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        搜索笔记

        Args:
            query: 查询文本
            top_k: 返回结果数量
            rerank: 是否使用重排序
            return_metadata: 是否返回元数据

        Returns:
            搜索结果列表
        """
        try:
            self.state["last_search"] = generate_timestamp()

            results = self.searcher.search(
                query=query,
                top_k=top_k,
                rerank=rerank
            )

            if return_metadata:
                return results
            else:
                return [{
                    "text": r.get("text", ""),
                    "score": r.get("score", 0)
                } for r in results]

        except Exception as e:
            logger.error(f"❌ 搜索失败: {e}")
            return []

    # ==================== 系统信息 ====================

    def get_stats(self) -> Dict[str, Any]:
        """
        获取系统统计信息

        Returns:
            统计信息字典
        """
        try:
            collection_data = self.vector_store.collection.get()
            total_vectors = len(collection_data["ids"]) if collection_data else 0
            total_docs = len(set([
                id.rsplit("_", 2)[0]
                for id in (collection_data["ids"] if collection_data else [])
            ]))

            return {
                "version": self.version,
                "initialized_at": self.state["initialized_at"],
                "last_vectorization": self.state["last_vectorization"],
                "last_search": self.state["last_search"],
                "vector_statistics": {
                    "total_vectors": total_vectors,
                    "total_documents": total_docs,
                    "avg_vectors_per_doc": (
                        round(total_vectors / total_docs if total_docs > 0 else 0, 2)
                    )
                },
                "system_health": {
                    "embedding_service": "✅",
                    "vector_store": "✅",
                    "searcher": "✅"
                }
            }
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {"error": str(e)}

    def get_version_info(self) -> Dict[str, Any]:
        """
        获取版本信息

        Returns:
            版本信息字典
        """
        return self.version_manager.get_version_info(self.version)

    def get_config(self) -> Dict[str, Any]:
        """
        获取系统配置

        Returns:
            配置字典
        """
        return self.config_manager.get_config()

    # ==================== 系统管理 ====================

    def health_check(self) -> bool:
        """
        系统健康检查

        Returns:
            系统是否健康
        """
        try:
            # 检查各个组件
            checks = {
                "embedding_service": bool(self.embedding_service),
                "vector_store": bool(self.vector_store.collection),
                "searcher": bool(self.searcher),
                "collector": bool(self.collector),
                "vectorizer": bool(self.vectorizer),
                "verifier": bool(self.verifier)
            }

            all_healthy = all(checks.values())

            if all_healthy:
                logger.info("✅ 系统健康检查通过")
            else:
                logger.warning(f"⚠️  系统健康检查失败: {checks}")

            return all_healthy

        except Exception as e:
            logger.error(f"❌ 健康检查异常: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        获取系统状态

        Returns:
            系统状态
        """
        return {
            "version": self.version,
            "healthy": self.health_check(),
            "state": self.state,
            "stats": self.get_stats()
        }


def main():
    """
    演示脚本: 展示如何使用统一接口
    """
    # 初始化系统
    system = LocalRAGSystem(version="1.1.0")

    # 运行完整流程
    result = system.run_complete_pipeline()

    # 获取统计信息
    print("\n📊 系统统计信息:")
    print(system.get_stats())

    # 获取版本信息
    print("\n📋 版本信息:")
    print(system.get_version_info())

    # 尝试搜索
    if result["success"]:
        print("\n🔍 测试搜索:")
        results = system.search("工作总结", top_k=3)
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r.get('text', '')[:100]}... (分数: {r.get('score', 0):.2f})")


if __name__ == "__main__":
    main()
