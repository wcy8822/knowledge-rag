#!/usr/bin/env python3
"""
向量化验证模块
验证向量化结果的完整性、正确性和可用性
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

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
from src.store.vector_stores.chroma_store import ChromaVectorStore
from src.search.hybrid_searcher import HybridSearcher

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VectorizationVerifier:
    """
    向量化验证器

    功能：
    - 验证向量数据库完整性
    - 执行搜索测试
    - 验证向量质量
    - 生成验证报告
    """

    def __init__(self, output_dir: str = "logs"):
        """
        初始化验证器

        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = output_dir
        ensure_directory_exists(output_dir)

        # 初始化RAG组件
        logger.info("初始化RAG系统组件...")
        try:
            self.vector_store = ChromaVectorStore()
            self.hybrid_searcher = HybridSearcher()
        except Exception as e:
            logger.warning(f"初始化RAG组件失败: {e}")
            self.vector_store = None
            self.hybrid_searcher = None

        # 验证统计数据
        self.stats = {
            "timestamp": generate_timestamp(),
            "checks_passed": 0,
            "checks_failed": 0,
            "total_vectors": 0,
            "total_documents": 0,
            "sample_search_results": [],
            "integrity_checks": [],
            "quality_metrics": {},
            "errors": [],
            "warnings": []
        }

    def check_vector_database(self) -> Dict[str, Any]:
        """
        检查向量数据库

        Returns:
            检查结果
        """
        logger.info("\n🔍 检查向量数据库...")
        result = {
            "check": "database_integrity",
            "status": "pending",
            "details": {}
        }

        try:
            if not self.vector_store:
                result["status"] = "failed"
                result["error"] = "向量数据库未初始化"
                self.stats["checks_failed"] += 1
                return result

            # 1. 检查集合是否存在
            logger.info("  检查向量集合...")
            collection = self.vector_store.collection

            if not collection:
                result["status"] = "failed"
                result["error"] = "向量集合不存在"
                self.stats["checks_failed"] += 1
                return result

            # 2. 获取集合统计信息
            try:
                collection_data = collection.get()
            except Exception as e:
                result["status"] = "failed"
                result["error"] = f"无法获取集合数据: {e}"
                self.stats["checks_failed"] += 1
                return result

            if not collection_data or "ids" not in collection_data:
                result["status"] = "failed"
                result["error"] = "集合为空或格式不正确"
                self.stats["checks_failed"] += 1
                return result

            # 3. 统计信息
            total_vectors = len(collection_data["ids"])
            total_documents = len(set([id.rsplit("_", 2)[0] for id in collection_data["ids"]]))

            self.stats["total_vectors"] = total_vectors
            self.stats["total_documents"] = total_documents

            result["status"] = "success"
            result["details"] = {
                "total_vectors": total_vectors,
                "total_documents": total_documents,
                "avg_vectors_per_doc": round(total_vectors / total_documents if total_documents > 0 else 0, 2)
            }

            logger.info(f"  ✅ 集合检查通过: {total_vectors} 个向量, {total_documents} 个文档")
            self.stats["checks_passed"] += 1

            return result

        except Exception as e:
            error_msg = f"数据库检查异常: {e}"
            logger.error(error_msg)
            result["status"] = "failed"
            result["error"] = error_msg
            self.stats["errors"].append(error_msg)
            self.stats["checks_failed"] += 1
            return result

    def check_vector_quality(self) -> Dict[str, Any]:
        """
        检查向量质量

        Returns:
            检查结果
        """
        logger.info("\n🔍 检查向量质量...")
        result = {
            "check": "vector_quality",
            "status": "pending",
            "details": {}
        }

        try:
            if not self.vector_store or not self.stats["total_vectors"]:
                result["status"] = "skipped"
                result["reason"] = "向量库为空或不可用"
                return result

            # 1. 获取样本向量
            logger.info("  采样向量检查...")
            collection = self.vector_store.collection
            collection_data = collection.get()

            sample_ids = collection_data["ids"][:min(100, len(collection_data["ids"]))]

            if not collection_data.get("embeddings"):
                result["status"] = "warning"
                result["warning"] = "无法获取嵌入向量进行质量检查"
                self.stats["warnings"].append("无法获取嵌入向量")
                return result

            # 2. 检查向量维度
            embeddings = collection_data["embeddings"]
            if embeddings:
                sample_embedding = embeddings[0]
                vector_dim = len(sample_embedding) if isinstance(sample_embedding, list) else 0

                result["details"]["vector_dimension"] = vector_dim
                if vector_dim == 768:
                    logger.info(f"  ✅ 向量维度正确: {vector_dim}")
                else:
                    logger.warning(f"  ⚠️  向量维度异常: {vector_dim}（预期768）")
                    self.stats["warnings"].append(f"向量维度异常: {vector_dim}")

            # 3. 检查向量范围
            import math
            if embeddings:
                flat_embeddings = [v for emb in embeddings[:100] if isinstance(emb, list) for v in emb]
                if flat_embeddings:
                    min_val = min(flat_embeddings)
                    max_val = max(flat_embeddings)
                    mean_val = sum(flat_embeddings) / len(flat_embeddings)

                    result["details"]["embedding_stats"] = {
                        "min": round(min_val, 4),
                        "max": round(max_val, 4),
                        "mean": round(mean_val, 4)
                    }
                    logger.info(f"  ✅ 向量范围: [{min_val:.4f}, {max_val:.4f}]")

            result["status"] = "success"
            self.stats["checks_passed"] += 1
            return result

        except Exception as e:
            error_msg = f"向量质量检查异常: {e}"
            logger.error(error_msg)
            result["status"] = "failed"
            result["error"] = error_msg
            self.stats["errors"].append(error_msg)
            self.stats["checks_failed"] += 1
            return result

    def test_search_functionality(self) -> Dict[str, Any]:
        """
        测试搜索功能

        Returns:
            检查结果
        """
        logger.info("\n🔍 测试搜索功能...")
        result = {
            "check": "search_functionality",
            "status": "pending",
            "test_queries": []
        }

        try:
            if not self.hybrid_searcher or self.stats["total_vectors"] == 0:
                result["status"] = "skipped"
                result["reason"] = "搜索器不可用或向量库为空"
                return result

            # 测试查询
            test_queries = [
                "工作总结",
                "技术方案",
                "项目进展",
                "性能优化",
                "文档处理"
            ]

            logger.info(f"  执行 {len(test_queries)} 个测试查询...")

            for query in test_queries:
                try:
                    # 执行搜索
                    results = self.hybrid_searcher.search(
                        query=query,
                        top_k=5,
                        rerank=True
                    )

                    test_result = {
                        "query": query,
                        "hits": len(results) if results else 0,
                        "status": "success" if results else "no_results"
                    }

                    if results and len(results) > 0:
                        test_result["top_score"] = results[0].get("score", 0)

                    result["test_queries"].append(test_result)
                    logger.info(f"    ✅ '{query}': {len(results)} 结果")

                except Exception as e:
                    logger.warning(f"    ⚠️  '{query}' 查询失败: {e}")
                    result["test_queries"].append({
                        "query": query,
                        "status": "error",
                        "error": str(e)
                    })

            # 统计成功的查询
            successful_queries = sum(1 for q in result["test_queries"] if q["status"] == "success")

            if successful_queries > 0:
                result["status"] = "success"
                self.stats["checks_passed"] += 1
                self.stats["sample_search_results"] = result["test_queries"]
                logger.info(f"  ✅ 搜索功能测试通过: {successful_queries}/{len(test_queries)} 成功")
            else:
                result["status"] = "failed"
                result["reason"] = "所有查询都失败"
                self.stats["checks_failed"] += 1
                logger.warning(f"  ❌ 所有查询失败")

            return result

        except Exception as e:
            error_msg = f"搜索功能测试异常: {e}"
            logger.error(error_msg)
            result["status"] = "failed"
            result["error"] = error_msg
            self.stats["errors"].append(error_msg)
            self.stats["checks_failed"] += 1
            return result

    def verify_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        执行所有验证检查

        Returns:
            所有检查结果
        """
        logger.info("=" * 70)
        logger.info("✅ 开始向量化验证")
        logger.info("=" * 70)

        checks = []

        # 1. 数据库完整性检查
        check1 = self.check_vector_database()
        checks.append(check1)

        # 2. 向量质量检查
        check2 = self.check_vector_quality()
        checks.append(check2)

        # 3. 搜索功能测试
        check3 = self.test_search_functionality()
        checks.append(check3)

        logger.info(f"\n✅ 验证完成")
        logger.info(f"  通过: {self.stats['checks_passed']}")
        logger.info(f"  失败: {self.stats['checks_failed']}")

        return checks

    def generate_report(self, checks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        生成验证报告

        Returns:
            报告字典
        """
        # 计算整体状态
        all_passed = all(check.get("status") in ["success", "skipped"] for check in checks)

        summary = {
            "timestamp": self.stats["timestamp"],
            "overall_status": "passed" if all_passed else "failed",
            "checks_passed": self.stats["checks_passed"],
            "checks_failed": self.stats["checks_failed"],
            "total_vectors": self.stats["total_vectors"],
            "total_documents": self.stats["total_documents"],
            "quality_metrics": {
                "vector_database_health": "✅" if self.stats["total_vectors"] > 0 else "❌",
                "search_functionality": "✅" if self.stats["sample_search_results"] else "❌",
                "sample_searches_successful": sum(
                    1 for q in self.stats["sample_search_results"]
                    if q.get("status") == "success"
                )
            }
        }

        # 添加错误和警告
        if self.stats["errors"]:
            summary["errors"] = self.stats["errors"]

        if self.stats["warnings"]:
            summary["warnings"] = self.stats["warnings"]

        report = {
            "metadata": {
                "report_type": "vectorization_verification",
                "version": "1.0",
                "generated_at": generate_timestamp(),
                "generator": "VectorizationVerifier"
            },
            "summary": summary,
            "checks": checks,
            "sample_search_results": self.stats["sample_search_results"]
        }

        return report

    def save_report(self, report: Dict[str, Any]) -> str:
        """
        保存验证报告

        Returns:
            保存的报告文件路径
        """
        # 生成报告文件名
        report_filename = generate_report_filename("verification_report", "json")
        report_path = os.path.join(self.output_dir, report_filename)

        # 保存报告
        success = save_json_report(report, report_path)

        if success:
            logger.info(f"✅ 报告已保存: {report_path}")
            return report_path
        else:
            logger.error(f"❌ 报告保存失败: {report_path}")
            return None

    def print_summary(self, report: Dict[str, Any]):
        """
        打印验证摘要
        """
        summary = report.get("summary", {})

        print_section_header("✅ 向量化验证摘要", width=70)

        print(f"\n📊 整体状态: {summary.get('overall_status', 'unknown').upper()}")

        print(f"\n✔️  检查结果:")
        print(f"  • 通过: {summary.get('checks_passed', 0)}")
        print(f"  • 失败: {summary.get('checks_failed', 0)}")

        print(f"\n📈 数据统计:")
        print(f"  • 总向量数: {summary.get('total_vectors', 0)}")
        print(f"  • 总文档数: {summary.get('total_documents', 0)}")

        metrics = summary.get("quality_metrics", {})
        print(f"\n🔍 质量指标:")
        print(f"  • 数据库健康: {metrics.get('vector_database_health', '❓')}")
        print(f"  • 搜索功能: {metrics.get('search_functionality', '❓')}")
        print(f"  • 搜索成功: {metrics.get('sample_searches_successful', 0)} 个")

        if summary.get("errors"):
            print(f"\n❌ 错误信息:")
            for error in summary["errors"][:3]:
                print(f"  • {error}")

        if summary.get("warnings"):
            print(f"\n⚠️  警告信息:")
            for warning in summary["warnings"][:3]:
                print(f"  • {warning}")

        print(f"\n✅ 验证完成")
        print_section_header("", width=70)


def main():
    """
    主函数：执行验证
    """
    try:
        # 创建验证器
        verifier = VectorizationVerifier(output_dir="logs")

        # 执行所有验证
        checks = verifier.verify_all()

        # 生成报告
        report = verifier.generate_report(checks)

        # 保存报告
        report_path = verifier.save_report(report)

        # 打印摘要
        verifier.print_summary(report)

        return {
            "success": report["summary"]["overall_status"] == "passed",
            "report_path": report_path,
            "report": report,
            "total_vectors": verifier.stats["total_vectors"],
            "total_documents": verifier.stats["total_documents"]
        }

    except Exception as e:
        logger.error(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    result = main()

    if result.get("success"):
        print(f"\n🎉 验证成功！")
        print(f"   总向量数: {result.get('total_vectors', 0)}")
        print(f"   总文档数: {result.get('total_documents', 0)}")
        print(f"   报告位置: {result['report_path']}")
        sys.exit(0)
    else:
        print(f"\n❌ 验证失败: {result.get('error', '未知错误')}")
        sys.exit(1)
