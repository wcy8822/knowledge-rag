"""
本地知识库全量向量化自动化系统 - 检索模块
版本: v1.0
日期: 2026-03-01

本模块实现：
- 关键词检索
- 向量相似度检索
- 混合检索
- 结果排序和过滤
"""

import re
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field

from .base import VectorStore, SearchResult, VectorChunk
from .config import Config
from .utils import (
    setup_logger,
    cosine_similarity,
    md5_vector,
    sanitize_text,
)


@dataclass
class RetrievalResult:
    """检索结果"""
    type: str  # 'keyword', 'vector', 'hybrid'
    query: str
    results: List[SearchResult] = field(default_factory=list)
    total: int = 0
    query_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type,
            "query": self.query,
            "total": self.total,
            "query_time": self.query_time,
            "results": [r.to_dict() for r in self.results]
        }


class Retriever:
    """文档检索器"""

    def __init__(self, store: VectorStore, config: Config):
        """
        初始化检索器

        Args:
            store: 向量存储实例
            config: 配置对象
        """
        self.store = store
        self.config = config
        self.logger = setup_logger("retriever", config.log_dir, config.log_level)

        # 检索权重
        self.keyword_weight = config.get("retrieval.hybrid_weights.keyword", 0.3)
        self.vector_weight = config.get("retrieval.hybrid_weights.vector", 0.7)

        # 预览长度
        self.preview_length = config.get("retrieval.preview_length", 200)

        # 脱敏模式
        self.sanitize_mode = config.get("retrieval.sanitization_mode", "moderate")

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        search_type: str = "hybrid",
        filters: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """
        搜索文档

        Args:
            query: 查询文本
            top_k: 返回结果数
            search_type: 搜索类型 ('keyword', 'vector', 'hybrid')
            filters: 过滤条件

        Returns:
            检索结果
        """
        from time import time

        start_time = time()
        top_k = top_k or self.config.default_top_k
        top_k = min(top_k, self.config.max_top_k)

        if search_type == "keyword":
            results = self.keyword_search(query, top_k, filters)
        elif search_type == "vector":
            results = self.vector_search(query, top_k, filters)
        elif search_type == "hybrid":
            results = self.hybrid_search(query, top_k, filters)
        else:
            raise ValueError(f"不支持的搜索类型: {search_type}")

        query_time = time() - start_time

        return RetrievalResult(
            type=search_type,
            query=query,
            results=results,
            total=len(results),
            query_time=query_time
        )

    def keyword_search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        关键词检索

        Args:
            query: 查询文本
            top_k: 返回结果数
            filters: 过滤条件

        Returns:
            搜索结果列表
        """
        self.logger.debug(f"关键词检索: {query}")

        # 预处理查询
        keywords = self._extract_keywords(query)

        if not keywords:
            return []

        # 获取所有元数据
        all_metadata = self.store.metadata_store._metadata

        # 计算匹配分数
        scored_results = []

        for vector_id, metadata in all_metadata.items():
            # 应用过滤条件
            if filters and not self._match_filters(metadata, filters):
                continue

            # 计算匹配分数
            score = 0.0

            chunk_text = metadata.get("chunk_text", "")
            file_name = metadata.get("file_name", "")
            category = metadata.get("category", "")

            for keyword in keywords:
                if keyword.lower() in chunk_text.lower():
                    score += 1.0
                if keyword.lower() in file_name.lower():
                    score += 0.5
                if keyword.lower() in category.lower():
                    score += 0.3

            if score > 0:
                # 脱敏处理
                text_preview = self._get_preview(chunk_text)
                sanitized_text = sanitize_text(text_preview, mode=self.sanitize_mode)

                scored_results.append({
                    "id": vector_id,
                    "file_path": metadata["file_path"],
                    "file_name": file_name,
                    "category": category,
                    "chunk_index": metadata.get("chunk_index", 0),
                    "chunk_text": sanitized_text,
                    "similarity": min(score / len(keywords), 1.0),  # 归一化
                    "metadata": metadata.get("metadata", {}),
                    "_score": score
                })

        # 按分数排序
        scored_results.sort(key=lambda x: x["_score"], reverse=True)

        # 取前 top_k 个结果
        results = []
        for item in scored_results[:top_k]:
            del item["_score"]  # 移除内部字段
            results.append(SearchResult(**item))

        self.logger.info(f"关键词检索完成: 找到 {len(results)} 个结果")
        return results

    def vector_search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        向量相似度检索

        Args:
            query: 查询文本
            top_k: 返回结果数
            filters: 过滤条件

        Returns:
            搜索结果列表
        """
        self.logger.debug(f"向量检索: {query}")

        # 向量化查询
        query_vector = md5_vector(query, dim=self.config.vector_dim)

        # 搜索
        results = self.store.search(query_vector, top_k, filters)

        # 处理预览
        for result in results:
            result.chunk_text = self._get_preview(result.chunk_text)

        self.logger.info(f"向量检索完成: 找到 {len(results)} 个结果")
        return results

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        混合检索（关键词 + 向量）

        Args:
            query: 查询文本
            top_k: 返回结果数
            filters: 过滤条件

        Returns:
            搜索结果列表
        """
        self.logger.debug(f"混合检索: {query}")

        # 分别进行关键词和向量检索
        keyword_results = self.keyword_search(query, top_k * 2, filters)
        vector_results = self.vector_search(query, top_k * 2, filters)

        # 合并结果
        merged: Dict[str, SearchResult] = {}

        # 添加关键词结果
        for result in keyword_results:
            merged[result.id] = result

        # 合并向量结果
        for result in vector_results:
            if result.id in merged:
                # 已存在，取相似度更高的
                if result.similarity > merged[result.id].similarity:
                    merged[result.id] = result
            else:
                merged[result.id] = result

        # 重新计算混合分数
        keywords = self._extract_keywords(query)

        for result in merged.values():
            # 计算关键词匹配分数
            keyword_score = 0.0
            for keyword in keywords:
                if keyword.lower() in result.chunk_text.lower():
                    keyword_score += 1.0
            keyword_score = min(keyword_score / len(keywords), 1.0) if keywords else 0

            # 计算向量相似度分数
            vector_score = result.similarity

            # 混合分数
            result.similarity = (
                self.keyword_weight * keyword_score +
                self.vector_weight * vector_score
            )

        # 排序
        sorted_results = sorted(
            merged.values(),
            key=lambda x: x.similarity,
            reverse=True
        )

        self.logger.info(f"混合检索完成: 找到 {len(sorted_results)} 个结果")
        return sorted_results[:top_k]

    def search_by_file(
        self,
        file_path: str,
        top_k: Optional[int] = None
    ) -> List[SearchResult]:
        """
        按文件搜索

        Args:
            file_path: 文件路径
            top_k: 返回结果数

        Returns:
            搜索结果列表
        """
        # 获取文件的所有向量元数据
        metadata_list = self.store.metadata_store.get_vectors_by_file(file_path)

        results = []
        for metadata in metadata_list:
            if metadata:
                text_preview = self._get_preview(metadata["chunk_text"])
                sanitized_text = sanitize_text(text_preview, mode=self.sanitize_mode)

                results.append(SearchResult(
                    id=metadata["id"],
                    file_path=metadata["file_path"],
                    file_name=metadata["file_name"],
                    category=metadata["category"],
                    chunk_index=metadata["chunk_index"],
                    chunk_text=sanitized_text,
                    similarity=1.0,  # 同一文件视为完全相关
                    metadata=metadata.get("metadata", {})
                ))

        if top_k:
            results = results[:top_k]

        return results

    def _extract_keywords(self, text: str) -> List[str]:
        """
        提取关键词

        Args:
            text: 输入文本

        Returns:
            关键词列表
        """
        # 移除标点符号
        text = re.sub(r'[^\w\s]', ' ', text)

        # 分词
        words = text.split()

        # 过滤停用词（简单版）
        stop_words = {
            '的', '了', '和', '是', '在', '我', '有', '就', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
            '你', '会', '着', '没有', '看', '好', '自己', '这',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'should', 'can', 'could', 'may', 'might', 'must', 'to', 'of',
            'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
            'through', 'during', 'before', 'after', 'above', 'below'
        }

        keywords = [word for word in words if word.lower() not in stop_words and len(word) > 1]

        return keywords

    def _get_preview(self, text: str, max_length: Optional[int] = None) -> str:
        """
        获取文本预览

        Args:
            text: 输入文本
            max_length: 最大长度

        Returns:
            预览文本
        """
        max_length = max_length or self.preview_length

        if len(text) <= max_length:
            return text

        return text[:max_length] + "..."

    def _match_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """
        检查元数据是否匹配过滤条件

        Args:
            metadata: 元数据
            filters: 过滤条件

        Returns:
            是否匹配
        """
        for key, value in filters.items():
            if key not in metadata:
                return False
            if metadata[key] != value:
                # 支持模糊匹配
                if isinstance(value, str) and isinstance(metadata[key], str):
                    if value.lower() not in metadata[key].lower():
                        return False
                else:
                    return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        获取检索器统计信息

        Returns:
            统计信息字典
        """
        return {
            "keyword_weight": self.keyword_weight,
            "vector_weight": self.vector_weight,
            "sanitize_mode": self.sanitize_mode,
            "store_stats": self.store.get_stats()
        }


# 快捷函数
def quick_search(query: str, config: Config) -> RetrievalResult:
    """
    快速搜索

    Args:
        query: 查询文本
        config: 配置对象

    Returns:
        检索结果
    """
    from .storage import create_vector_store

    store = create_vector_store(config)
    retriever = Retriever(store, config)

    return retriever.search(query)


__all__ = [
    # 数据类
    "RetrievalResult",
    # 检索器
    "Retriever",
    # 快捷函数
    "quick_search",
]
