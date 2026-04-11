"""
本地知识库全量向量化自动化系统 - API 模块
版本: v1.0
日期: 2026-03-01
"""

__version__ = "1.0.0"

from .server import create_app, run_server
from .schemas import (
    SearchRequest,
    SearchResponse,
    ErrorResponse,
    SuccessResponse
)

__all__ = [
    "__version__",
    "create_app",
    "run_server",
    "SearchRequest",
    "SearchResponse",
    "ErrorResponse",
    "SuccessResponse",
]
