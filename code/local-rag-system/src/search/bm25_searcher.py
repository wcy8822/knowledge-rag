from typing import List, Dict, Any, Optional, Tuple
import math
import re
from collections import defaultdict, Counter
import logging

from ..models import DocumentChunkWithMetadata
from ..store.metadata_store import metadata_store

logger = logging.getLogger(__name__)

class BM25Searcher:
    """BM25检索引擎"""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1  # 控制词频饱和度
        self.b = b    # 控制文档长度归一化程度
        
        # BM25相关变量
        self.doc_freqs = defaultdict(dict)  # {word: {doc_id: freq}}
        self.doc_lengths = defaultdict(int)  # {doc_id: length}
        self.avg_doc_length = 0
        self.total_docs = 0
        self.vocab = set()
        
        # 文档索引
        self.documents = {}  # {chunk_id: DocumentChunkWithMetadata}
        
        self._initialized = False
    
    def build_index(self, documents: List[DocumentChunkWithMetadata]):
        """构建BM25索引"""
        logger.info(f"Building BM25 index for {len(documents)} documents")
        
        # 清空现有索引
        self.doc_freqs = defaultdict(dict)
        self.doc_lengths = defaultdict(int)
        self.documents = {}
        self.vocab = set()
        
        total_length = 0
        
        for doc in documents:
            self.documents[doc.chunk_id] = doc
            
            # 分词和清理
            terms = self._tokenize(doc.content)
            term_counts = Counter(terms)
            
            # 更新统计信息
            self.doc_lengths[doc.chunk_id] = len(terms)
            total_length += len(terms)
            
            # 更新文档频率
            for term, freq in term_counts.items():
                self.doc_freqs[term][doc.chunk_id] = freq
                self.vocab.add(term)
        
        # 计算平均文档长度
        self.total_docs = len(documents)
        self.avg_doc_length = total_length / self.total_docs if self.total_docs > 0 else 0
        
        self._initialized = True
        logger.info(f"BM25 index built successfully. Vocabulary size: {len(self.vocab)}, "
                   f"Average doc length: {self.avg_doc_length:.2f}")
    
    def search(self, query: str, top_k: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """BM25搜索"""
        if not self._initialized:
            logger.warning("BM25 index not initialized, returning empty results")
            return []
        
        # 预处理查询
        query_terms = self._tokenize(query)
        if not query_terms:
            return []
        
        # 应用过滤器
        candidate_docs = self._apply_filters(filters) if filters else set(self.documents.keys())
        
        # 计算每个文档的BM25分数
        doc_scores = defaultdict(float)
        
        for term in query_terms:
            if term not in self.doc_freqs:
                continue
            
            # 计算IDF
            df = len(self.doc_freqs[term])
            idf = math.log((self.total_docs - df + 0.5) / (df + 0.5))
            
            # 更新每个包含该词的文档的分数
            for doc_id, term_freq in self.doc_freqs[term].items():
                if doc_id not in candidate_docs:
                    continue
                
                doc_len = self.doc_lengths[doc_id]
                
                # BM25公式
                numerator = term_freq * (self.k1 + 1)
                denominator = term_freq + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_length)
                term_score = idf * (numerator / denominator)
                
                doc_scores[doc_id] += term_score
        
        # 排序并返回top_k结果
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = []
        for doc_id, score in sorted_docs:
            if doc_id in self.documents:
                doc = self.documents[doc_id]
                result = {
                    'chunk_id': doc.chunk_id,
                    'content': doc.content,
                    'metadata': doc.metadata,
                    'bm25_score': float(score),
                    'score': float(score)  # 统一接口
                }
                results.append(result)
        
        logger.info(f"BM25 search found {len(results)} results for query: {query}")
        return results
    
    def _tokenize(self, text: str) -> List[str]:
        """文本分词"""
        if not text:
            return []
        
        # 清理文本
        text = text.lower()
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)  # 保留中文字符
        
        # 分词（简单空格分割，中文单独处理）
        tokens = []
        words = text.split()
        
        for word in words:
            if not word.strip():
                continue
            
            # 中文分词：简单按字符分割
            if re.search(r'[\u4e00-\u9fff]', word):
                # 混合中英文的情况
                en_part = re.findall(r'[a-zA-Z]+', word)
                cn_part = re.findall(r'[\u4e00-\u9fff]', word)
                
                if en_part:
                    tokens.extend(en_part)
                if cn_part:
                    tokens.extend(cn_part)
            else:
                # 纯英文
                if len(word) > 2:
                    # 可能需要词干提取，这里简单截短
                    tokens.append(word[:20])
                else:
                    tokens.append(word)
        
        # 过滤停用词和短词
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have',
                     'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                     'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i',
                     'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us',
                     'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their', '的', '了',
                     '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
                     '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
                     '看', '好', '自己', '这'}
        
        filtered_tokens = [token for token in tokens 
                         if token not in stop_words and len(token) >= 2]
        
        return filtered_tokens
    
    def _apply_filters(self, filters: Dict[str, Any]) -> set:
        """应用文档过滤器"""
        if not filters:
            return set(self.documents.keys())
        
        filtered_docs = set(self.documents.keys())
        
        # 文件类型过滤
        if 'file_types' in filters:
            file_types = set(filters['file_types'])
            type_filtered = set()
            for doc_id in filtered_docs:
                doc = self.documents[doc_id]
                # 从metadata中获取文件类型信息
                if hasattr(doc, 'file_type') or 'file_type' in doc.metadata:
                    file_type = getattr(doc, 'file_type', doc.metadata.get('file_type', ''))
                    if file_type in file_types:
                        type_filtered.add(doc_id)
            filtered_docs = type_filtered
        
        # 其他过滤器可以在这里添加
        if 'min_token_count' in filters:
            min_tokens = filters['min_token_count']
            token_filtered = set()
            for doc_id in filtered_docs:
                doc = self.documents[doc_id]
                if doc.token_count >= min_tokens:
                    token_filtered.add(doc_id)
            filtered_docs = token_filtered
        
        return filtered_docs
    
    def get_document_count(self) -> int:
        """获取索引文档数量"""
        return self.total_docs
    
    def get_vocabulary_size(self) -> int:
        """获取词汇表大小"""
        return len(self.vocab)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._initialized:
            return {"status": "not_initialized"}
        
        doc_lengths = list(self.doc_lengths.values())
        
        return {
            "status": "initialized",
            "document_count": self.total_docs,
            "vocabulary_size": len(self.vocab),
            "average_doc_length": self.avg_doc_length,
            "min_doc_length": min(doc_lengths) if doc_lengths else 0,
            "max_doc_length": max(doc_lengths) if doc_lengths else 0,
            "parameters": {
                "k1": self.k1,
                "b": self.b
            }
        }
    
    def load_from_metadata_store(self, filters: Optional[Dict[str, Any]] = None):
        """从元数据存储加载文档构建索引"""
        logger.info("Loading documents from metadata store for BM25 indexing")
        
        try:
            # 从元数据存储获取文档
            documents = metadata_store.search_documents("", filters=filters, limit=10000)
            
            if not documents:
                logger.warning("No documents found in metadata store")
                return
            
            self.build_index(documents)
            
        except Exception as e:
            logger.error(f"Failed to load documents from metadata store: {e}")
    
    def update_document(self, document: DocumentChunkWithMetadata):
        """更新索引中的单个文档"""
        self.documents[document.chunk_id] = document
        
        # 重新计算词频
        terms = self._tokenize(document.content)
        term_counts = Counter(terms)
        
        # 更新文档长度
        old_length = self.doc_lengths[document.chunk_id] if document.chunk_id in self.doc_lengths else 0
        new_length = len(terms)
        self.doc_lengths[document.chunk_id] = new_length
        
        # 更新平均文档长度
        if self.total_docs > 0:
            self.avg_doc_length += (new_length - old_length) / self.total_docs
        
        # 更新词频统计
        for term, freq in term_counts.items():
            # 移除旧的频率记录（如果存在）
            if document.chunk_id in self.doc_freqs[term]:
                old_freq = self.doc_freqs[term][document.chunk_id]
                if old_freq <= 1:
                    del self.doc_freqs[term][document.chunk_id]
                    # 如果没有其他文档使用这个词，从词汇表中移除
                    if not self.doc_freqs[term]:
                        self.vocab.discard(term)
                else:
                    self.doc_freqs[term][document.chunk_id] = old_freq - freq
            
            # 添加新的频率记录
            if document.chunk_id not in self.doc_freqs[term]:
                self.doc_freqs[term][document.chunk_id] = 0
            self.doc_freqs[term][document.chunk_id] += freq
            
            # 添加到词汇表
            self.vocab.add(term)
    
    def remove_document(self, doc_id: str):
        """从索引中移除文档"""
        if doc_id not in self.documents:
            return
        
        # 移除文档
        if doc_id in self.documents:
            del self.documents[doc_id]
        
        # 更新统计信息
        if doc_id in self.doc_lengths:
            old_length = self.doc_lengths[doc_id]
            del self.doc_lengths[doc_id]
            
            if self.total_docs > 1:
                self.avg_doc_length *= self.total_docs / (self.total_docs - 1)
                self.avg_doc_length -= old_length / (self.total_docs - 1)
            else:
                self.avg_doc_length = 0
            
            self.total_docs -= 1
        
        # 更新词频统计
        terms_to_remove = []
        for term, doc_freqs in self.doc_freqs.items():
            if doc_id in doc_freqs:
                del doc_freqs[doc_id]
                # 如果没有其他文档使用这个词，准备移除
                if not doc_freqs:
                    terms_to_remove.append(term)
        
        for term in terms_to_remove:
            del self.doc_freqs[term]
            self.vocab.discard(term)
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        stats = self.get_statistics()
        
        return {
            "status": "healthy" if stats.get("status") == "initialized" else "unhealthy",
            "statistics": stats
        }

# 全局BM25搜索器实例
bm25_searcher = BM25Searcher()