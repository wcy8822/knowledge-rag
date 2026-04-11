from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
import logging
import time
import json
from pathlib import Path

from ...config import config
from ...search.hybrid_searcher import hybrid_searcher
from ...store.metadata_store import metadata_store
from ...session_manager import session_manager
from ...utils.metrics import metrics_collector

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/system")
async def get_system_status():
    """获取系统状态"""
    try:
        # 获取混合搜索器状态
        search_health = hybrid_searcher.health_check()
        
        # 获取元数据存储状态
        metadata_health = metadata_store.health_check()
        
        # 获取会话管理器状态
        session_health = session_manager.health_check()
        
        # 获取系统指标
        system_metrics = metrics_collector.get_system_metrics()
        
        # 获取配置信息
        config_info = {
            "app_name": config.settings.app_name,
            "version": config.settings.app_version,
            "debug": config.settings.debug,
            "data_directory": str(Path(config.settings.data_base_dir).resolve()),
            "supported_formats": config.get('document', {}).get('supported_formats', [])
        }
        
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "search_engine": search_health,
            "metadata_store": metadata_health,
            "session_manager": session_health,
            "system_metrics": system_metrics,
            "configuration": config_info
        }
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system status")

@router.get("/components")
async def get_component_status():
    """获取各组件详细状态"""
    try:
        components = {}
        
        # 嵌入服务状态
        from ...store.embedding_service import embedding_service
        components["embedding_service"] = embedding_service.health_check()
        
        # 重排序器状态
        from ...search.reranker import reranker
        components["reranker"] = reranker.health_check()
        
        # BM25搜索器状态
        from ...search.bm25_searcher import bm25_searcher
        components["bm25_searcher"] = bm25_searcher.health_check()
        
        # 向量搜索器状态
        from ...search.vector_searcher import vector_searcher
        components["vector_searcher"] = vector_searcher.health_check()
        
        # 会话统计
        components["session_statistics"] = session_manager.get_session_statistics()
        
        return {
            "timestamp": time.time(),
            "components": components
        }
        
    except Exception as e:
        logger.error(f"Failed to get component status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get component status")

@router.get("/search/statistics")
async def get_search_statistics():
    """获取搜索统计信息"""
    try:
        # 获取混合搜索器统计
        search_stats = hybrid_searcher.get_statistics()
        
        # 获取请求指标
        request_metrics = metrics_collector.get_request_metrics()
        
        # 获取搜索特定指标
        search_metrics = metrics_collector.get_search_metrics()
        
        # 获取问答指标
        ask_metrics = metrics_collector.get_ask_metrics()
        
        return {
            "timestamp": time.time(),
            "search_engine": search_stats,
            "request_metrics": request_metrics,
            "search_metrics": search_metrics,
            "ask_metrics": ask_metrics
        }
        
    except Exception as e:
        logger.error(f"Failed to get search statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get search statistics")

@router.get("/metrics")
async def get_all_metrics():
    """获取所有指标"""
    try:
        all_metrics = metrics_collector.get_all_metrics()
        return all_metrics
        
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get metrics")

@router.post("/metrics/reset")
async def reset_metrics():
    """重置指标"""
    try:
        metrics_collector.reset_metrics()
        return {
            "message": "Metrics reset successfully",
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Failed to reset metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset metrics")

@router.post("/index/rebuild")
async def rebuild_index(
    background_tasks: BackgroundTasks,
    filters: Optional[Dict[str, Any]] = None,
    force_rebuild: bool = False
):
    """重建搜索索引"""
    try:
        # 在后台启动重建任务
        background_tasks.add_task(
            _rebuild_index_task,
            filters,
            force_rebuild
        )
        
        return {
            "message": "Index rebuild started in background",
            "filters": filters,
            "force_rebuild": force_rebuild,
            "task_id": f"rebuild_{int(time.time())}"
        }
        
    except Exception as e:
        logger.error(f"Failed to start index rebuild: {e}")
        raise HTTPException(status_code=500, detail="Failed to start index rebuild")

async def _rebuild_index_task(
    filters: Optional[Dict[str, Any]] = None,
    force_rebuild: bool = False
):
    """重建索引的后台任务"""
    try:
        logger.info(f"Starting index rebuild with filters: {filters}")
        
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

@router.get("/configuration")
async def get_configuration():
    """获取当前配置"""
    try:
        # 返回非敏感配置信息
        safe_config = {
            "app": {
                "name": config.settings.app_name,
                "version": config.settings.app_version,
                "debug": config.settings.debug
            },
            "data": {
                "base_dir": str(Path(config.settings.data_base_dir).resolve()),
                "upload_dir": str(Path(config.settings.upload_dir).resolve())
            },
            "document": config.get('document', {}),
            "embedding": {
                "provider": config.get('embedding', {}).get('provider'),
                "model_name": config.get('embedding', {}).get('model_name'),
                "device": config.get('embedding', {}).get('device'),
                "batch_size": config.get('embedding', {}).get('batch_size')
            },
            "retrieval": config.get('retrieval', {}),
            "monitoring": {
                "enabled": config.get('monitoring', {}).get('enabled', True),
                "log_level": config.get('monitoring', {}).get('log_level')
            }
        }
        
        return {
            "configuration": safe_config,
            "config_file_used": str(Path("config.yaml").resolve()) if Path("config.yaml").exists() else None
        }
        
    except Exception as e:
        logger.error(f"Failed to get configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to get configuration")

@router.post("/configuration/update")
async def update_configuration(
    background_tasks: BackgroundTasks,
    config_updates: Dict[str, Any]
):
    """更新配置（需要重启服务生效）"""
    try:
        # 验证配置更新
        valid_updates = _validate_config_updates(config_updates)
        
        if not valid_updates:
            raise HTTPException(status_code=400, detail="No valid configuration updates provided")
        
        # 备份当前配置
        config_file = Path("config.yaml")
        if config_file.exists():
            backup_file = config_file.with_suffix('.yaml.backup')
            import shutil
            shutil.copy2(config_file, backup_file)
            logger.info(f"Configuration backed up to {backup_file}")
        
        # 这里应该实现配置更新逻辑
        # 由于涉及服务重启，这里只是记录更新请求
        
        return {
            "message": "Configuration update request received. Service restart required.",
            "updates": valid_updates,
            "restart_required": True,
            "backup_created": config_file.with_suffix('.yaml.backup').exists()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")

@router.get("/logs")
async def get_logs(
    log_type: str = "application",
    lines: int = 100,
    level: Optional[str] = None
):
    """获取日志"""
    try:
        log_file_path = Path("logs") / f"{log_type}.log"
        
        if not log_file_path.exists():
            return {"logs": [], "message": f"Log file {log_type}.log not found"}
        
        # 读取日志文件最后几行
        with open(log_file_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            
        # 获取最后N行
        recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # 如果指定了日志级别，进行过滤
        if level:
            recent_lines = [line for line in recent_lines if level.upper() in line.upper()]
        
        return {
            "log_type": log_type,
            "lines_returned": len(recent_lines),
            "total_lines_in_file": len(all_lines),
            "logs": [line.strip() for line in recent_lines]
        }
        
    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get logs")

@router.get("/sessions")
async def get_active_sessions():
    """获取活跃会话"""
    try:
        session_stats = session_manager.get_session_statistics()
        
        return {
            "timestamp": time.time(),
            "session_statistics": session_stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get active sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active sessions")

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话"""
    try:
        success = session_manager.delete_session(session_id)
        
        if success:
            return {"message": f"Session {session_id} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete session")

def _validate_config_updates(config_updates: Dict[str, Any]) -> Dict[str, Any]:
    """验证配置更新"""
    valid_updates = {}
    
    # 允许更新的配置键
    allowed_keys = [
        'document.chunk_size',
        'document.chunk_overlap',
        'retrieval.hybrid_search.vector_weight',
        'retrieval.hybrid_search.bm25_weight',
        'retrieval.reranker.top_n',
        'monitoring.log_level'
    ]
    
    for key, value in config_updates.items():
        if key in allowed_keys:
            # 这里可以添加更详细的验证逻辑
            valid_updates[key] = value
    
    return valid_updates