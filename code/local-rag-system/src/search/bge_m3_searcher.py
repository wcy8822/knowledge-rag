#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BGE-M3 搜索器 - 支持高精度 1024D 向量搜索和混合搜索
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    import chromadb
except ImportError:
    logger.error("缺少依赖: sentence-transformers 或 chromadb")
    raise


class BGE_M3_Searcher:
    """BGE-M3 向量搜索器 - 支持混合搜索和结果重排"""

    def __init__(
        self,
        model_path: str = "/Users/didi/models/bge-m3/BAAI/bge-m3",
        db_path: str = "/Users/didi/Downloads/panth/data/chroma",
        collection_name: str = "bge-m3-documents"
    ):
        """
        初始化搜索器

        Args:
            model_path: BGE-M3 模型本地路径
            db_path: ChromaDB 数据库路径
            collection_name: ChromaDB collection 名称
        """
        self.model_path = model_path
        self.db_path = db_path
        self.collection_name = collection_name

        self.model: Optional[SentenceTransformer] = None
        self.client: Optional[chromadb.PersistentClient] = None
        self.collection: Optional[chromadb.Collection] = None

        # 搜索统计
        self.search_stats = {
            "total_searches": 0,
            "avg_response_time_ms": 0,
            "total_response_time_ms": 0
        }

        self._init()

    def _init(self) -> bool:
        """初始化模型和数据库"""
        try:
            logger.info("📦 初始化 BGE-M3 搜索器...")

            # 加载模型
            logger.info(f"加载模型: {self.model_path}")
            self.model = SentenceTransformer(self.model_path)
            logger.info("✅ BGE-M3 模型加载成功")

            # 连接数据库
            logger.info(f"连接 ChromaDB: {self.db_path}")
            self.client = chromadb.PersistentClient(path=self.db_path)

            # 获取 collection
            self.collection = self.client.get_collection(name=self.collection_name)
            logger.info(f"✅ 连接到 Collection: {self.collection_name}")

            # 验证集合存在
            data = self.collection.get(limit=1)
            doc_count = len(data['ids']) if data and 'ids' in data else 0
            logger.info(f"✓ 集合中包含 {doc_count} 个文档")

            return True

        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            return False

    def search(
        self,
        query: str,
        top_k: int = 5,
        use_reranking: bool = True
    ) -> List[Dict[str, Any]]:
        """
        搜索知识库

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            use_reranking: 是否使用重排

        Returns:
            搜索结果列表
        """
        if not self.model or not self.collection:
            logger.error("❌ 搜索器未初始化")
            return []

        try:
            import time
            start_time = time.time()

            # 1. 向量搜索
            query_embedding = self.model.encode(query)
            vector_results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=min(top_k * 2, 20)  # 获取更多候选用于重排
            )

            # 2. 重排（如果启用）
            if use_reranking and len(vector_results['ids'][0]) > 0:
                results = self._rerank_results(query, vector_results, top_k)
            else:
                results = self._format_results(vector_results, top_k)

            # 3. 记录统计信息
            elapsed_ms = (time.time() - start_time) * 1000
            self.search_stats["total_searches"] += 1
            self.search_stats["total_response_time_ms"] += elapsed_ms
            self.search_stats["avg_response_time_ms"] = (
                self.search_stats["total_response_time_ms"] /
                self.search_stats["total_searches"]
            )

            logger.info(
                f"✓ 搜索完成: '{query}' (耗时: {elapsed_ms:.1f}ms, "
                f"结果数: {len(results)})"
            )

            return results

        except Exception as e:
            logger.error(f"❌ 搜索失败: {e}")
            return []

    def _format_results(
        self,
        chroma_results: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """格式化 ChromaDB 搜索结果"""
        results = []

        ids = chroma_results.get('ids', [[]])[0]
        documents = chroma_results.get('documents', [[]])[0]
        metadatas = chroma_results.get('metadatas', [[]])[0]
        distances = chroma_results.get('distances', [[]])[0]

        for i, (doc_id, document, metadata, distance) in enumerate(
            zip(ids[:top_k], documents[:top_k], metadatas[:top_k], distances[:top_k])
        ):
            # ChromaDB 返回的距离是 cosine 距离，转换为相似度
            similarity = 1 - distance

            result = {
                "rank": i + 1,
                "document_id": doc_id,
                "content": document,
                "relevance_score": similarity,
                "file_path": metadata.get('file_path', 'unknown'),
                "file_name": metadata.get('file_name', 'unknown'),
                "search_method": "vector"
            }
            results.append(result)

        return results

    def _rerank_results(
        self,
        query: str,
        chroma_results: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """重排搜索结果"""
        # 获取候选结果
        candidates = self._format_results(chroma_results, len(chroma_results['ids'][0]))

        if not candidates:
            return []

        try:
            # 使用 BGE-M3 的重排能力计算查询和文档的相似度
            query_embedding = self.model.encode(query)

            # 为每个候选重新计算相似度
            for candidate in candidates:
                doc_embedding = self.model.encode(candidate['content'][:500])
                similarity = self._cosine_similarity(query_embedding, doc_embedding)
                candidate['relevance_score'] = similarity
                candidate['search_method'] = "vector_reranked"

            # 按相似度排序
            candidates.sort(key=lambda x: x['relevance_score'], reverse=True)

            # 返回前 k 个结果，更新排名
            for i, result in enumerate(candidates[:top_k]):
                result['rank'] = i + 1

            return candidates[:top_k]

        except Exception as e:
            logger.warning(f"⚠️  重排失败，使用原始结果: {e}")
            return candidates[:top_k]

    @staticmethod
    def _cosine_similarity(vec1, vec2) -> float:
        """计算向量余弦相似度"""
        import numpy as np

        # 归一化
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-10)
        vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-10)

        # 计算余弦相似度
        return float(np.dot(vec1_norm, vec2_norm))

    def get_stats(self) -> Dict[str, Any]:
        """获取搜索统计信息"""
        try:
            if not self.collection:
                return {"status": "error", "message": "Collection not initialized"}

            data = self.collection.get(limit=1)
            doc_count = len(data['ids']) if data and 'ids' in data else 0

            return {
                "status": "ready",
                "model": "BAAI/bge-m3",
                "vector_dimension": 1024,
                "database": self.db_path,
                "collection": self.collection_name,
                "document_count": doc_count,
                "search_statistics": {
                    "total_searches": self.search_stats["total_searches"],
                    "avg_response_time_ms": round(
                        self.search_stats["avg_response_time_ms"], 2
                    )
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {"status": "error", "message": str(e)}

    def health_check(self) -> bool:
        """健康检查"""
        try:
            if not self.model or not self.collection:
                return False

            # 测试搜索
            results = self.search("test", top_k=1)
            return len(results) > 0
        except Exception as e:
            logger.error(f"❌ 健康检查失败: {e}")
            return False


# 便利函数
def create_searcher(
    model_path: str = "/Users/didi/models/bge-m3/BAAI/bge-m3",
    db_path: str = "/Users/didi/Downloads/panth/data/chroma",
    collection_name: str = "bge-m3-documents"
) -> Optional[BGE_M3_Searcher]:
    """创建搜索器实例"""
    searcher = BGE_M3_Searcher(
        model_path=model_path,
        db_path=db_path,
        collection_name=collection_name
    )

    if searcher._init():
        return searcher

    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # 测试
    print("测试 BGE-M3 搜索器...")
    searcher = create_searcher()

    if searcher:
        # 测试搜索
        results = searcher.search("项目管理", top_k=3)
        print(f"\n搜索结果 ({len(results)} 个):")
        for r in results:
            print(f"  #{r['rank']}: {r['file_name']} (相关性: {r['relevance_score']:.2%})")

        # 获取统计
        stats = searcher.get_stats()
        print(f"\n统计信息: {json.dumps(stats, ensure_ascii=False, indent=2)}")
    else:
        print("❌ 搜索器初始化失败")
