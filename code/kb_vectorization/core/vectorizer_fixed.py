#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地知识库全量向量化自动化系统 - 向量化模块（内存修复版本）
版本: v1.0.1
日期: 2026-03-01

**修复内容**:
1. 修复 MarkdownParser._preprocess 缺失问题
2. 添加批量处理方法
3. 优化内存使用
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .base import FileInfo, VectorChunk, ProcessingStats
from .config import Config
from .utils import (
    setup_logger_fixed,
    get_memory_usage,
    sanitize_text,
    split_text_into_chunks,
    get_file_extension,
    safe_file_read,
    format_file_size,
    md5_vector
    force_gc,
    timeit,
    retry,
    ProgressTracker,
)


# Logger 单例（已从 utils_fixed 导入）
logger = setup_logger_fixed(__name__)


# ==================== 文件解析器基类 ====================

class FileParser(ABC):
    """文件解析器基类"""

    def __init__(self, config: Config):
        """
        初始化文件解析器

        Args:
            config: 配置对象
        """
        self.config = config
        self.logger = setup_logger_fixed(__name__)
        self.logger.debug(f"{__class__.__name__} 初始化完成")

    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """
        判断是否可以解析该文件

        Args:
            file_path: 文件路径

        Returns:
            是否支持
        """
        pass

    @abstractmethod
    def parse(self, file_path: str) -> List[str]:
        """
        解析文件，返回文本块列表

        Args:
            file_path: 文件路径

        Returns:
            文本块列表
        """
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """支持的文件扩展名"""
        pass


# ==================== Markdown 文件解析器 ====================

class MarkdownParser(FileParser):
    """Markdown 文件解析器（修复版）"""

    def __init__(self, config: Config):
        super().__init__(config)
        self.preprocessing_rules = config.get("vectorize.md_preprocessing", {})

    @property
    def supported_extensions(self) -> List[str]:
        return [".md", ".markdown"]

    def can_parse(self, file_path: str) -> bool:
        ext = get_file_extension(file_path)
        return ext in self.supported_extensions

    def parse(self, file_path: str) -> List[str]:
        """
        解析 Markdown 文件
        """
        content = safe_file_read(file_path)
        if not content:
            self.logger.debug(f"文件为空: {file_path}")
            return []

        # 预处理
        processed = self._preprocess(content)

        # 分块
        chunks = split_text_into_chunks(
            processed,
            chunk_size=self.config.chunk_size,
            overlap=self.config.chunk_overlap,
            min_size=self.config.min_chunk_size
        )

        return chunks

    def _preprocess(self, text: str) -> str:
        """
        预处理 Markdown 文本

        Args:
            text: Markdown 文本

        Returns:
            预处理后的文本
        """
        result = text

        # 移除 markdown 标记
        if self.preprocessing_rules.get("remove_md_syntax", True):
            # 移除标题标记
            result = re.sub(r'^#+\s+', '', result, flags=re.MULTILINE)
            # 移除加粗/斜体标记
            result = re.sub(r'\*\*(.+?)\*\*', r'\1', result)
            result = re.sub(r'\*(.+?)\*', r'\1', result)
            result = re.sub(r'~~(.+?)~~', r'\1', result)
            # 移除链接标记 [text](url)
            result = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', result)
            # 移除代码块标记
            if self.preprocessing_rules.get("remove_code_block_syntax", True):
                result = re.sub(r'```[\w]*\n', '', result)
                result = re.sub(r'```', '', result)
                result = re.sub(r'`([^`]+)`', r'\1', result)
                result = re.sub(r'`([^`]+)`', r'\1', result)
                # 移除代码块标记
                result = re.sub(r'`([^`]+)`', r'\1', result)

        # 移除 HTML 标签
        if self.preprocessing_rules.get("remove_html_tags", True):
            result = re.sub(r'<[^>]+>', '', result)

        # 合并连续空行
        if self.preprocessing_rules.get("merge_empty_lines", True):
            result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)

        # 处理表格
        if self.preprocessing_rules.get("process_tables", True):
            result = self._process_tables(result)

        return result.strip()

    def _process_tables(self, text: str) -> str:
        """简单处理表格"""
        lines = text.split('\n')
        result = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # 检测表格分隔线
            if re.match(r'^\|?[\s\-:]+\|?$', line) and i > 0:
                # 前一行是表头
                header = lines[i - 1]
                table_data = []

                # 收集表格行
                j = i + 1
                while j < len(lines) and '|' in lines[j]:
                    table_data.append(lines[j])
                    j += 1

                # 将表格转换为可读文本
                result.append(header)
                for row in table_data:
                    result.append(row)
                i = j

            else:
                result.append(line)
            i += 1

        return '\n'.join(result)


# ==================== SQL 文件解析器 ====================

class SQLParser(FileParser):
    """SQL 文件解析器"""

    def __init__(self, config: Config):
        super().__init__(config)
        self.logger = setup_logger_fixed(__name__)

    @property
    def supported_extensions(self) -> List[str]:
        return [".sql"]

    def can_parse(self, file_path: str) -> bool:
        ext = get_file_extension(file_path)
        return ext in self.supported_extensions

    def parse(self, file_path: str) -> List[str]:
        """
        解析 SQL 文件
        """
        content = safe_file_read(file_path)
        if not content:
            self.logger.debug(f"SQL 文件为空: {file_path}")
            return []

        # 移除注释
        content = self._remove_comments(content)

        # 分块（按语句）
        chunks = self._split_statements(content)

        # 进一步分块大的语句
        result = []
        for chunk in chunks:
            if len(chunk) > self.config.chunk_size:
                result.extend(split_text_into_chunks(
                    chunk,
                    chunk_size=self.config.chunk_size,
                    overlap=self.config.chunk_overlap,
                    min_size=self.config.min_chunk_size
                ))
            else:
                result.append(chunk)

        return [c.strip() for c in result if c.strip()]

    def _remove_comments(self, sql: str) -> str:
        """
        移除 SQL 注释
        """
        # 移除单行注释
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)

        # 移除多行注释
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)

        return sql


# ==================== 代码文件解析器 ====================

class CodeParser(FileParser):
    """代码文件解析器（修复版）"""

    def __init__(self, config: Config):
        super().__init__(config)
        self.current_path = None  # 修复：添加此属性

    @property
    def supported_extensions(self) -> List[str]:
        return [
            ".py", ".js", ".ts", ".jsx", ".tsx",
            ".java", ".c", ".cpp", ".h", ".hpp",
            ".go", ".rs", ".rb", ".php", ".sh"
        ]

    def can_parse(self, file_path: str) -> bool:
        ext = get_file_extension(file_path)
        return ext in self.supported_extensions

    def parse(self, file_path: str) -> List[str]:
        """
        解析代码文件

        Args:
            file_path: 文件路径

        Returns:
            文本块列表
        """
        self.current_path = file_path  # 修复：设置当前路径

        content = safe_file_read(file_path)
        if not content:
            self.logger.debug(f"文件为空: {file_path}")
            return []

        # 按函数/类分块
        chunks = self._split_by_structure(content)

        return chunks

    def _split_by_structure(self, code: str) -> List[str]:
        """按代码结构分块"""
        ext = get_file_path if self.current_path else ""

        # Python 特殊处理
        if ext == ".py":
            return self._split_python(code)

        # 默认按行数分块
        lines = code.split('\n')
        chunks = []
        i = 0

        while i < len(lines):
            chunk_lines = lines[i:i + 50]  # 每块约 50 行
            chunk = '\n'.join(chunk_lines)
            if chunk.strip():
                chunks.append(chunk)
            i += 50

        return chunks

    def _split_python(self, code: str) -> List[str]:
        """
        按函数/类定义分割 Python 代码
        """
        import re

        # 按类/类定义分割
        pattern = r'^(class|def|async def)\s+\w+.*?:'

        chunks = re.split(pattern, flags=re.MULTILINE)

        # 重新组合（保留定义行）
        result = []
        for i in range(0, len(chunks), 2):
            if i + 1 < len(chunks):
                result.append(chunks[i] + chunks[i + 1])
            elif i < len(chunks):
                result.append(chunks[i])

        return [c for c in result if c.strip()]

    def _split_by_structure(self, code: str) -> List[str]:
        """
        按代码结构分块（默认实现）

        默认按行数分块，每块约 50 行
        """
        lines = code.split('\n')
        chunks = []
        i = 0

        while i < len(lines):
            chunk_lines = lines[i:i + 50]  # 每块约 50 行
            chunk = '\n'.join(chunk_lines)
            if chunk.strip():
                chunks.append(chunk)
            i += 50

        return [c for c in chunks if c.strip()]


# ==================== 主向量化器类 ====================

class Vectorizer:
    """文档向量化器（内存优化版）"""

    def __init__(self, config: Config):
        """
        初始化向量化器

        Args:
            config: 配置对象
        """
        self.config = config
        self.logger = setup_logger_fixed(__name__)

        # 注册解析器
        self._parsers: List[FileParser] = [
            MarkdownParser(self.config),
            SQLParser(self.config),
            CodeParser(self.config),
        ]

        # 统计信息
        self.stats = ProcessingStats()

        # 向量化函数（使用固定实现）
        self._vectorize_fn: Callable[[str], List[float]] = md5_vector

    @property
    def vector_dim(self) -> int:
        """向量维度"""
        return self.config.vector_dim

    @property
    def batch_size(self) -> int:
        """批次大小"""
        return self.config.batch_size

    @property
    def mvp_batch_size(self) -> int:
        """MVP 批次大小"""
        return self.config.mvp_batch_size

    @property
    def chunk_size(self) -> int:
        """分块大小"""
        return self.config.chunk_size

    @property
    def chunk_overlap(self) -> int:
        """重叠大小"""
        return self.config.chunk_overlap

    @property
    def min_chunk_size(self) -> int:
        """最小块大小"""
        return self.config.min_chunk_size

    def register_parser(self, parser: FileParser) -> None:
        """
        注册文件解析器

        Args:
            parser: 解析器对象
        """
        self._parsers.append(parser)
        self.logger.info(f"注册解析器: {parser.__class__.__name__}")

    def set_vectorize_fn(self, fn: Callable[[str], List[float]]) -> None:
        """
        设置向量化函数

        Args:
            fn: 向量化函数，接受文本返回向量
        """
        self._vectorize_fn = fn

    def vectorize_file(self, file_path: str, file_info: Optional[FileInfo] = None) -> List[VectorChunk]:
        """
        向量化单个文件

        Args:
            file_path: 文件路径
            file_info: 文件信息对象

        Returns:
            向量块列表
        """
        # 获取解析器
        parser = self._get_parser(file_path)
        if not parser:
            self.logger.warning(f"不支持的文件类型: {file_path}")
            return []

        # 解析文件
        try:
            text_chunks = parser.parse(file_path)
            self.logger.debug(f"文件 {file_path} 解析出 {len(text_chunks)} 个文本块")
        except Exception as e:
            self.logger.error(f"解析文件失败 {file_path}: {e}")
            return []

        if not text_chunks:
            self.logger.warning(f"文件内容为空: {file_path}")
            return []

        # 获取文件信息
        if file_info is None:
            file_name = os.path.basename(file_path)
            category = self.config.classify(file_path)
            file_type = get_file_extension(file_path)
        else:
            file_name = file_info.name
            category = file_info.category
            file_type = file_info.type

        # 向量化每个块
        vector_chunks = []

        for i, text_chunk in enumerate(text_chunks):
            # 限制块数量
            if i >= self.config.max_chunks_per_file:
                self.logger.warning(f"文件块数超限，截断: {file_path}")
                break

            # 跳过过短的块
            if len(text_chunk) < self.config.min_chunk_size:
                continue

            # 向量化
            try:
                vector = self._vectorize_fn(text_chunk, dim=self.config.vector_dim)
            except Exception as e:
                self.logger.error(f"向量化失败 {file_path} chunk {i}: {e}")
                continue

            # 创建向量块
            vector_chunk = VectorChunk(
                file_path=file_path,
                file_name=file_name,
                category=category,
                chunk_index=i,
                chunk_text=text_chunk,
                vector=vector,
                metadata={
                    "file_type": file_type,
                    "chunk_size": len(text_chunk),
                    "vectorized_at": datetime.now().isoformat()
                }
            )

            vector_chunks.append(vector_chunk)

        self.logger.debug(f"文件 {file_path} 向量化完成，生成 {len(vector_chunks)} 个向量块")
        return vector_chunks

    def vectorize_batch(
        self,
        files: List[str],
        batch_size: Optional[int] = None
    ) -> Tuple[List[VectorChunk], ProcessingStats]:
        """
        批量向量化

        Args:
            files: 文件路径列表
            batch_size: 批次大小，默认从配置读取

        Returns:
            (向量块列表, 处理统计)
        """
        batch_size = batch_size or self.batch_size
        stats = ProcessingStats(total_files=len(files), start_time=datetime.now())

        all_chunks: List[VectorChunk] = []

        # 分批处理
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            self.logger.info(f"处理批次 {i//batch_size + 1}/{(len(files)-1)//batch_size + 1}, 文件数: {len(batch)}")

            # 处理批次中的每个文件
            for file_path in batch:
                try:
                    chunks = self.vectorize_file(file_path)
                    if chunks:
                        all_chunks.extend(chunks)
                        stats.processed_files += 1
                        stats.processed_chunks += len(chunks)
                    else:
                        stats.failed_files += 1
                except Exception as e:
                    self.logger.error(f"处理文件失败 {file_path}: {e}")
                    stats.failed_files += 1

                stats.total_chunks += len(chunks) if 'chunks' in locals() else 0

            # 检查内存
            current_mem = get_memory_usage()
            stats.memory_peak = max(stats.memory_peak, current_mem)

            if not check_memory(self.config.memory_limit, raise_on_exceed=False):
                self.logger.warning(f"内存接近上限 {current_mem:.2f}GB，释放内存")
                force_gc()

        stats.end_time = datetime.now()
        self.logger.info(
            f"批量向量化完成: "
            f"处理 {stats.processed_files}/{stats.total_files} 文件, "
            f"生成 {stats.processed_chunks} 个向量, "
            f"成功率: {stats.success_rate:.1%}, "
            f"耗时 {stats.duration:.2f}s"
        )

        return all_chunks, stats

    def vectorize_mvp_batch(
        self,
        files: List[str],
        file_infos: Optional[List[FileInfo]] = None
    ) -> Tuple[List[VectorChunk], ProcessingStats]:
        """
        MVP 小批量向量化（用于测试）

        Args:
            files: 文件路径列表
            file_infos: 文件信息列表

        Returns:
            (向量块列表, 处理统计)
        """
        return self.vectorize_batch(files, self.config.mvp_batch_size)

    def _get_parser(self, file_path: str) -> Optional['FileParser']:
        """
        获取对应的解析器

        Args:
            file_path: 文件路径

        Returns:
            解析器对象，不支持返回 None
        """
        for parser in self._parsers:
            if parser.can_parse(file_path):
                return parser
        return None

    def get_memory_usage(self) -> float:
        """
        获取当前进程的内存使用量（GB）

        Returns:
            内存使用量（GB）
        """
        return get_memory_usage()

    def get_stats(self) -> ProcessingStats:
        """
        获取处理统计

        Returns:
            处理统计对象
        """
        return self.stats


# ==================== 快捷函数 ====================

def quick_vectorize(file_path: str, vector_dim: int = 384) -> List[VectorChunk]:
    """
    快速向量化单个文件（独立版本）

    Args:
        file_path: 文件路径
        vector_dim: 向量维度

    Returns:
        向量块列表
    """
    from .config import Config

    config = Config()
    config.set("vectorize.vector_dim", vector_dim)

    vectorizer = Vectorizer(config)
    return vectorizer.vectorize_file(file_path)


def quick_batch_vectorize(files: List[str]) -> List[VectorChunk]:
    """
    快速批量向量化

    Args:
        files: 文件路径列表

    Returns:
        向量块列表
    """
    from .config import Config
    from .core.config import Config

    config = Config()
    vectorizer = Vectorizer(config)

    chunks, _ = vectorizer.vectorize_batch(files)
    return chunks


__all__ = [
    # 解析器
    "FileParser",
    "MarkdownParser",
    "SQLParser",
    "CodeParser",
    # 向量化器
    "Vectorizer",
    # 快捷函数
    "quick_vectorize",
    "quick_batch_vectorize",
]
