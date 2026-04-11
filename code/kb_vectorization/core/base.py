"""
本地知识库全量向量化自动化系统 - 基类定义
版本: v1.0
日期: 2026-03-01
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
import uuid


@dataclass
class FileInfo:
    """文件信息数据类"""
    path: str                      # 文件路径
    name: str                      # 文件名
    type: str                      # 文件类型
    category: str                  # 业务分类
    size: int                      # 文件大小（字节）
    modified_time: datetime        # 修改时间
    is_valid: bool = True          # 是否有效
    file_hash: Optional[str] = None  # 文件哈希（用于检测变化）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "path": self.path,
            "name": self.name,
            "type": self.type,
            "category": self.category,
            "size": self.size,
            "modified_time": self.modified_time.isoformat(),
            "is_valid": self.is_valid,
            "file_hash": self.file_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileInfo":
        """从字典创建"""
        if isinstance(data["modified_time"], str):
            data["modified_time"] = datetime.fromisoformat(data["modified_time"])
        return cls(**data)


@dataclass
class VectorChunk:
    """向量分块数据类"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str = ""
    file_name: str = ""
    category: str = ""
    chunk_index: int = 0
    chunk_text: str = ""
    vector: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "category": self.category,
            "chunk_index": self.chunk_index,
            "chunk_text": self.chunk_text,
            "vector": self.vector,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorChunk":
        """从字典创建"""
        return cls(**data)


@dataclass
class SearchResult:
    """搜索结果数据类"""
    id: str
    file_path: str
    file_name: str
    category: str
    chunk_index: int
    chunk_text: str
    similarity: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "category": self.category,
            "chunk_index": self.chunk_index,
            "chunk_text": self.chunk_text,
            "similarity": float(self.similarity),
            "metadata": self.metadata
        }


@dataclass
class ScanResult:
    """扫描结果数据类"""
    total_files: int
    total_size: int
    files: List[FileInfo]
    by_type: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    scan_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_files": self.total_files,
            "total_size": self.total_size,
            "files": [f.to_dict() for f in self.files],
            "by_type": self.by_type,
            "by_category": self.by_category,
            "scan_time": self.scan_time
        }


@dataclass
class FileEvent:
    """文件事件数据类"""
    event_type: str  # 'created', 'modified', 'deleted', 'moved'
    src_path: str
    dest_path: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    file_info: Optional[FileInfo] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "event_type": self.event_type,
            "src_path": self.src_path,
            "dest_path": self.dest_path,
            "timestamp": self.timestamp.isoformat()
        }
        if self.file_info:
            result["file_info"] = self.file_info.to_dict()
        return result


@dataclass
class ProcessingStats:
    """处理统计数据类"""
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    total_chunks: int = 0
    processed_chunks: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    memory_peak: float = 0.0  # GB

    @property
    def duration(self) -> Optional[float]:
        """处理时长（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_files == 0:
            return 0.0
        return self.processed_files / self.total_files

    @property
    def avg_time_per_file(self) -> Optional[float]:
        """平均每个文件处理时间（秒）"""
        if self.processed_files == 0 or not self.duration:
            return None
        return self.duration / self.processed_files

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "failed_files": self.failed_files,
            "total_chunks": self.total_chunks,
            "processed_chunks": self.processed_chunks,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "success_rate": self.success_rate,
            "avg_time_per_file": self.avg_time_per_file,
            "memory_peak": self.memory_peak
        }


class VectorStore(ABC):
    """向量存储基类"""

    @abstractmethod
    def add_vectors(self, chunks: List[VectorChunk]) -> bool:
        """添加向量"""
        pass

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """搜索向量"""
        pass

    @abstractmethod
    def delete_by_file(self, file_path: str) -> int:
        """删除指定文件的所有向量"""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        pass

    @abstractmethod
    def clear(self) -> bool:
        """清空向量库"""
        pass


class FileParser(ABC):
    """文件解析器基类"""

    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """判断是否可以解析该文件"""
        pass

    @abstractmethod
    def parse(self, file_path: str) -> List[str]:
        """解析文件，返回文本块列表"""
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """支持的文件扩展名"""
        pass
