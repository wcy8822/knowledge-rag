from typing import List, Dict, Any, Optional, Tuple
import chromadb
from chromadb.config import Settings as ChromaSettings
import logging
from uuid import uuid4

from .base_store import BaseVectorStore
from ...models import DocumentChunkWithMetadata

logger = logging.getLogger(__name__)

class ChromaVectorStore(BaseVectorStore):
    """ChromaDB向量存储实现"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.persist_directory = self.config.get('persist_directory', './data/chroma')
        self.host = self.config.get('host', 'localhost')
        self.port = self.config.get('port', 8001)
        
        self.client = None
        self.collection = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化ChromaDB客户端"""
        try:
            # 尝试连接到持久化的ChromaDB
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=False
                )
            )
            
            # 获取或创建collection
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
                logger.info(f"Connected to existing collection: {self.collection_name}")
            except Exception:
                self.collection = self.client.create_collection(name=self.collection_name)
                logger.info(f"Created new collection: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client: {e}")
            # 尝试内存模式作为回退
            try:
                self.client = chromadb.Client()
                self.collection = self.client.create_collection(name=self.collection_name)
                logger.warning("Using in-memory ChromaDB as fallback")
            except Exception as e2:
                logger.error(f"Failed to initialize in-memory client: {e2}")
                raise
    
    def add_documents(self, documents: List[DocumentChunkWithMetadata]) -> List[str]:
        """添加文档向量"""
        if not documents:
            return []
        
        ids = []
        embeddings = []
        documents_text = []
        metadatas = []
        
        for doc in documents:
            # 验证嵌入向量
            if not doc.embedding or not self._validate_embedding(doc.embedding):
                logger.warning(f"Invalid embedding for document {doc.chunk_id}")
                continue
            
            ids.append(doc.chunk_id)
            embeddings.append(doc.embedding)
            documents_text.append(doc.content)
            metadatas.append(self._extract_metadata(doc))
        
        if not ids:
            logger.warning("No valid documents to add")
            return []
        
        try:
            # 批量添加到ChromaDB
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents_text,
                metadatas=metadatas
            )
            
            logger.info(f"Successfully added {len(ids)} documents to ChromaDB")
            return ids
            
        except Exception as e:
            logger.error(f"Failed to add documents to ChromaDB: {e}")
            return []
    
    def search(self, query_embedding: List[float], top_k: int = 10,
              filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """向量搜索"""
        if not self._validate_embedding(query_embedding):
            raise ValueError("Invalid query embedding")
        
        try:
            # 构建查询参数
            query_params = {
                "query_embeddings": [query_embedding],
                "n_results": top_k
            }
            
            # 添加过滤条件
            if filters:
                where_conditions = self._build_where_clause(filters)
                if where_conditions:
                    query_params["where"] = where_conditions
            
            # 执行搜索
            results = self.collection.query(**query_params)
            
            # 格式化结果
            formatted_results = []
            if (results['ids'] and results['ids'][0] and 
                results['documents'] and results['documents'][0]):
                
                for i in range(len(results['ids'][0])):
                    result = {
                        'chunk_id': results['ids'][0][i],
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i] if results['metadatas'][0] else {},
                        'distance': results['distances'][0][i] if results['distances'][0] else 0.0,
                        'score': 1.0 - (results['distances'][0][i] if results['distances'][0] else 0.0)
                    }
                    formatted_results.append(result)
            
            logger.info(f"Found {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def delete_documents(self, doc_ids: List[str]) -> bool:
        """删除文档"""
        if not doc_ids:
            return True
        
        try:
            self.collection.delete(ids=doc_ids)
            logger.info(f"Deleted {len(doc_ids)} documents")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            return False
    
    def update_documents(self, documents: List[DocumentChunkWithMetadata]) -> List[str]:
        """更新文档"""
        if not documents:
            return []
        
        try:
            # ChromaDB不支持直接更新，需要先删除再添加
            doc_ids = [doc.chunk_id for doc in documents]
            self.delete_documents(doc_ids)
            
            # 添加更新后的文档
            return self.add_documents(documents)
            
        except Exception as e:
            logger.error(f"Failed to update documents: {e}")
            return []
    
    def get_document_by_id(self, chunk_id: str) -> Optional[DocumentChunkWithMetadata]:
        """根据ID获取文档"""
        try:
            results = self.collection.get(
                ids=[chunk_id],
                include=['documents', 'metadatas', 'embeddings']
            )
            
            if (results['ids'] and results['documents'] and 
                results['documents'][0] is not None):
                
                # 重建元数据
                metadata, excel_meta, ppt_meta, code_meta = self._restore_metadata(
                    results['metadatas'][0] if results['metadatas'][0] else {}
                )
                
                # 创建文档对象
                document = DocumentChunkWithMetadata(
                    chunk_id=chunk_id,
                    doc_id=metadata.get('doc_id', ''),
                    content=results['documents'][0],
                    chunk_index=metadata.get('chunk_index', 0),
                    token_count=metadata.get('token_count', 0),
                    metadata=metadata,
                    embedding=results['embeddings'][0] if results['embeddings'][0] else None
                )
                
                # 恢复特定元数据
                document.excel_metadata = excel_meta
                document.ppt_metadata = ppt_meta
                document.code_metadata = code_meta
                
                return document
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get document {chunk_id}: {e}")
            return None
    
    def count_documents(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """计算文档数量"""
        try:
            # ChromaDB没有直接的count方法，使用查询获取所有ID
            query_params = {
                "query_embeddings": [[0.0] * 768],  # 虚拟嵌入
                "n_results": 1  # 只需要数量
            }
            
            if filters:
                where_conditions = self._build_where_clause(filters)
                if where_conditions:
                    query_params["where"] = where_conditions
            
            results = self.collection.query(**query_params)
            count = len(results['ids'][0]) if results['ids'] and results['ids'][0] else 0
            return count
            
        except Exception as e:
            logger.error(f"Failed to count documents: {e}")
            return 0
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 检查客户端连接
            if not self.client:
                return {"status": "error", "message": "Client not initialized"}
            
            # 检查collection
            if not self.collection:
                return {"status": "error", "message": "Collection not found"}
            
            # 尝试简单查询
            try:
                count = self.count_documents()
                
                return {
                    "status": "healthy",
                    "client_type": "persistent" if self.persist_directory else "in-memory",
                    "collection_name": self.collection_name,
                    "document_count": count,
                    "persist_directory": self.persist_directory
                }
                
            except Exception as e:
                return {"status": "error", "message": f"Query failed: {e}"}
                
        except Exception as e:
            return {"status": "error", "message": f"Health check failed: {e}"}
    
    def _build_where_clause(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """构建ChromaDB where子句"""
        if not filters:
            return {}
        
        conditions = []
        
        for key, value in filters.items():
            if isinstance(value, list):
                # IN条件
                conditions.append({key: {"$in": value}})
            elif isinstance(value, dict):
                # 复杂条件
                conditions.append({key: value})
            else:
                # 等值条件
                conditions.append({key: value})
        
        # 如果只有一个条件，直接返回
        if len(conditions) == 1:
            return conditions[0]
        
        # 多个条件使用AND连接
        return {"$and": conditions}
    
    def get_collection_info(self) -> Dict[str, Any]:
        """获取collection信息"""
        try:
            if not self.collection:
                return {}
            
            # 获取collection统计信息
            count = self.count_documents()
            
            return {
                "name": self.collection_name,
                "document_count": count,
                "persist_directory": self.persist_directory,
                "client_type": "persistent" if self.persist_directory else "in-memory"
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}