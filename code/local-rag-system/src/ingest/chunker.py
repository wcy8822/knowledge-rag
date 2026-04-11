from typing import List, Dict, Any, Optional
import re
from dataclasses import dataclass

from ..models.document import DocumentChunkWithMetadata

@dataclass
class ChunkConfig:
    """切分配置"""
    chunk_size: int = 750  # tokens
    chunk_overlap: int = 0.15  # 重叠比例
    min_chunk_size: int = 50  # 最小块大小
    max_chunk_size: int = 1500  # 最大块大小
    separator: str = "\n\n"  # 段落分隔符
    separators: List[str] = None  # 备用分隔符列表
    
    def __post_init__(self):
        if self.separators is None:
            self.separators = ["\n\n", "\n", ". ", "。", "! ", "！", "? ", "？"]

class TextChunker:
    """文本切分器"""
    
    def __init__(self, config: ChunkConfig = None):
        self.config = config or ChunkConfig()
    
    def chunk_text(self, text: str, doc_id: str, metadata: Dict[str, Any] = None) -> List[DocumentChunkWithMetadata]:
        """切分文本为chunks"""
        if not text or not text.strip():
            return []
        
        # 清理文本
        text = self._clean_text(text)
        
        # 计算总token数
        total_tokens = self._count_tokens(text)
        
        if total_tokens <= self.config.chunk_size:
            # 文本较短，不需要切分
            return [self._create_chunk(text, 0, doc_id, metadata)]
        
        # 文本较长，需要切分
        return self._split_text(text, doc_id, metadata)
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        # 移除首尾空白
        text = text.strip()
        return text
    
    def _count_tokens(self, text: str) -> int:
        """估算token数量（简化实现）"""
        # 这里使用简化的token计算方法
        # 实际应用中可以使用tiktoken等库
        words = text.split()
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        return len(words) + chinese_chars
    
    def _split_text(self, text: str, doc_id: str, metadata: Dict[str, Any] = None) -> List[DocumentChunkWithMetadata]:
        """分割文本"""
        chunks = []
        
        # 按分隔符分割
        separators = self.config.separators
        
        for separator in separators:
            sections = text.split(separator)
            
            # 尝试按当前分隔符切分
            chunks = self._split_by_separator(sections, separator, doc_id, metadata)
            
            # 检查是否满足大小要求
            if self._validate_chunks(chunks):
                return chunks
            
            # 如果不满足，尝试下一个分隔符
            chunks = []
        
        # 如果所有分隔符都不满足，按字符强制分割
        if not chunks:
            chunks = self._split_by_characters(text, doc_id, metadata)
        
        return chunks
    
    def _split_by_separator(self, sections: List[str], separator: str, 
                           doc_id: str, metadata: Dict[str, Any] = None) -> List[DocumentChunkWithMetadata]:
        """按分隔符分割"""
        chunks = []
        current_chunk = ""
        current_tokens = 0
        chunk_index = 0
        
        for i, section in enumerate(sections):
            # 清理section
            section = section.strip()
            if not section:
                continue
            
            # 添加分隔符（除了最后一个section）
            if i < len(sections) - 1:
                section_with_sep = section + separator
            else:
                section_with_sep = section
            
            section_tokens = self._count_tokens(section_with_sep)
            
            # 检查是否超过chunk大小
            if current_tokens + section_tokens > self.config.chunk_size:
                # 保存当前chunk
                if current_chunk.strip():
                    chunk = self._create_chunk(current_chunk, chunk_index, doc_id, metadata)
                    chunks.append(chunk)
                    chunk_index += 1
                
                # 如果单个section过大，需要进一步分割
                if section_tokens > self.config.max_chunk_size:
                    sub_chunks = self._split_oversized_section(section, doc_id, metadata)
                    chunks.extend(sub_chunks)
                    chunk_index += len(sub_chunks)
                    current_chunk = ""
                    current_tokens = 0
                else:
                    current_chunk = section_with_sep
                    current_tokens = section_tokens
            else:
                # 添加到当前chunk
                current_chunk += section_with_sep
                current_tokens += section_tokens
        
        # 处理最后剩余内容
        if current_chunk.strip():
            chunk = self._create_chunk(current_chunk, chunk_index, doc_id, metadata)
            chunks.append(chunk)
        
        return chunks
    
    def _split_oversized_section(self, section: str, doc_id: str, 
                                 metadata: Dict[str, Any] = None) -> List[DocumentChunkWithMetadata]:
        """分割过大的section"""
        chunks = []
        
        # 按句子分割
        sentences = re.split(r'[.!?。！？]', section)
        
        current_chunk = ""
        current_tokens = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_tokens = self._count_tokens(sentence)
            
            if current_tokens + sentence_tokens > self.config.chunk_size:
                # 保存当前chunk
                if current_chunk.strip():
                    chunk = self._create_chunk(current_chunk, 0, doc_id, metadata)
                    chunks.append(chunk)
                
                # 如果单个句子过大，按字符强制分割
                if sentence_tokens > self.config.max_chunk_size:
                    char_chunks = self._split_by_characters(sentence, doc_id, metadata)
                    chunks.extend(char_chunks)
                    current_chunk = ""
                    current_tokens = 0
                else:
                    current_chunk = sentence
                    current_tokens = sentence_tokens
            else:
                if current_chunk:
                    current_chunk += "。" + sentence
                else:
                    current_chunk = sentence
                current_tokens += sentence_tokens
        
        # 处理最后剩余内容
        if current_chunk.strip():
            chunk = self._create_chunk(current_chunk, 0, doc_id, metadata)
            chunks.append(chunk)
        
        return chunks
    
    def _split_by_characters(self, text: str, doc_id: str, 
                            metadata: Dict[str, Any] = None) -> List[DocumentChunkWithMetadata]:
        """按字符强制分割"""
        chunks = []
        chunk_size_chars = self.config.chunk_size * 4  # token到字符的转换
        
        for i in range(0, len(text), chunk_size_chars):
            chunk_text = text[i:i + chunk_size_chars]
            if chunk_text.strip():
                chunk = self._create_chunk(chunk_text, i // chunk_size_chars, doc_id, metadata)
                chunks.append(chunk)
        
        return chunks
    
    def _create_chunk(self, text: str, chunk_index: int, doc_id: str, 
                     metadata: Dict[str, Any] = None) -> DocumentChunkWithMetadata:
        """创建文档块"""
        # 清理文本
        text = text.strip()
        
        # 计算token数量
        token_count = self._count_tokens(text)
        
        # 合并元数据
        chunk_metadata = metadata.copy() if metadata else {}
        chunk_metadata.update({
            "chunk_index": chunk_index,
            "token_count": token_count,
            "char_count": len(text)
        })
        
        # 创建文档块
        chunk = DocumentChunkWithMetadata(
            doc_id=doc_id,
            content=text,
            chunk_index=chunk_index,
            token_count=token_count,
            metadata=chunk_metadata
        )
        
        return chunk
    
    def _validate_chunks(self, chunks: List[DocumentChunkWithMetadata]) -> bool:
        """验证chunks是否满足要求"""
        if not chunks:
            return False
        
        # 检查每个chunk的大小
        for chunk in chunks:
            if chunk.token_count < self.config.min_chunk_size:
                continue  # 小chunks可以接受
            if chunk.token_count > self.config.max_chunk_size:
                return False  # 过大的chunk不接受
        
        return True
    
    def merge_small_chunks(self, chunks: List[DocumentChunkWithMetadata], 
                          doc_id: str) -> List[DocumentChunkWithMetadata]:
        """合并过小的chunks"""
        if len(chunks) <= 1:
            return chunks
        
        merged_chunks = []
        current_chunk = None
        current_tokens = 0
        
        for chunk in chunks:
            if chunk.token_count < self.config.min_chunk_size:
                # 小chunk，尝试合并
                if current_chunk is None:
                    current_chunk = chunk
                    current_tokens = chunk.token_count
                elif current_tokens + chunk.token_count <= self.config.chunk_size:
                    # 可以合并
                    current_chunk.content += "\n\n" + chunk.content
                    current_chunk.token_count += chunk.token_count
                    current_tokens += chunk.token_count
                    current_chunk.metadata.update(chunk.metadata)
                else:
                    # 无法合并，保存当前chunk
                    merged_chunks.append(current_chunk)
                    current_chunk = chunk
                    current_tokens = chunk.token_count
            else:
                # 正常大小的chunk
                if current_chunk is not None:
                    merged_chunks.append(current_chunk)
                    current_chunk = None
                    current_tokens = 0
                
                merged_chunks.append(chunk)
        
        # 处理最后的chunk
        if current_chunk is not None:
            merged_chunks.append(current_chunk)
        
        return merged_chunks