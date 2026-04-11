"""
向量化模块
提供全局笔记的收集、向量化和验证功能

主要组件:
- NotesCollector: 全局笔记收集器
- GlobalNotesVectorizer: 向量化处理器
- VectorizationVerifier: 验证器
- utils: 工具函数

使用方式:
    from src.vectorization.collect_notes import NotesCollector
    from src.vectorization.vectorize_global_notes import GlobalNotesVectorizer
    from src.vectorization.verify_vectorization import VectorizationVerifier

一键启动:
    ./scripts/vectorize_all.sh
"""

__version__ = "1.0.0"
__all__ = [
    'collect_notes',
    'vectorize_global_notes',
    'verify_vectorization',
    'utils'
]
