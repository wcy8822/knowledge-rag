"""
本地知识库全量向量化自动化系统 - 核心模块
版本: v1.0
日期: 2026-03-01
"""

__version__ = "1.0.0"
__author__ = "Claude (无人值守模式)"

from .base import FileInfo, VectorChunk, SearchResult
from .config import Config
from .scanner import FileScanner, ScanResult
from .vectorizer import Vectorizer
from .storage import VectorStore, ChromaStore, FaissStore
from .retriever import Retriever
from .updater import FileUpdater, FileEvent
from .utils import (
    setup_logger,
    check_memory,
    sanitize_text,
    format_file_size,
    get_file_hash
)

__all__ = [
    # 版本
    "__version__",
    "__author__",
    # 基类
    "FileInfo",
    "VectorChunk",
    "SearchResult",
    # 配置
    "Config",
    # 扫描
    "FileScanner",
    "ScanResult",
    # 向量化
    "Vectorizer",
    # 存储
    "VectorStore",
    "ChromaStore",
    "FaissStore",
    # 检索
    "Retriever",
    # 更新
    "FileUpdater",
    "FileEvent",
    # 工具
    "setup_logger",
    "check_memory",
    "sanitize_text",
    "format_file_size",
    "get_file_hash",
]
