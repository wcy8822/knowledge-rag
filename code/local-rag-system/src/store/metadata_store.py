from typing import List, Dict, Any, Optional, Union
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path

from ..models import DocumentWithChunks, DocumentChunkWithMetadata, ProcessingStatus
from ..config import config

logger = logging.getLogger(__name__)

class MetadataStore:
    """元数据存储管理"""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = Path(config.settings.metadata_dir) / "metadata.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._initialize_database()
    
    def _initialize_database(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 文档表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size_bytes INTEGER,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    sha256_hash TEXT,
                    embedding_version TEXT DEFAULT 'v20250126',
                    processing_status TEXT DEFAULT 'pending',
                    metadata TEXT,
                    chunk_count INTEGER DEFAULT 0
                )
            ''')
            
            # 文档块表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS document_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    token_count INTEGER DEFAULT 0,
                    metadata TEXT,
                    excel_metadata TEXT,
                    ppt_metadata TEXT,
                    code_metadata TEXT,
                    embedding_version TEXT DEFAULT 'v20250126',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (doc_id) REFERENCES documents (doc_id)
                )
            ''')
            
            # 索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_documents_file_path ON documents(file_path)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON document_chunks(doc_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_chunks_created_at ON document_chunks(created_at)
            ''')
            
            conn.commit()
    
    def save_document(self, document: DocumentWithChunks) -> bool:
        """保存文档和块"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 保存文档
                cursor.execute('''
                    INSERT OR REPLACE INTO documents 
                    (doc_id, file_path, file_type, file_size_bytes, created_at, updated_at,
                     sha256_hash, embedding_version, processing_status, metadata, chunk_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    document.doc_id,
                    document.file_path,
                    document.file_type.value,
                    document.file_size_bytes,
                    document.created_at.isoformat() if document.created_at else None,
                    document.updated_at.isoformat() if document.updated_at else None,
                    document.sha256_hash,
                    document.embedding_version,
                    document.processing_status.value,
                    json.dumps(document.metadata) if document.metadata else None,
                    len(document.chunks)
                ))
                
                # 保存文档块
                for chunk in document.chunks:
                    self._save_chunk(cursor, chunk, document.doc_id)
                
                conn.commit()
                logger.info(f"Saved document {document.doc_id} with {len(document.chunks)} chunks")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save document {document.doc_id}: {e}")
            return False
    
    def _save_chunk(self, cursor, chunk: DocumentChunkWithMetadata, doc_id: str):
        """保存单个文档块"""
        cursor.execute('''
            INSERT OR REPLACE INTO document_chunks
            (chunk_id, doc_id, content, chunk_index, token_count, metadata,
             excel_metadata, ppt_metadata, code_metadata, embedding_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            chunk.chunk_id,
            doc_id,
            chunk.content,
            chunk.chunk_index,
            chunk.token_count,
            json.dumps(chunk.metadata) if chunk.metadata else None,
            json.dumps(chunk.excel_metadata.dict()) if chunk.excel_metadata else None,
            json.dumps(chunk.ppt_metadata.dict()) if chunk.ppt_metadata else None,
            json.dumps(chunk.code_metadata.dict()) if chunk.code_metadata else None,
            getattr(chunk, 'embedding_version', 'v20250126')
        ))
    
    def get_document(self, doc_id: str) -> Optional[DocumentWithChunks]:
        """获取文档"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 获取文档信息
                cursor.execute('''
                    SELECT doc_id, file_path, file_type, file_size_bytes, created_at, updated_at,
                           sha256_hash, embedding_version, processing_status, metadata, chunk_count
                    FROM documents WHERE doc_id = ?
                ''', (doc_id,))
                
                doc_row = cursor.fetchone()
                if not doc_row:
                    return None
                
                # 获取文档块
                cursor.execute('''
                    SELECT chunk_id, content, chunk_index, token_count, metadata,
                           excel_metadata, ppt_metadata, code_metadata
                    FROM document_chunks WHERE doc_id = ?
                    ORDER BY chunk_index
                ''', (doc_id,))
                
                chunk_rows = cursor.fetchall()
                
                # 构建文档对象
                document = self._build_document_from_db(doc_row, chunk_rows)
                return document
                
        except Exception as e:
            logger.error(f"Failed to get document {doc_id}: {e}")
            return None
    
    def get_chunk(self, chunk_id: str) -> Optional[DocumentChunkWithMetadata]:
        """获取单个文档块"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT chunk_id, doc_id, content, chunk_index, token_count, metadata,
                           excel_metadata, ppt_metadata, code_metadata
                    FROM document_chunks WHERE chunk_id = ?
                ''', (chunk_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return self._build_chunk_from_db(row)
                
        except Exception as e:
            logger.error(f"Failed to get chunk {chunk_id}: {e}")
            return None
    
    def list_documents(self, status: Optional[ProcessingStatus] = None,
                     limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """列出文档"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = '''
                    SELECT doc_id, file_path, file_type, file_size_bytes, created_at,
                           updated_at, processing_status, chunk_count
                    FROM documents
                '''
                params = []
                
                if status:
                    query += ' WHERE processing_status = ?'
                    params.append(status.value)
                
                query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                documents = []
                for row in rows:
                    doc_info = {
                        'doc_id': row[0],
                        'file_path': row[1],
                        'file_type': row[2],
                        'file_size_bytes': row[3],
                        'created_at': row[4],
                        'updated_at': row[5],
                        'processing_status': row[6],
                        'chunk_count': row[7]
                    }
                    documents.append(doc_info)
                
                return documents
                
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []
    
    def search_documents(self, query: str, filters: Optional[Dict[str, Any]] = None,
                       limit: int = 50) -> List[DocumentChunkWithMetadata]:
        """搜索文档内容"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 构建搜索查询
                base_query = '''
                    SELECT chunk_id, doc_id, content, chunk_index, token_count, metadata,
                           excel_metadata, ppt_metadata, code_metadata
                    FROM document_chunks WHERE content LIKE ?
                '''
                params = [f'%{query}%']
                
                # 添加过滤条件
                if filters:
                    if 'file_types' in filters:
                        file_types = filters['file_types']
                        if file_types:
                            placeholders = ','.join(['?' for _ in file_types])
                            base_query += f'''
                                AND doc_id IN (
                                    SELECT doc_id FROM documents WHERE file_type IN ({placeholders})
                                )
                            '''
                            params.extend(file_types)
                    
                    if 'date_range' in filters:
                        date_range = filters['date_range']
                        if date_range.get('start'):
                            base_query += ' AND created_at >= ?'
                            params.append(date_range['start'])
                        if date_range.get('end'):
                            base_query += ' AND created_at <= ?'
                            params.append(date_range['end'])
                
                base_query += ' ORDER BY chunk_index LIMIT ?'
                params.append(limit)
                
                cursor.execute(base_query, params)
                rows = cursor.fetchall()
                
                chunks = []
                for row in rows:
                    chunk = self._build_chunk_from_db(row)
                    chunks.append(chunk)
                
                return chunks
                
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            return []
    
    def delete_document(self, doc_id: str) -> bool:
        """删除文档及其所有块"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 删除文档块
                cursor.execute('DELETE FROM document_chunks WHERE doc_id = ?', (doc_id,))
                
                # 删除文档
                cursor.execute('DELETE FROM documents WHERE doc_id = ?', (doc_id,))
                
                conn.commit()
                logger.info(f"Deleted document {doc_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False
    
    def update_document_status(self, doc_id: str, status: ProcessingStatus) -> bool:
        """更新文档处理状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE documents SET processing_status = ?, updated_at = ?
                    WHERE doc_id = ?
                ''', (status.value, datetime.utcnow().isoformat(), doc_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update document status {doc_id}: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 总文档数
                cursor.execute('SELECT COUNT(*) FROM documents')
                total_docs = cursor.fetchone()[0]
                
                # 按状态统计
                cursor.execute('''
                    SELECT processing_status, COUNT(*) 
                    FROM documents 
                    GROUP BY processing_status
                ''')
                status_counts = dict(cursor.fetchall())
                
                # 按类型统计
                cursor.execute('''
                    SELECT file_type, COUNT(*) 
                    FROM documents 
                    GROUP BY file_type
                ''')
                type_counts = dict(cursor.fetchall())
                
                # 总块数
                cursor.execute('SELECT COUNT(*) FROM document_chunks')
                total_chunks = cursor.fetchone()[0]
                
                # 平均块数
                avg_chunks = total_chunks / total_docs if total_docs > 0 else 0
                
                return {
                    'total_documents': total_docs,
                    'total_chunks': total_chunks,
                    'average_chunks_per_document': avg_chunks,
                    'status_distribution': status_counts,
                    'type_distribution': type_counts
                }
                
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
    
    def _build_document_from_db(self, doc_row, chunk_rows) -> DocumentWithChunks:
        """从数据库记录构建文档对象"""
        from ..models import DataSource
        
        # 解析文档元数据
        metadata = json.loads(doc_row[9]) if doc_row[9] else {}
        
        document = DocumentWithChunks(
            doc_id=doc_row[0],
            file_path=doc_row[1],
            file_type=DataSource(doc_row[2]),
            file_size_bytes=doc_row[3],
            created_at=datetime.fromisoformat(doc_row[4]) if doc_row[4] else None,
            updated_at=datetime.fromisoformat(doc_row[5]) if doc_row[5] else None,
            sha256_hash=doc_row[6],
            embedding_version=doc_row[7],
            processing_status=ProcessingStatus(doc_row[8]),
            metadata=metadata,
            chunks=[]
        )
        
        # 添加文档块
        for chunk_row in chunk_rows:
            chunk = self._build_chunk_from_db(chunk_row)
            document.chunks.append(chunk)
        
        return document
    
    def _build_chunk_from_db(self, row) -> DocumentChunkWithMetadata:
        """从数据库记录构建文档块对象"""
        # 解析元数据
        metadata = json.loads(row[4]) if row[4] else {}
        
        chunk = DocumentChunkWithMetadata(
            chunk_id=row[0],
            doc_id=row[1],
            content=row[2],
            chunk_index=row[3],
            token_count=row[4] if isinstance(row[4], int) else 0,
            metadata=metadata
        )
        
        # 解析特定元数据
        if row[5]:  # excel_metadata
            from ..models import ExcelMetadata
            chunk.excel_metadata = ExcelMetadata(**json.loads(row[5]))
        
        if row[6]:  # ppt_metadata
            from ..models import PPTMetadata
            chunk.ppt_metadata = PPTMetadata(**json.loads(row[6]))
        
        if row[7]:  # code_metadata
            from ..models import CodeMetadata
            chunk.code_metadata = CodeMetadata(**json.loads(row[7]))
        
        return chunk
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 检查数据库连接
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                test_query = cursor.fetchone()
                
            if not test_query or test_query[0] != 1:
                return {"status": "error", "message": "Database query failed"}
            
            # 获取统计信息
            stats = self.get_statistics()
            
            return {
                "status": "healthy",
                "database_path": str(self.db_path),
                "statistics": stats
            }
            
        except Exception as e:
            return {"status": "error", "message": f"Health check failed: {e}"}

# 全局元数据存储实例
metadata_store = MetadataStore()