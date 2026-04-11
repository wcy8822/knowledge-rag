from typing import List, Dict, Any, Optional, Tuple
import torch
from sentence_transformers import CrossEncoder
import numpy as np
import logging

from ..models import DocumentChunkWithMetadata
from ..config import config

logger = logging.getLogger(__name__)

class Reranker:
    """重排序器（BGE-reranker）"""
    
    def __init__(self):
        self.config = config.get('retrieval', {}).get('reranker', {})
        self.model_name = self.config.get('model_name', 'BAAI/bge-reranker-base')
        self.device = self.config.get('device', 'cpu')
        self.top_n = self.config.get('top_n', 6)
        self.batch_size = self.config.get('batch_size', 16)
        self.enabled = self.config.get('enabled', True)
        
        self.model = None
        self._initialized = False
        
        if self.enabled:
            self._load_model()
    
    def _load_model(self):
        """加载重排序模型"""
        try:
            logger.info(f"Loading reranker model: {self.model_name}")
            
            # 检查设备可用性
            if self.device == 'cuda' and not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU for reranker")
                self.device = 'cpu'
            
            # 加载CrossEncoder模型
            self.model = CrossEncoder(
                self.model_name,
                device=self.device,
                trust_remote_code=True
            )
            
            self._initialized = True
            logger.info(f"Reranker loaded successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to load reranker model: {e}")
            self.enabled = False
            logger.warning("Reranker disabled due to model loading failure")
    
    def rerank(self, query: str, documents: List[Dict[str, Any]], 
                top_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """重排序文档"""
        if not self.enabled or not self._initialized or not documents:
            logger.debug("Reranker not enabled or not initialized, returning original documents")
            return documents
        
        if not query.strip():
            return documents
        
        top_n = top_n or self.top_n
        
        try:
            # 准备重排序数据
            rerank_data = self._prepare_rerank_data(query, documents)
            
            if len(rerank_data) <= 1:
                return documents
            
            # 批量计算相关性分数
            scores = self._compute_scores(rerank_data)
            
            # 合并分数并排序
            reranked_docs = self._merge_scores_and_sort(documents, scores)
            
            # 返回top_n结果
            final_results = reranked_docs[:top_n]
            
            logger.info(f"Reranked {len(documents)} documents to {len(final_results)} results")
            return final_results
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # 返回原始文档
            return documents[:top_n]
    
    def _prepare_rerank_data(self, query: str, documents: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
        """准备重排序数据"""
        rerank_data = []
        
        for doc in documents:
            # 提取文档内容
            content = doc.get('content', '')
            
            # 如果内容太长，截取前512个字符
            if len(content) > 512:
                content = content[:512] + "..."
            
            # 移除多余空白
            content = ' '.join(content.split())
            
            if content.strip():
                rerank_data.append((query, content))
        
        return rerank_data
    
    def _compute_scores(self, rerank_data: List[Tuple[str, str]]) -> np.ndarray:
        """计算重排序分数"""
        if not rerank_data:
            return np.array([])
        
        try:
            # 分批处理
            all_scores = []
            
            for i in range(0, len(rerank_data), self.batch_size):
                batch_data = rerank_data[i:i + self.batch_size]
                
                # 使用模型计算分数
                batch_scores = self.model.predict(batch_data)
                all_scores.extend(batch_scores)
            
            return np.array(all_scores)
            
        except Exception as e:
            logger.error(f"Failed to compute rerank scores: {e}")
            return np.zeros(len(rerank_data))
    
    def _merge_scores_and_sort(self, documents: List[Dict[str, Any]], 
                              scores: np.ndarray) -> List[Dict[str, Any]]:
        """合并分数并排序"""
        # 确保分数数量匹配
        if len(scores) != len(documents):
            logger.warning(f"Score count ({len(scores)}) doesn't match document count ({len(documents)})")
            min_length = min(len(scores), len(documents))
            documents = documents[:min_length]
            scores = scores[:min_length]
        
        # 合并分数到文档中
        scored_docs = []
        for doc, score in zip(documents, scores):
            scored_doc = doc.copy()
            scored_doc['rerank_score'] = float(score)
            scored_docs.append(scored_doc)
        
        # 按重排序分数降序排列
        scored_docs.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        return scored_docs
    
    def rerank_with_fallback(self, query: str, documents: List[Dict[str, Any]], 
                           top_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """带回退机制的重排序"""
        try:
            # 尝试重排序
            reranked = self.rerank(query, documents, top_n)
            
            # 如果重排序失败或结果异常，使用原始排序
            if not reranked or len(reranked) == 0:
                logger.warning("Reranking failed, using original order")
                return documents[:top_n or self.top_n]
            
            return reranked
            
        except Exception as e:
            logger.error(f"Reranking with fallback failed: {e}")
            return documents[:top_n or self.top_n]
    
    def enable(self):
        """启用重排序器"""
        if not self._initialized and not self.model:
            self._load_model()
        self.enabled = True
        logger.info("Reranker enabled")
    
    def disable(self):
        """禁用重排序器"""
        self.enabled = False
        logger.info("Reranker disabled")
    
    def set_top_n(self, top_n: int):
        """设置返回结果数量"""
        self.top_n = max(1, top_n)
        logger.info(f"Reranker top_n set to {self.top_n}")
    
    def set_batch_size(self, batch_size: int):
        """设置批处理大小"""
        self.batch_size = max(1, batch_size)
        logger.info(f"Reranker batch_size set to {self.batch_size}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        statistics = {
            "enabled": self.enabled,
            "initialized": self._initialized,
            "model_name": self.model_name,
            "device": self.device,
            "top_n": self.top_n,
            "batch_size": self.batch_size
        }
        
        if self.model and self._initialized:
            try:
                # 获取模型信息
                if hasattr(self.model, 'model'):
                    model_params = sum(p.numel() for p in self.model.model.parameters())
                    statistics["model_parameters"] = model_params
                
                statistics["model_loaded"] = True
            except Exception as e:
                statistics["model_loaded"] = False
                statistics["model_error"] = str(e)
        else:
            statistics["model_loaded"] = False
        
        return statistics
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self.enabled:
                return {
                    "status": "disabled",
                    "message": "Reranker is disabled"
                }
            
            if not self._initialized:
                return {
                    "status": "unhealthy",
                    "message": "Reranker not initialized"
                }
            
            # 测试重排序功能
            test_docs = [
                {"content": "这是一个测试文档"},
                {"content": "这是另一个测试文档"}
            ]
            
            test_results = self.rerank("测试", test_docs, top_n=2)
            
            return {
                "status": "healthy",
                "model_name": self.model_name,
                "device": self.device,
                "test_results": len(test_results),
                "top_n": self.top_n,
                "batch_size": self.batch_size
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Health check failed: {e}"
            }
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """获取内存使用情况"""
        try:
            if not self._initialized or not torch.cuda.is_available():
                return {"cuda_available": False}
            
            # 获取GPU内存使用情况
            device = torch.device(self.device)
            if device.type == 'cuda':
                allocated = torch.cuda.memory_allocated(device)
                reserved = torch.cuda.memory_reserved(device)
                max_allocated = torch.cuda.max_memory_allocated(device)
                
                return {
                    "cuda_available": True,
                    "device": self.device,
                    "memory_allocated_mb": allocated / (1024**2),
                    "memory_reserved_mb": reserved / (1024**2),
                    "max_memory_allocated_mb": max_allocated / (1024**2)
                }
            else:
                return {"cuda_available": True, "device": "cpu"}
                
        except Exception as e:
            return {"cuda_available": False, "error": str(e)}

# 全局重排序器实例
reranker = Reranker()