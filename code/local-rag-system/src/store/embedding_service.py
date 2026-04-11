from typing import List, Optional, Union
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel
import logging
from tqdm import tqdm

from ..config import config
from ..models import DocumentChunkWithMetadata

logger = logging.getLogger(__name__)

class EmbeddingService:
    """向量化服务"""
    
    def __init__(self):
        self.config = config.get('embedding', {})
        self.model_name = self.config.get('model_name', 'BAAI/bge-m3')
        self.device = self.config.get('device', 'cpu')
        self.batch_size = self.config.get('batch_size', 32)
        self.normalize_embeddings = self.config.get('normalize_embeddings', True)
        self.max_length = self.config.get('max_length', 8192)
        
        self.model = None
        self.tokenizer = None
        self._load_model()
    
    def _load_model(self):
        """加载嵌入模型"""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            
            # 检查GPU可用性
            if self.device == 'cuda' and not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU")
                self.device = 'cpu'
            
            # 使用sentence-transformers加载模型（推荐）
            if 'bge' in self.model_name.lower():
                self.model = SentenceTransformer(
                    self.model_name,
                    device=self.device,
                    trust_remote_code=True
                )
                self.model.max_seq_length = self.max_length
                logger.info(f"Loaded sentence-transformer model on {self.device}")
            else:
                # 使用transformers加载其他模型
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    trust_remote_code=True
                )
                self.model = AutoModel.from_pretrained(
                    self.model_name,
                    trust_remote_code=True
                ).to(self.device)
                logger.info(f"Loaded transformer model on {self.device}")
                
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            # 回退到简单的词袋模型
            self._init_fallback_model()
    
    def _init_fallback_model(self):
        """初始化回退模型"""
        logger.warning("Using fallback TF-IDF based embeddings")
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.decomposition import TruncatedSVD
        
        self.fallback_vectorizer = TfidfVectorizer(
            max_features=768,
            stop_words='english'
        )
        self.fallback_reducer = TruncatedSVD(n_components=768)
        self.use_fallback = True
    def embed_texts(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """向量化文本列表"""
        if not texts:
            return []
        
        batch_size = batch_size or self.batch_size
        embeddings = []
        
        logger.info(f"Embedding {len(texts)} texts in batches of {batch_size}")
        
        if hasattr(self, 'use_fallback') and self.use_fallback:
            return self._embed_texts_fallback(texts)
        
        try:
            # 分批处理
            for i in tqdm(range(0, len(texts), batch_size), desc="Embedding"):
                batch_texts = texts[i:i + batch_size]
                
                # 预处理文本
                cleaned_texts = [self._preprocess_text(text) for text in batch_texts]
                
                # 生成嵌入
                if hasattr(self.model, 'encode'):
                    # sentence-transformers模型
                    batch_embeddings = self.model.encode(
                        cleaned_texts,
                        batch_size=len(batch_texts),
                        normalize_embeddings=self.normalize_embeddings,
                        show_progress_bar=False
                    )
                    embeddings.extend(batch_embeddings.tolist())
                else:
                    # transformers模型
                    batch_embeddings = self._encode_with_transformers(cleaned_texts)
                    embeddings.extend(batch_embeddings)
        
        except Exception as e:
            logger.error(f"Error during embedding: {e}")
            # 回退到简单方法
            return self._embed_texts_simple(texts)
        
        return embeddings
    
    def embed_single(self, text: str) -> List[float]:
        """向量化单个文本"""
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else []
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本"""
        if not text:
            return ""
        
        # 基本清理
        text = text.strip()
        
        # 移除过多空白
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # 截断过长的文本
        max_chars = self.max_length * 4  # 粗略估算
        if len(text) > max_chars:
            text = text[:max_chars]
        
        return text
    
    def _encode_with_transformers(self, texts: List[str]) -> List[List[float]]:
        """使用transformers模型编码"""
        embeddings = []
        
        with torch.no_grad():
            for text in texts:
                try:
                    # Tokenize
                    inputs = self.tokenizer(
                        text,
                        truncation=True,
                        padding=True,
                        max_length=self.max_length,
                        return_tensors='pt'
                    ).to(self.device)
                    
                    # 获取模型输出
                    outputs = self.model(**inputs)
                    
                    # 池化策略：使用[CLS] token或平均池化
                    if hasattr(outputs, 'last_hidden_state'):
                        if outputs.last_hidden_state.shape[1] > 0:
                            # 平均池化
                            embedding = outputs.last_hidden_state.mean(dim=1)
                        else:
                            embedding = torch.zeros(1, 768).to(self.device)
                    else:
                        embedding = outputs.pooler_output
                    
                    # 归一化
                    if self.normalize_embeddings:
                        embedding = torch.nn.functional.normalize(embedding, p=2, dim=1)
                    
                    embeddings.extend(embedding.cpu().numpy().tolist())
                
                except Exception as e:
                    logger.warning(f"Error encoding text: {e}")
                    # 使用零向量作为回退
                    embeddings.append([0.0] * 768)
        
        return embeddings
    
    def _embed_texts_fallback(self, texts: List[str]) -> List[List[float]]:
        """回退方法：TF-IDF + SVD"""
        try:
            # 如果是第一次调用，先拟合模型
            if not hasattr(self.fallback_vectorizer, 'vocabulary_') or not self.fallback_vectorizer.vocabulary_:
                self.fallback_vectorizer.fit(texts)
                tfidf_matrix = self.fallback_vectorizer.transform(texts)
                self.fallback_reducer.fit(tfidf_matrix)
            else:
                tfidf_matrix = self.fallback_vectorizer.transform(texts)
            
            # 降维到768维
            embeddings = self.fallback_reducer.transform(tfidf_matrix)
            
            # 归一化
            if self.normalize_embeddings:
                from sklearn.preprocessing import normalize
                embeddings = normalize(embeddings, norm='l2')
            
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"Fallback embedding failed: {e}")
            return self._embed_texts_simple(texts)
    
    def _embed_texts_simple(self, texts: List[str]) -> List[List[float]]:
        """最简单的回退方法：基于hash的伪嵌入"""
        import hashlib
        
        embeddings = []
        for text in texts:
            # 使用文本的hash生成固定维度向量
            hash_obj = hashlib.sha256(text.encode())
            hash_hex = hash_obj.hexdigest()
            
            # 转换为768维向量
            vector = []
            for i in range(0, min(len(hash_hex), 768), 2):
                byte_val = int(hash_hex[i:i+2], 16) if i+2 < len(hash_hex) else int(hash_hex[i], 16)
                normalized_val = (byte_val - 128) / 128.0
                vector.append(normalized_val)
            
            # 填充到768维
            while len(vector) < 768:
                vector.append(0.0)
            
            embeddings.append(vector[:768])
        
        return embeddings
    
    def embed_documents(self, documents: List[DocumentChunkWithMetadata]) -> List[DocumentChunkWithMetadata]:
        """向量化文档块列表"""
        if not documents:
            return []
        
        # 提取文本
        texts = [doc.content for doc in documents]
        
        # 生成嵌入
        embeddings = self.embed_texts(texts)
        
        # 更新文档块
        for doc, embedding in zip(documents, embeddings):
            doc.embedding = embedding
        
        return documents
    
    def get_embedding_dimension(self) -> int:
        """获取嵌入维度"""
        if hasattr(self.model, 'get_sentence_embedding_dimension'):
            return self.model.get_sentence_embedding_dimension()
        elif hasattr(self, 'use_fallback') and self.use_fallback:
            return 768
        else:
            return 768  # BGE-M3默认维度
    
    def health_check(self) -> dict:
        """健康检查"""
        status = {
            "model_loaded": self.model is not None,
            "device": self.device,
            "model_name": self.model_name,
            "embedding_dimension": self.get_embedding_dimension(),
            "batch_size": self.batch_size,
            "fallback_mode": hasattr(self, 'use_fallback') and self.use_fallback
        }
        
        # 测试嵌入
        try:
            test_embedding = self.embed_single("test")
            status["test_embedding_success"] = len(test_embedding) > 0
        except Exception as e:
            status["test_embedding_success"] = False
            status["test_embedding_error"] = str(e)
        
        return status

# 全局嵌入服务实例
embedding_service = EmbeddingService()