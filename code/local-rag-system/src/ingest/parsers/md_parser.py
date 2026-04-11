from typing import List, Dict, Any, Optional
from pathlib import Path
import re
from markdown import markdown
from bs4 import BeautifulSoup

from .base_parser import BaseParser
from ...models.document import DocumentWithChunks, DocumentChunkWithMetadata, DataSource

class MarkdownParser(BaseParser):
    """Markdown文件解析器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.chunk_size = self.config.get('chunk_size', 750)
        self.chunk_overlap = self.config.get('chunk_overlap', 0.15)
        self.min_chunk_size = 100
    
    def can_parse(self, file_path: str) -> bool:
        """检查是否为Markdown文件"""
        return Path(file_path).suffix.lower() in ['.md', '.markdown']
    
    def parse(self, file_path: str) -> DocumentWithChunks:
        """解析Markdown文件"""
        doc_id = self._generate_doc_id(file_path)
        file_size = self._get_file_size(file_path)
        file_hash = self._calculate_file_hash(file_path)
        
        # 创建文档对象
        document = DocumentWithChunks(
            doc_id=doc_id,
            file_path=file_path,
            file_type=DataSource.MARKDOWN,
            file_size_bytes=file_size,
            sha256_hash=file_hash
        )
        
        try:
            # 读取和解析Markdown文件
            chunks = self._parse_markdown_file(file_path, doc_id)
            document.chunks = chunks
            document.processing_status = "completed"
            
        except Exception as e:
            document.processing_status = "failed"
            print(f"Error parsing Markdown file {file_path}: {e}")
            raise
        
        return document
    
    def _parse_markdown_file(self, file_path: str, doc_id: str) -> List[DocumentChunkWithMetadata]:
        """解析Markdown文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
        
        # 按标题分割文档
        sections = self._split_by_headers(content)
        
        chunks = []
        chunk_index = 0
        
        for section in sections:
            # 进一步分割大段内容
            section_chunks = self._split_section_into_chunks(
                section, doc_id, chunk_index
            )
            chunks.extend(section_chunks)
            chunk_index += len(section_chunks)
        
        return chunks
    
    def _split_by_headers(self, content: str) -> List[Dict[str, Any]]:
        """按标题分割Markdown内容"""
        sections = []
        
        # 匹配标题的正则表达式
        header_pattern = r'^(#{1,6})\s+(.+)$'
        
        current_section = {
            'title': None,
            'level': 0,
            'content': '',
            'start_line': 0,
            'end_line': 0
        }
        
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            header_match = re.match(header_pattern, line)
            
            if header_match:
                # 保存当前section（如果有内容）
                if current_section['content'].strip():
                    current_section['end_line'] = line_num - 1
                    sections.append(current_section.copy())
                
                # 开始新的section
                current_section = {
                    'title': header_match.group(2).strip(),
                    'level': len(header_match.group(1)),
                    'content': line + '\n',
                    'start_line': line_num,
                    'end_line': line_num
                }
            else:
                # 添加到当前section
                current_section['content'] += line + '\n'
                current_section['end_line'] = line_num
        
        # 保存最后一个section
        if current_section['content'].strip():
            sections.append(current_section)
        
        return sections
    
    def _split_section_into_chunks(self, section: Dict[str, Any], 
                                  doc_id: str, start_chunk_index: int) -> List[DocumentChunkWithMetadata]:
        """将section分割为chunks"""
        content = section['content']
        title = section['title']
        level = section['level']
        start_line = section['start_line']
        
        # 估算token数量（简化：按字符数/4）
        estimated_tokens = len(content) // 4
        
        if estimated_tokens <= self.chunk_size:
            # 不需要分割，直接作为一个chunk
            chunk = self._create_markdown_chunk(
                content, title, level, start_line, start_chunk_index, doc_id
            )
            return [chunk]
        else:
            # 需要分割
            return self._split_long_content(
                content, title, level, start_line, start_chunk_index, doc_id
            )
    
    def _split_long_content(self, content: str, title: Optional[str], level: int,
                           start_line: int, start_chunk_index: int, doc_id: str) -> List[DocumentChunkWithMetadata]:
        """分割长内容"""
        chunks = []
        
        # 按段落分割
        paragraphs = self._split_into_paragraphs(content)
        
        current_chunk_content = ""
        current_chunk_size = 0
        chunk_index = start_chunk_index
        
        for paragraph in paragraphs:
            paragraph_size = len(paragraph) // 4  # 估算token数
            
            # 如果单个段落就超过限制，需要进一步分割
            if paragraph_size > self.chunk_size:
                # 先保存当前chunk
                if current_chunk_content.strip():
                    chunk = self._create_markdown_chunk(
                        current_chunk_content, title, level, start_line, 
                        chunk_index, doc_id
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    current_chunk_content = ""
                    current_chunk_size = 0
                
                # 分割长段落
                sub_chunks = self._split_long_paragraph(paragraph)
                for sub_chunk in sub_chunks:
                    chunk = self._create_markdown_chunk(
                        sub_chunk, title, level, start_line, 
                        chunk_index, doc_id
                    )
                    chunks.append(chunk)
                    chunk_index += 1
            else:
                # 检查是否超过chunk大小
                if current_chunk_size + paragraph_size > self.chunk_size:
                    # 保存当前chunk
                    if current_chunk_content.strip():
                        chunk = self._create_markdown_chunk(
                            current_chunk_content, title, level, start_line,
                            chunk_index, doc_id
                        )
                        chunks.append(chunk)
                        chunk_index += 1
                    
                    current_chunk_content = ""
                    current_chunk_size = 0
                
                # 添加到当前chunk
                current_chunk_content += paragraph + "\n\n"
                current_chunk_size += paragraph_size
        
        # 保存最后剩余内容
        if current_chunk_content.strip():
            chunk = self._create_markdown_chunk(
                current_chunk_content, title, level, start_line,
                chunk_index, doc_id
            )
            chunks.append(chunk)
        
        return chunks
    
    def _split_into_paragraphs(self, content: str) -> List[str]:
        """将内容分割为段落"""
        paragraphs = []
        current_paragraph = ""
        lines = content.split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            
            # 空行表示段落结束
            if not line_stripped:
                if current_paragraph.strip():
                    paragraphs.append(current_paragraph.strip())
                    current_paragraph = ""
            elif line.startswith('#'):
                # 标题也表示段落结束
                if current_paragraph.strip():
                    paragraphs.append(current_paragraph.strip())
                    current_paragraph = ""
                current_paragraph = line
            elif line.startswith('```'):
                # 代码块特殊处理
                if current_paragraph.strip():
                    paragraphs.append(current_paragraph.strip())
                    current_paragraph = ""
                current_paragraph = line
            else:
                current_paragraph += line + "\n"
        
        # 处理最后剩余内容
        if current_paragraph.strip():
            paragraphs.append(current_paragraph.strip())
        
        return paragraphs
    
    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """分割长段落"""
        chunks = []
        
        # 按句子分割
        sentences = re.split(r'[。！？;!?]', paragraph)
        
        current_chunk = ""
        current_size = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_size = len(sentence) // 4  # 估算token数
            
            if current_size + sentence_size > self.chunk_size:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                
                # 如果单个句子太长，按字符强制分割
                if sentence_size > self.chunk_size:
                    char_chunks = self._split_by_characters(sentence)
                    chunks.extend(char_chunks)
                    current_chunk = ""
                    current_size = 0
                else:
                    current_chunk = sentence
                    current_size = sentence_size
            else:
                if current_chunk:
                    current_chunk += sentence + "。"
                else:
                    current_chunk = sentence + "。"
                current_size += sentence_size
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_by_characters(self, text: str) -> List[str]:
        """按字符强制分割文本"""
        max_chars = self.chunk_size * 4  # token到字符的转换
        
        chunks = []
        for i in range(0, len(text), max_chars):
            chunk = text[i:i + max_chars]
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks
    
    def _create_markdown_chunk(self, content: str, title: Optional[str], level: int,
                             start_line: int, chunk_index: int, doc_id: str) -> DocumentChunkWithMetadata:
        """创建Markdown文档块"""
        # 清理内容
        content = content.strip()
        
        # 计算token数量
        token_count = len(content.split())
        
        # 创建元数据
        metadata = {
            "title": title,
            "header_level": level,
            "start_line": start_line,
            "chunk_index": chunk_index,
            "content_type": "markdown"
        }
        
        # 创建文档块
        chunk = DocumentChunkWithMetadata(
            doc_id=doc_id,
            content=content,
            chunk_index=chunk_index,
            token_count=token_count,
            metadata=metadata
        )
        
        return chunk
    
    def _generate_doc_id(self, file_path: str) -> str:
        """生成文档ID"""
        return f"md_{Path(file_path).stem}"