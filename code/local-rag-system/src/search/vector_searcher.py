from typing import List, Dict, Any, Optional
import numpy as np
import logging

from ..models import DocumentChunkWithMetadata
from ..store.embedding_service import embedding_service
from ..store.vector_stores.chroma_store import ChromaVectorStore
from ..store.metadata_store import metadata_store
from ..config import config

logger = logging.getLogger(__name__)

class VectorSearcher:
    """向量检索引擎"""
    
    def __init__(self):
        self.config = config.get('vector_db', {})
        self.vector_store = ChromaVectorStore(self.config)
        self._initialized = False
    
    def initialize(self):
        """初始化向量检索器"""
        try:
            # 检查向量存储健康状态
            health = self.vector_store.health_check()
            if health.get('status') != 'healthy':
                logger.error(f"Vector store not healthy: {health}")
                return False
            
            self._initialized = True
            logger.info("Vector searcher initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize vector searcher: {e}")
            return False
    
    def search(self, query: str, top_k: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """向量搜索"""
        if not self._initialized:
            logger.warning("Vector searcher not initialized")
            return []
        
        if not query.strip():
            logger.warning("Empty query provided")
            return []
        
        try:
            # 生成查询向量
            query_embedding = embedding_service.embed_single(query)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []
            
            # 在向量存储中搜索
            results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filters=filters
            )
            
            # 处理结果
            processed_results = []
            for result in results:
                processed_result = self._process_search_result(result)
                processed_results.append(processed_result)
            
            logger.info(f"Vector search found {len(processed_results)} results for query: {query[:50]}...")
            return processed_results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def search_by_embedding(self, query_embedding: List[float], top_k: int = 10,
                          filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """根据向量搜索"""
        if not self._initialized:
            logger.warning("Vector searcher not initialized")
            return []
        
        if not query_embedding:
            logger.warning("Empty embedding provided")
            return []
        
        try:
            # 在向量存储中搜索
            results = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filters=filters
            )
            
            # 处理结果
            processed_results = []
            for result in results:
                processed_result = self._process_search_result(result)
                processed_results.append(processed_result)
            
            logger.info(f"Vector embedding search found {len(processed_results)} results")
            return processed_results
            
        except Exception as e:
            logger.error(f"Vector embedding search failed: {e}")
            return []
    
    def add_documents(self, documents: List[DocumentChunkWithMetadata]) -> bool:
        """添加文档到向量存储"""
        if not self._initialized:
            logger.error("Vector searcher not initialized")
            return False
        
        if not documents:
            return True
        
        try:
            # 确保文档有嵌入向量
            documents_with_embeddings = []
            for doc in documents:
                if not doc.embedding:
                    # 生成嵌入向量
                    doc.embedding = embedding_service.embed_single(doc.content)
                
                if doc.embedding:
                    documents_with_embeddings.append(doc)
                else:
                    logger.warning(f"Failed to generate embedding for document {doc.chunk_id}")
            
            if not documents_with_embeddings:
                logger.warning("No documents with valid embeddings to add")
                return False
            
            # 添加到向量存储
            added_ids = self.vector_store.add_documents(documents_with_embeddings)
            
            logger.info(f"Added {len(added_ids)} documents to vector store")
            return len(added_ids) > 0
            
        except Exception as e:
            logger.error(f"Failed to add documents to vector store: {e}")
            return False
    
    def update_documents(self, documents: List[DocumentChunkWithMetadata]) -> bool:
        """更新向量存储中的文档"""
        if not self._initialized:
            logger.error("Vector searcher not initialized")
            return False
        
        if not documents:
            return True
        
        try:
            # 确保文档有嵌入向量
            for doc in documents:
                if not doc.embedding:
                    doc.embedding = embedding_service.embed_single(doc.content)
            
            # 更新向量存储
            updated_ids = self.vector_store.update_documents(documents)
            
            logger.info(f"Updated {len(updated_ids)} documents in vector store")
            return len(updated_ids) > 0
            
        except Exception as e:
            logger.error(f"Failed to update documents in vector store: {e}")
            return False
    
    def delete_documents(self, doc_ids: List[str]) -> bool:
        """从向量存储删除文档"""
        if not self._initialized:
            logger.error("Vector searcher not initialized")
            return False
        
        if not doc_ids:
            return True
        
        try:
            success = self.vector_store.delete_documents(doc_ids)
            
            if success:
                logger.info(f"Deleted {len(doc_ids)} documents from vector store")
            else:
                logger.warning(f"Failed to delete {len(doc_ids)} documents from vector store")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete documents from vector store: {e}")
            return False
    
    def get_document_by_id(self, chunk_id: str) -> Optional[DocumentChunkWithMetadata]:
        """根据ID获取文档"""
        if not self._initialized:
            logger.warning("Vector searcher not initialized")
            return None
        
        try:
            document = self.vector_store.get_document_by_id(chunk_id)
            return document
            
        except Exception as e:
            logger.error(f"Failed to get document {chunk_id}: {e}")
            return None
    
    def count_documents(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """计算文档数量"""
        if not self._initialized:
            logger.warning("Vector searcher not initialized")
            return 0
        
        try:
            count = self.vector_store.count_documents(filters)
            return count
            
        except Exception as e:
            logger.error(f"Failed to count documents: {e}")
            return 0
    
    def rebuild_index(self, filters: Optional[Dict[str, Any]] = None) -> bool:
        """重建索引"""
        logger.info("Rebuilding vector index...")
        
        try:
            # 从元数据存储获取所有文档
            if filters:
                documents = metadata_store.search_documents("", filters=filters, limit=10000)
            else:
                documents = metadata_store.search_documents("", limit=10000)
            
            if not documents:
                logger.warning("No documents found for index rebuild")
                return False
            
            # 生成嵌入向量并添加到向量存储
            success = self.add_documents(documents)
            
            if success:
                logger.info(f"Vector index rebuilt with {len(documents)} documents")
            else:
                logger.error("Failed to rebuild vector index")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to rebuild vector index: {e}")
            return False
    
    def _process_search_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """处理搜索结果"""
        processed_result = result.copy()
        
        # 确保必要的字段存在
        if 'vector_score' not in processed_result:
            processed_result['vector_score'] = result.get('score', 0.0)
        
        # 添加搜索方法标识
        processed_result['search_method'] = 'vector'
        
        # 处理元数据
        metadata = processed_result.get('metadata', {})
        if not isinstance(metadata, dict):
            metadata = {}
        
        # 确保有chunk_id
        if 'chunk_id' not in processed_result and 'chunk_id' not in metadata:
            processed_result['chunk_id'] = processed_result.get('id', '')
        
        return processed_result
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            return {"status": "not_initialized"}
        
        try:
            # 获取向量存储统计信息
            vector_stats = self.vector_store.health_check()
            
            # 获取嵌入服务统计信息
            embedding_stats = embedding_service.health_check()
            
            # 合并统计信息
            statistics = {
                "status": "initialized",
                "vector_store": vector_stats,
                "embedding_service": embedding_stats,
                "document_count": self.count_documents()
            }
            
            return statistics
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {"status": "error", "error": str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        if not self._initialized:
            return {
                "status": "unhealthy",
                "message": "Vector searcher not initialized"
            }
        
        try:
            # 检查向量存储
            vector_health = self.vector_store.health_check()
            
            # 检查嵌入服务
            embedding_health = embedding_service.health_check()
            
            # 测试搜索功能
            test_results = self.search("test", top_k=1)
            
            overall_status = "healthy"
            if vector_health.get('status') != 'healthy':
                overall_status = "unhealthy"
            if embedding_health.get('test_embedding_success') != True:
                overall_status = "degraded"
            
            return {
                "status": overall_status,
                "vector_store": vector_health,
                "embedding_service": embedding_health,
                "test_search_results": len(test_results)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Health check failed: {e}"
            }

# 全局向量搜索器实例
vector_searcher = VectorSearcher()