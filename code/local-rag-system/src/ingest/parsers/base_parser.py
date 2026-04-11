from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pathlib import Path
import hashlib

from ...models.document import DocumentWithChunks, DocumentChunkWithMetadata

class BaseParser(ABC):
    """解析器基类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """检查是否能解析指定文件"""
        pass
    
    @abstractmethod
    def parse(self, file_path: str) -> DocumentWithChunks:
        """解析文件，返回文档和块"""
        pass
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件SHA256哈希"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return ""
    
    def _get_file_size(self, file_path: str) -> int:
        """获取文件大小"""
        try:
            return Path(file_path).stat().st_size
        except Exception:
            return 0