from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from ..models import DocumentChunkWithMetadata

class BaseVectorStore(ABC):
    """向量存储基类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.collection_name = self.config.get('collection_name', 'knowledge_base')
    
    @abstractmethod
    def add_documents(self, documents: List[DocumentChunkWithMetadata]) -> List[str]:
        """添加文档向量"""
        pass
    
    @abstractmethod
    def search(self, query_embedding: List[float], top_k: int = 10, 
              filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """向量搜索"""
        pass
    
    @abstractmethod
    def delete_documents(self, doc_ids: List[str]) -> bool:
        """删除文档"""
        pass
    
    @abstractmethod
    def update_documents(self, documents: List[DocumentChunkWithMetadata]) -> List[str]:
        """更新文档"""
        pass
    
    @abstractmethod
    def get_document_by_id(self, chunk_id: str) -> Optional[DocumentChunkWithMetadata]:
        """根据ID获取文档"""
        pass
    
    @abstractmethod
    def count_documents(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """计算文档数量"""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        pass
    
    def _validate_embedding(self, embedding: List[float]) -> bool:
        """验证嵌入向量格式"""
        return (
            isinstance(embedding, list) and
            len(embedding) > 0 and
            all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in embedding)
        )
    
    def _extract_metadata(self, document: DocumentChunkWithMetadata) -> Dict[str, Any]:
        """提取元数据用于存储"""
        metadata = document.metadata.copy()
        
        # 添加特定元数据
        if document.excel_metadata:
            metadata['_excel_metadata'] = document.excel_metadata.dict()
        if document.ppt_metadata:
            metadata['_ppt_metadata'] = document.ppt_metadata.dict()
        if document.code_metadata:
            metadata['_code_metadata'] = document.code_metadata.dict()
        
        return metadata
    
    def _restore_metadata(self, metadata: Dict[str, Any]) -> Tuple[Dict[str, Any], Any, Any, Any]:
        """恢复元数据"""
        base_metadata = metadata.copy()
        excel_metadata = None
        ppt_metadata = None
        code_metadata = None
        
        # 恢复特定元数据
        if '_excel_metadata' in metadata:
            from ...models import ExcelMetadata
            excel_metadata = ExcelMetadata(**metadata['_excel_metadata'])
            del base_metadata['_excel_metadata']
            
        if '_ppt_metadata' in metadata:
            from ...models import PPTMetadata
            ppt_metadata = PPTMetadata(**metadata['_ppt_metadata'])
            del base_metadata['_ppt_metadata']
            
        if '_code_metadata' in metadata:
            from ...models import CodeMetadata
            code_metadata = CodeMetadata(**metadata['_code_metadata'])
            del base_metadata['_code_metadata']
        
        return base_metadata, excel_metadata, ppt_metadata, code_metadata