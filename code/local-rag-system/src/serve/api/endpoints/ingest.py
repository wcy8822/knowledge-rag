from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from typing import List, Dict, Any, Optional
import logging
import time
import uuid
import os
from pathlib import Path

from ...models import IngestRequest, IngestResponse
from ...ingest.processor import DocumentProcessor
from ...store.metadata_store import metadata_store
from ...config import config

logger = logging.getLogger(__name__)
router = APIRouter()

# 全局文档处理器实例
document_processor = DocumentProcessor(config.get('document', {}))

@router.post("/files", response_model=IngestResponse)
async def ingest_files(
    background_tasks: BackgroundTasks,
    file_paths: Optional[List[str]] = None,
    files: Optional[List[UploadFile]] = None,
    force_reprocess: bool = False,
    batch_id: Optional[str] = None
):
    """从文件路径或上传文件摄入文档"""
    start_time = time.time()
    
    try:
        # 生成批次ID
        if not batch_id:
            batch_id = str(uuid.uuid4())
        
        # 收集所有文件路径
        all_file_paths = []
        
        # 添加提供的文件路径
        if file_paths:
            all_file_paths.extend(file_paths)
        
        # 处理上传的文件
        if files:
            upload_dir = Path(config.settings.upload_dir)
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            for upload_file in files:
                # 验证文件类型
                if not document_processor._is_supported_file(upload_file.filename):
                    logger.warning(f"Unsupported file type: {upload_file.filename}")
                    continue
                
                # 保存上传的文件
                file_path = upload_dir / upload_file.filename
                with open(file_path, "wb") as buffer:
                    content = await upload_file.read()
                    buffer.write(content)
                
                all_file_paths.append(str(file_path))
                logger.info(f"Uploaded file: {upload_file.filename} -> {file_path}")
        
        if not all_file_paths:
            raise HTTPException(status_code=400, detail="No valid files provided")
        
        # 创建摄入请求
        request = IngestRequest(
            file_paths=all_file_paths,
            force_reprocess=force_reprocess,
            batch_id=batch_id
        )
        
        # 处理文档
        response = document_processor.process_request(request)
        
        # 在后台任务中保存到元数据存储
        background_tasks.add_task(
            _save_processed_documents,
            request.file_paths,
            response.successful,
            response.failed_files
        )
        
        processing_time = time.time() - start_time
        
        logger.info(f"Batch {batch_id} completed in {processing_time:.2f}s: "
                   f"{response.successful} successful, {response.failed} failed")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during ingestion")

@router.post("/directory")
async def ingest_directory(
    background_tasks: BackgroundTasks,
    directory_path: str,
    force_reprocess: bool = False,
    recursive: bool = True,
    batch_id: Optional[str] = None
):
    """从目录摄入所有支持的文档"""
    try:
        # 验证目录路径
        dir_path = Path(directory_path)
        if not dir_path.exists() or not dir_path.is_dir():
            raise HTTPException(status_code=400, detail="Invalid directory path")
        
        # 查找支持的文件
        supported_formats = document_processor.get_supported_formats()
        file_paths = []
        
        if recursive:
            for ext in supported_formats:
                file_paths.extend(dir_path.rglob(f"*{ext}"))
                file_paths.extend(dir_path.rglob(f"*{ext.upper()}"))
        else:
            for ext in supported_formats:
                file_paths.extend(dir_path.glob(f"*{ext}"))
                file_paths.extend(dir_path.glob(f"*{ext.upper()}"))
        
        if not file_paths:
            return {
                "message": "No supported files found in directory",
                "directory": directory_path,
                "supported_formats": supported_formats
            }
        
        # 转换为字符串路径
        file_paths_str = [str(fp) for fp in file_paths]
        
        # 创建摄入请求
        request = IngestRequest(
            file_paths=file_paths_str,
            force_reprocess=force_reprocess,
            batch_id=batch_id
        )
        
        # 处理文档
        response = document_processor.process_request(request)
        
        # 在后台任务中保存到元数据存储
        background_tasks.add_task(
            _save_processed_documents,
            file_paths_str,
            response.successful,
            response.failed_files
        )
        
        return {
            "batch_id": request.batch_id,
            "directory": directory_path,
            "total_files": len(file_paths_str),
            "successful": response.successful,
            "failed": response.failed,
            "processing_time_seconds": response.processing_time_seconds
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Directory ingestion error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during directory ingestion")

@router.get("/status/{batch_id}")
async def get_batch_status(batch_id: str):
    """获取批次处理状态"""
    try:
        # 这里应该从某种作业队列或状态存储中获取状态
        # 暂时返回模拟状态
        return {
            "batch_id": batch_id,
            "status": "completed",  # pending, processing, completed, failed
            "message": "Batch processing completed successfully",
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Failed to get batch status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get batch status")

@router.delete("/documents")
async def delete_documents(
    doc_ids: List[str],
    delete_from_storage: bool = True
):
    """删除指定文档"""
    try:
        deleted_count = 0
        failed_deletions = []
        
        for doc_id in doc_ids:
            try:
                # 从元数据存储删除
                success = metadata_store.delete_document(doc_id)
                
                if success:
                    deleted_count += 1
                    
                    # 如果需要，从向量存储删除
                    if delete_from_storage:
                        from ...search.hybrid_searcher import hybrid_searcher
                        hybrid_searcher.delete_documents([doc_id])
                else:
                    failed_deletions.append({
                        "doc_id": doc_id,
                        "error": "Metadata deletion failed"
                    })
                        
            except Exception as e:
                failed_deletions.append({
                    "doc_id": doc_id,
                    "error": str(e)
                })
        
        return {
            "total_requested": len(doc_ids),
            "deleted_count": deleted_count,
            "failed_deletions": failed_deletions
        }
        
    except Exception as e:
        logger.error(f"Document deletion error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete documents")

@router.get("/documents")
async def list_documents(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """列出已摄入的文档"""
    try:
        from ...models import ProcessingStatus
        
        # 转换状态字符串为枚举
        status_filter = None
        if status:
            try:
                status_filter = ProcessingStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        # 获取文档列表
        documents = metadata_store.list_documents(
            status=status_filter,
            limit=limit,
            offset=offset
        )
        
        # 获取总数统计
        all_docs = metadata_store.list_documents(status=status_filter)
        total_count = len(all_docs)
        
        return {
            "documents": documents,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total_count": total_count,
                "has_more": offset + limit < total_count
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list documents")

@router.get("/statistics")
async def get_ingestion_statistics():
    """获取摄入统计信息"""
    try:
        # 从元数据存储获取统计信息
        stats = metadata_store.get_statistics()
        
        # 添加处理器信息
        processor_info = document_processor.get_parser_info()
        
        return {
            "ingestion_statistics": stats,
            "parser_info": processor_info,
            "supported_formats": document_processor.get_supported_formats()
        }
        
    except Exception as e:
        logger.error(f"Failed to get ingestion statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

async def _save_processed_documents(
    file_paths: List[str], 
    successful: int, 
    failed_files: List[Dict[str, str]]
):
    """保存已处理文档到元数据存储（后台任务）"""
    try:
        logger.info(f"Background task: Saving {successful} documents, {len(failed_files)} failed")
        
        # 这里可以实现更复杂的后台保存逻辑
        # 比如更新索引、发送通知等
        
    except Exception as e:
        logger.error(f"Background save task failed: {e}")

@router.post("/reindex")
async def reindex_documents(
    background_tasks: BackgroundTasks,
    filters: Optional[Dict[str, Any]] = None,
    force_rebuild: bool = False
):
    """重建索引"""
    try:
        # 启动后台重建任务
        background_tasks.add_task(
            _rebuild_index,
            filters,
            force_rebuild
        )
        
        return {
            "message": "Index rebuild started in background",
            "filters": filters,
            "force_rebuild": force_rebuild
        }
        
    except Exception as e:
        logger.error(f"Reindex error: {e}")
        raise HTTPException(status_code=500, detail="Failed to start index rebuild")

async def _rebuild_index(
    filters: Optional[Dict[str, Any]] = None,
    force_rebuild: bool = False
):
    """重建索引的后台任务"""
    try:
        logger.info("Starting background index rebuild")
        
        # 重建混合搜索器索引
        from ...search.hybrid_searcher import hybrid_searcher
        
        if force_rebuild:
            success = hybrid_searcher.rebuild_index(filters)
        else:
            success = hybrid_searcher.initialize()
        
        if success:
            logger.info("Index rebuild completed successfully")
        else:
            logger.error("Index rebuild failed")
            
    except Exception as e:
        logger.error(f"Background index rebuild failed: {e}")

@router.get("/health")
async def ingest_health_check():
    """摄入模块健康检查"""
    try:
        health_status = {
            "status": "healthy",
            "processor_loaded": document_processor is not None,
            "supported_formats": document_processor.get_supported_formats(),
            "timestamp": time.time()
        }
        
        # 检查元数据存储健康状态
        metadata_health = metadata_store.health_check()
        health_status["metadata_store"] = metadata_health
        
        return health_status
        
    except Exception as e:
        logger.error(f"Ingest health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }