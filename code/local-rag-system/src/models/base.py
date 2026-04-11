from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import uuid

class DataSource(str, Enum):
    EXCEL = "excel"
    PPT = "ppt"
    MARKDOWN = "markdown"
    CODE = "code"
    PDF = "pdf"
    DOCX = "docx"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class BaseDocument(BaseModel):
    """基础文档模型"""
    doc_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str
    file_type: DataSource
    file_size_bytes: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    sha256_hash: str
    embedding_version: str = "v20250126"
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    
    class Config:
        use_enum_values = True

class DocumentChunk(BaseModel):
    """文档块模型"""
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str
    content: str
    chunk_index: int
    token_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    
    class Config:
        use_enum_values = True