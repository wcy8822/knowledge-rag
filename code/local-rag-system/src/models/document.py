from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from .base import BaseDocument, DocumentChunk, DataSource

class ExcelMetadata(BaseModel):
    sheet_name: str
    row_start: int
    row_end: int
    primary_key: Optional[str]
    column_count: int
    
class PPTMetadata(BaseModel):
    slide_number: int
    slide_title: Optional[str]
    has_notes: bool
    
class CodeMetadata(BaseModel):
    language: str
    file_path: str
    symbol: str
    signature: str
    line_start: int
    line_end: int
    symbol_type: str  # function, class, method
    
class DocumentChunkWithMetadata(DocumentChunk):
    """带特定元数据的文档块"""
    excel_metadata: Optional[ExcelMetadata] = None
    ppt_metadata: Optional[PPTMetadata] = None
    code_metadata: Optional[CodeMetadata] = None

class IngestRequest(BaseModel):
    """文档摄入请求"""
    file_paths: List[str]
    force_reprocess: bool = False
    batch_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    priority: int = Field(default=1, ge=1, le=5)  # 1-5, 5最高

class IngestResponse(BaseModel):
    """文档摄入响应"""
    batch_id: str
    total_files: int
    successful: int
    failed: int
    failed_files: List[Dict[str, str]] = Field(default_factory=list)
    processing_time_seconds: float
    message: str = "Ingestion completed"

class DocumentWithChunks(BaseDocument):
    """包含块的完整文档"""
    chunks: List[DocumentChunkWithMetadata] = Field(default_factory=list)