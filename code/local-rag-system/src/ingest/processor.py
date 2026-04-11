from typing import List, Dict, Any, Optional
from pathlib import Path
import time
from datetime import datetime

from ..models import DocumentWithChunks, IngestRequest, IngestResponse, ProcessingStatus, DataSource
from ..config import config
from .parsers import ExcelParser, PPTParser, CodeParser, MarkdownParser
from .chunker import TextChunker, ChunkConfig

class DocumentProcessor:
    """文档处理器主类"""
    
    def __init__(self, processor_config: Dict[str, Any] = None):
        self.config = processor_config or config.get('document', {})
        
        # 初始化解析器
        self.parsers = self._init_parsers()
        
        # 初始化文本切分器
        chunk_config = ChunkConfig(
            chunk_size=self.config.get('chunk_size', 750),
            chunk_overlap=self.config.get('chunk_overlap', 0.15),
            min_chunk_size=self.config.get('min_chunk_size', 50),
            max_chunk_size=self.config.get('max_chunk_size', 1500)
        )
        self.chunker = TextChunker(chunk_config)
        
        # 支持的文件类型
        self.supported_formats = self.config.get('supported_formats', [
            'pdf', 'xlsx', 'pptx', 'md', 'docx', 'txt', 'html'
        ])
    
    def _init_parsers(self) -> Dict[str, Any]:
        """初始化解析器"""
        parsers = {}
        
        # Excel解析器
        excel_config = self.config.get('excel', {})
        parsers['excel'] = ExcelParser(excel_config)
        
        # PPT解析器
        ppt_config = self.config.get('ppt', {})
        parsers['ppt'] = PPTParser(ppt_config)
        
        # 代码解析器
        code_config = self.config.get('code', {})
        parsers['code'] = CodeParser(code_config)
        
        # Markdown解析器
        parsers['markdown'] = MarkdownParser()
        
        return parsers
    
    def process_request(self, request: IngestRequest) -> IngestResponse:
        """处理文档摄入请求"""
        start_time = time.time()
        
        successful = 0
        failed = 0
        failed_files = []
        
        # 处理每个文件
        for file_path in request.file_paths:
            try:
                # 检查文件是否存在
                if not Path(file_path).exists():
                    raise FileNotFoundError(f"File not found: {file_path}")
                
                # 检查文件类型是否支持
                if not self._is_supported_file(file_path):
                    raise ValueError(f"Unsupported file type: {file_path}")
                
                # 处理文件
                document = self.process_file(file_path, request.force_reprocess)
                
                if document.processing_status == ProcessingStatus.COMPLETED:
                    successful += 1
                else:
                    failed += 1
                    failed_files.append({
                        "file_path": file_path,
                        "error": "Processing failed"
                    })
                
            except Exception as e:
                failed += 1
                failed_files.append({
                    "file_path": file_path,
                    "error": str(e)
                })
        
        processing_time = time.time() - start_time
        
        # 构建响应
        response = IngestResponse(
            batch_id=request.batch_id,
            total_files=len(request.file_paths),
            successful=successful,
            failed=failed,
            failed_files=failed_files,
            processing_time_seconds=processing_time,
            message=f"Processed {successful} files successfully, {failed} failed"
        )
        
        return response
    
    def process_file(self, file_path: str, force_reprocess: bool = False) -> DocumentWithChunks:
        """处理单个文件"""
        try:
            # 确定文件类型
            data_source = self._get_data_source(file_path)
            
            # 选择合适的解析器
            parser = self._get_parser(data_source)
            
            if not parser:
                raise ValueError(f"No parser available for file type: {data_source}")
            
            # 解析文件
            document = parser.parse(file_path)
            
            # 如果解析器没有生成chunks，使用通用文本切分
            if not document.chunks:
                document = self._fallback_to_text_chunking(file_path, document.doc_id)
            
            return document
            
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
            # 创建失败的文档对象
            doc_id = f"failed_{Path(file_path).stem}"
            failed_doc = DocumentWithChunks(
                doc_id=doc_id,
                file_path=file_path,
                file_type=DataSource.CODE,  # 默认类型
                file_size_bytes=0,
                sha256_hash="",
                processing_status=ProcessingStatus.FAILED
            )
            return failed_doc
    
    def _is_supported_file(self, file_path: str) -> bool:
        """检查文件类型是否支持"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_formats
    
    def _get_data_source(self, file_path: str) -> DataSource:
        """根据文件扩展名确定数据源类型"""
        file_ext = Path(file_path).suffix.lower()
        
        ext_mapping = {
            '.xlsx': DataSource.EXCEL,
            '.xls': DataSource.EXCEL,
            '.pptx': DataSource.PPT,
            '.ppt': DataSource.PPT,
            '.md': DataSource.MARKDOWN,
            '.markdown': DataSource.MARKDOWN,
            '.pdf': DataSource.CODE,  # 暂时归类为代码，实际应该有PDF解析器
            '.docx': DataSource.CODE,
            '.txt': DataSource.CODE,
            '.html': DataSource.CODE
        }
        
        # 代码文件扩展名
        code_exts = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.go', '.rs', '.jsx', '.tsx']
        if file_ext in code_exts:
            return DataSource.CODE
        
        return ext_mapping.get(file_ext, DataSource.CODE)
    
    def _get_parser(self, data_source: DataSource):
        """根据数据源类型获取解析器"""
        parser_mapping = {
            DataSource.EXCEL: self.parsers['excel'],
            DataSource.PPT: self.parsers['ppt'],
            DataSource.CODE: self.parsers['code'],
            DataSource.MARKDOWN: self.parsers['markdown']
        }
        
        return parser_mapping.get(data_source)
    
    def _fallback_to_text_chunking(self, file_path: str, doc_id: str) -> DocumentWithChunks:
        """回退到通用文本切分"""
        try:
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
            except:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
        
        # 切分文本
        chunks = self.chunker.chunk_text(content, doc_id, {
            "file_path": file_path,
            "fallback_method": True
        })
        
        # 创建文档对象
        document = DocumentWithChunks(
            doc_id=doc_id,
            file_path=file_path,
            file_type=DataSource.CODE,
            file_size_bytes=Path(file_path).stat().st_size,
            sha256_hash="",  # 实际应该计算
            chunks=chunks,
            processing_status=ProcessingStatus.COMPLETED
        )
        
        return document
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的文件格式列表"""
        return self.supported_formats.copy()
    
    def get_parser_info(self) -> Dict[str, Any]:
        """获取解析器信息"""
        return {
            "excel": {
                "enabled": True,
                "config": self.config.get('excel', {})
            },
            "ppt": {
                "enabled": True,
                "config": self.config.get('ppt', {})
            },
            "code": {
                "enabled": True,
                "config": self.config.get('code', {})
            },
            "markdown": {
                "enabled": True,
                "config": {}
            }
        }