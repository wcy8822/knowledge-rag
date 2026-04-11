"""
本地知识库全量向量化自动化系统 - API 数据模型
版本: v1.0
日期: 2026-03-01
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from enum import Enum


class SearchType(str, Enum):
    """搜索类型枚举"""
    KEYWORD = "keyword"
    VECTOR = "vector"
    HYBRID = "hybrid"


@dataclass
class SearchRequest:
    """搜索请求"""
    query: str                      # 查询文本
    top_k: Optional[int] = None      # 返回结果数
    search_type: str = "hybrid"       # 搜索类型
    filters: Optional[Dict[str, Any]] = None  # 过滤条件

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class SearchResultItem:
    """搜索结果项"""
    id: str                         # 向量ID
    file_path: str                  # 文件路径
    file_name: str                  # 文件名
    category: str                   # 分类
    chunk_index: int                # 块索引
    chunk_text: str                 # 块文本（预览）
    similarity: float               # 相似度
    metadata: Optional[Dict[str, Any]] = None  # 元数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class SearchResponse:
    """搜索响应"""
    success: bool                   # 是否成功
    query: str                      # 查询文本
    type: str                       # 搜索类型
    total: int                      # 结果数量
    query_time: float               # 查询耗时（秒）
    results: List[SearchResultItem]  # 结果列表
    message: Optional[str] = None   # 附加消息

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data["results"] = [r.to_dict() for r in self.results]
        return data


@dataclass
class ScanResponse:
    """扫描响应"""
    success: bool                   # 是否成功
    total_files: int                # 总文件数
    total_size: int                 # 总大小
    by_type: Dict[str, int]         # 按类型统计
    by_category: Dict[str, int]     # 按分类统计
    scan_time: Optional[float] = None  # 扫描耗时
    message: Optional[str] = None   # 附加消息

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class VectorizeResponse:
    """向量化响应"""
    success: bool                   # 是否成功
    processed_files: int            # 处理文件数
    total_chunks: int               # 生成块数
    failed_files: int               # 失败文件数
    duration: Optional[float] = None  # 处理耗时
    message: Optional[str] = None   # 附加消息

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class StatsResponse:
    """统计响应"""
    success: bool                   # 是否成功
    stats: Dict[str, Any]           # 统计数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class HealthResponse:
    """健康检查响应"""
    status: str                     # 状态
    version: str                    # 版本
    uptime: float                   # 运行时长（秒）
    components: Dict[str, str]      # 组件状态

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class ErrorResponse:
    """错误响应"""
    success: bool = False           # 固定为 False
    error: Optional[Dict[str, Any]] = None  # 错误详情

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class SuccessResponse:
    """成功响应"""
    success: bool = True            # 固定为 True
    message: Optional[str] = None   # 消息
    data: Optional[Dict[str, Any]] = None  # 数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


# 响应工厂函数
def create_error_response(code: str, message: str, details: Optional[str] = None) -> ErrorResponse:
    """
    创建错误响应

    Args:
        code: 错误代码
        message: 错误消息
        details: 错误详情

    Returns:
        错误响应
    """
    error_data = {"code": code, "message": message}
    if details:
        error_data["details"] = details

    return ErrorResponse(error=error_data)


def create_success_response(message: str, data: Optional[Dict[str, Any]] = None) -> SuccessResponse:
    """
    创建成功响应

    Args:
        message: 消息
        data: 数据

    Returns:
        成功响应
    """
    return SuccessResponse(message=message, data=data)


# 错误代码定义
class ErrorCode:
    """错误代码常量"""
    # 通用错误
    UNKNOWN_ERROR = "UNKNOWN"
    INVALID_REQUEST = "INVALID_REQUEST"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    NOT_FOUND = "NOT_FOUND"

    # 搜索错误
    SEARCH_FAILED = "SEARCH_FAILED"
    INVALID_QUERY = "INVALID_QUERY"
    INVALID_SEARCH_TYPE = "INVALID_SEARCH_TYPE"

    # 扫描错误
    SCAN_FAILED = "SCAN_FAILED"
    INVALID_DIRECTORY = "INVALID_DIRECTORY"

    # 向量化错误
    VECTORIZATION_FAILED = "VECTORIZATION_FAILED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"

    # 存储错误
    STORAGE_ERROR = "STORAGE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"

    # 权限错误
    ACCESS_DENIED = "ACCESS_DENIED"
    FORBIDDEN = "FORBIDDEN"
