from typing import List, Dict, Any, Optional, Tuple
import logging
import numpy as np
from collections import defaultdict

from .bm25_searcher import bm25_searcher
from .vector_searcher import vector_searcher
from ..models import DocumentChunkWithMetadata
from ..config import config

logger = logging.getLogger(__name__)

class HybridSearcher:
    """混合检索引擎（向量相似度 + BM25）"""
    
    def __init__(self):
        self.config = config.get('retrieval', {}).get('hybrid_search', {})
        self.vector_weight = self.config.get('vector_weight', 0.6)
        self.bm25_weight = self.config.get('bm25_weight', 0.4)
        self.top_k = self.config.get('top_k', 20)
        
        # 初始化子搜索器
        self.vector_searcher = vector_searcher
        self.bm25_searcher = bm25_searcher
        
        self._initialized = False
    
    def initialize(self):
        """初始化混合检索器"""
        try:
            # 初始化向量搜索器
            vector_success = self.vector_searcher.initialize()
            if not vector_success:
                logger.error("Failed to initialize vector searcher")
                return False
            
            # 从元数据存储加载BM25索引
            self.bm25_searcher.load_from_metadata_store()
            
            self._initialized = True
            logger.info("Hybrid searcher initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize hybrid searcher: {e}")
            return False
    
    def search(self, query: str, top_k: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """混合搜索"""
        if not self._initialized:
            logger.warning("Hybrid searcher not initialized")
            return []
        
        if not query.strip():
            logger.warning("Empty query provided")
            return []
        
        try:
            # 并行执行向量搜索和BM25搜索
            vector_results = self._search_vector(query, filters)
            bm25_results = self._search_bm25(query, filters)
            
            # 融合结果
            fused_results = self._fusion_results(vector_results, bm25_results, top_k)
            
            logger.info(f"Hybrid search found {len(fused_results)} results for query: {query[:50]}...")
            return fused_results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []
    
    def _search_vector(self, query: str, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行向量搜索"""
        try:
            vector_results = self.vector_searcher.search(
                query=query,
                top_k=self.top_k,
                filters=filters
            )
            
            # 标准化分数
            for result in vector_results:
                if 'vector_score' in result:
                    result['normalized_vector_score'] = result['vector_score']
                else:
                    result['normalized_vector_score'] = result.get('score', 0.0)
            
            return vector_results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def _search_bm25(self, query: str, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行BM25搜索"""
        try:
            bm25_results = self.bm25_searcher.search(
                query=query,
                top_k=self.top_k,
                filters=filters
            )
            
            # 标准化分数
            bm25_scores = [result['bm25_score'] for result in bm25_results]
            if bm25_scores:
                max_score = max(bm25_scores)
                min_score = min(bm25_scores)
                
                for result in bm25_results:
                    if max_score > min_score:
                        normalized_score = (result['bm25_score'] - min_score) / (max_score - min_score)
                    else:
                        normalized_score = 1.0
                    result['normalized_bm25_score'] = normalized_score
            else:
                for result in bm25_results:
                    result['normalized_bm25_score'] = 0.0
            
            return bm25_results
            
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []
    
    def _fusion_results(self, vector_results: List[Dict[str, Any]], 
                       bm25_results: List[Dict[str, Any]], 
                       top_k: int) -> List[Dict[str, Any]]:
        """融合向量搜索和BM25结果"""
        if not vector_results and not bm25_results:
            return []
        
        if not vector_results:
            return bm25_results[:top_k]
        
        if not bm25_results:
            return vector_results[:top_k]
        
        # 按chunk_id分组
        chunk_scores = defaultdict(dict)
        
        # 添加向量搜索分数
        for i, result in enumerate(vector_results):
            chunk_id = result.get('chunk_id')
            if chunk_id:
                chunk_scores[chunk_id]['vector_score'] = result.get('normalized_vector_score', 0.0)
                chunk_scores[chunk_id]['vector_rank'] = i + 1
                chunk_scores[chunk_id]['vector_result'] = result
        
        # 添加BM25搜索分数
        for i, result in enumerate(bm25_results):
            chunk_id = result.get('chunk_id')
            if chunk_id:
                chunk_scores[chunk_id]['bm25_score'] = result.get('normalized_bm25_score', 0.0)
                chunk_scores[chunk_id]['bm25_rank'] = i + 1
                chunk_scores[chunk_id]['bm25_result'] = result
        
        # 计算混合分数
        final_results = []
        for chunk_id, scores in chunk_scores.items():
            # 加权分数融合
            vector_score = scores.get('vector_score', 0.0)
            bm25_score = scores.get('bm25_score', 0.0)
            
            hybrid_score = (self.vector_weight * vector_score + 
                          self.bm25_weight * bm25_score)
            
            # 选择完整的结果数据（优先向量搜索结果）
            base_result = scores.get('vector_result', scores.get('bm25_result', {}))
            
            # 更新结果
            result = base_result.copy()
            result['hybrid_score'] = hybrid_score
            result['vector_score'] = vector_score
            result['bm25_score'] = bm25_score
            result['vector_rank'] = scores.get('vector_rank', float('inf'))
            result['bm25_rank'] = scores.get('bm25_rank', float('inf'))
            result['search_method'] = 'hybrid'
            result['chunk_id'] = chunk_id
            
            final_results.append(result)
        
        # 按混合分数排序
        final_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        # 返回top_k结果
        return final_results[:top_k]
    
    def search_with_fallback(self, query: str, top_k: int = 10,
                           filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """带回退机制的搜索"""
        try:
            # 尝试混合搜索
            results = self.search(query, top_k, filters)
            
            # 如果结果太少，尝试回退策略
            if len(results) < min(3, top_k):
                logger.info(f"Hybrid search returned only {len(results)} results, trying fallback")
                
                # 尝试纯向量搜索
                vector_only = self.vector_searcher.search(query, top_k, filters)
                if len(vector_only) > len(results):
                    logger.info("Using vector-only results as fallback")
                    for result in vector_only:
                        result['fallback_method'] = 'vector_only'
                    return vector_only[:top_k]
                
                # 尝试纯BM25搜索
                bm25_only = self.bm25_searcher.search(query, top_k, filters)
                if len(bm25_only) > len(results):
                    logger.info("Using BM25-only results as fallback")
                    for result in bm25_only:
                        result['fallback_method'] = 'bm25_only'
                    return bm25_only[:top_k]
            
            return results
            
        except Exception as e:
            logger.error(f"Hybrid search with fallback failed: {e}")
            return []
    
    def add_documents(self, documents: List[DocumentChunkWithMetadata]) -> bool:
        """添加文档到索引"""
        try:
            # 添加到向量存储
            vector_success = self.vector_searcher.add_documents(documents)
            
            # 更新BM25索引
            for doc in documents:
                self.bm25_searcher.update_document(doc)
            
            return vector_success
            
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            return False
    
    def update_documents(self, documents: List[DocumentChunkWithMetadata]) -> bool:
        """更新索引中的文档"""
        try:
            # 更新向量存储
            vector_success = self.vector_searcher.update_documents(documents)
            
            # 更新BM25索引
            for doc in documents:
                self.bm25_searcher.update_document(doc)
            
            return vector_success
            
        except Exception as e:
            logger.error(f"Failed to update documents: {e}")
            return False
    
    def delete_documents(self, doc_ids: List[str]) -> bool:
        """从索引中删除文档"""
        try:
            # 从向量存储删除
            vector_success = self.vector_searcher.delete_documents(doc_ids)
            
            # 从BM25索引删除
            for doc_id in doc_ids:
                self.bm25_searcher.remove_document(doc_id)
            
            return vector_success
            
        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            return False
    
    def get_document_by_id(self, chunk_id: str) -> Optional[DocumentChunkWithMetadata]:
        """根据ID获取文档"""
        try:
            # 优先从向量存储获取
            document = self.vector_searcher.get_document_by_id(chunk_id)
            return document
            
        except Exception as e:
            logger.error(f"Failed to get document {chunk_id}: {e}")
            return None
    
    def count_documents(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """计算文档数量"""
        try:
            count = self.vector_searcher.count_documents(filters)
            return count
            
        except Exception as e:
            logger.error(f"Failed to count documents: {e}")
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            vector_stats = self.vector_searcher.get_statistics()
            bm25_stats = self.bm25_searcher.get_statistics()
            
            statistics = {
                "status": "initialized" if self._initialized else "not_initialized",
                "weights": {
                    "vector_weight": self.vector_weight,
                    "bm25_weight": self.bm25_weight
                },
                "parameters": {
                    "top_k": self.top_k
                },
                "vector_searcher": vector_stats,
                "bm25_searcher": bm25_stats
            }
            
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {"status": "error", "error": str(e)}
    
    def update_weights(self, vector_weight: float = None, bm25_weight: float = None):
        """更新融合权重"""
        if vector_weight is not None:
            self.vector_weight = max(0.0, min(1.0, vector_weight))
        
        if bm25_weight is not None:
            self.bm25_weight = max(0.0, min(1.0, bm25_weight))
        
        # 确保权重和为1
        total_weight = self.vector_weight + self.bm25_weight
        if total_weight > 0:
            self.vector_weight /= total_weight
            self.bm25_weight /= total_weight
        
        logger.info(f"Updated weights: vector={self.vector_weight:.3f}, bm25={self.bm25_weight:.3f}")
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self._initialized:
                return {
                    "status": "unhealthy",
                    "message": "Hybrid searcher not initialized"
                }
            
            # 检查子搜索器健康状态
            vector_health = self.vector_searcher.health_check()
            bm25_health = self.bm25_searcher.health_check()
            
            # 测试搜索功能
            test_results = self.search("test", top_k=1)
            
            overall_status = "healthy"
            if vector_health.get('status') != 'healthy':
                overall_status = "degraded"
            if bm25_health.get('status') != 'healthy':
                overall_status = "degraded"
            
            if not test_results:
                overall_status = "unhealthy"
            
            return {
                "status": overall_status,
                "vector_searcher": vector_health,
                "bm25_searcher": bm25_health,
                "test_search_results": len(test_results),
                "weights": {
                    "vector_weight": self.vector_weight,
                    "bm25_weight": self.bm25_weight
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Health check failed: {e}"
            }

# 全局混合搜索器实例
hybrid_searcher = HybridSearcher()