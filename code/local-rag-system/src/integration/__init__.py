"""
Local RAG 系统集成层
融合原有RAG系统 + 向量化模块

这个模块提供了统一的接口，整合了：
- 原有Local RAG系统的所有能力（向量存储、检索、API）
- 新增向量化模块的所有功能（收集、处理、验证）
- 完整的版本管理和配置系统

版本: 1.1.0
发布日期: 2025-01-27
"""

__version__ = "1.1.0"
__release_date__ = "2025-01-27"

from src.integration.unified import LocalRAGSystem
from src.integration.version import VersionManager
from src.integration.config import ConfigManager

__all__ = [
    'LocalRAGSystem',
    'VersionManager',
    'ConfigManager',
]
