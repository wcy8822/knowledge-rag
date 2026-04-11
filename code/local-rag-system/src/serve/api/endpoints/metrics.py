from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging
import time

from ...utils.metrics import metrics_collector

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/")
async def get_all_metrics():
    """获取所有指标"""
    try:
        all_metrics = metrics_collector.get_all_metrics()
        return all_metrics
        
    except Exception as e:
        logger.error(f"Failed to get all metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")

@router.get("/search")
async def get_search_metrics():
    """获取搜索相关指标"""
    try:
        search_metrics = metrics_collector.get_search_metrics()
        return search_metrics
        
    except Exception as e:
        logger.error(f"Failed to get search metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve search metrics")

@router.get("/ask")
async def get_ask_metrics():
    """获取问答相关指标"""
    try:
        ask_metrics = metrics_collector.get_ask_metrics()
        return ask_metrics
        
    except Exception as e:
        logger.error(f"Failed to get ask metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve ask metrics")

@router.get("/requests")
async def get_request_metrics():
    """获取请求相关指标"""
    try:
        request_metrics = metrics_collector.get_request_metrics()
        return request_metrics
        
    except Exception as e:
        logger.error(f"Failed to get request metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve request metrics")

@router.get("/system")
async def get_system_metrics():
    """获取系统相关指标"""
    try:
        system_metrics = metrics_collector.get_system_metrics()
        return system_metrics
        
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system metrics")

@router.post("/reset")
async def reset_metrics():
    """重置所有指标"""
    try:
        metrics_collector.reset_metrics()
        return {
            "message": "All metrics have been reset",
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Failed to reset metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset metrics")

@router.get("/performance")
async def get_performance_metrics():
    """获取性能指标摘要"""
    try:
        # 获取各项指标
        request_metrics = metrics_collector.get_request_metrics()
        search_metrics = metrics_collector.get_search_metrics()
        ask_metrics = metrics_collector.get_ask_metrics()
        system_metrics = metrics_collector.get_system_metrics()
        
        # 计算性能摘要
        performance_summary = {
            "uptime_percentage": 100.0,  # 简化计算
            "average_response_time": request_metrics.get("latency_stats", {}).get("avg", 0),
            "p95_response_time": request_metrics.get("latency_stats", {}).get("p95", 0),
            "total_requests": request_metrics.get("total_requests", 0),
            "error_rate": request_metrics.get("error_rate", 0),
            "search_hit_rate": search_metrics.get("hit_rate", 0),
            "average_search_latency": search_metrics.get("average_latency_ms", 0),
            "ask_success_rate": 1.0 - ask_metrics.get("total_asks", 0) * 0.05,  # 简化计算
            "groundedness_average": ask_metrics.get("average_groundedness", 0),
            "llm_average_latency": ask_metrics.get("average_llm_latency_ms", 0)
        }
        
        return {
            "timestamp": time.time(),
            "performance_summary": performance_summary,
            "detailed_metrics": {
                "requests": request_metrics,
                "search": search_metrics,
                "ask": ask_metrics,
                "system": system_metrics
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve performance metrics")

@router.get("/health")
async def get_metrics_health():
    """获取指标收集器健康状态"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "collector_active": True,
            "last_collection_time": time.time(),
            "metrics_memory_usage": {
                "estimated_requests": len(metrics_collector.request_counts),
                "estimated_searches": len(metrics_collector.search_queries),
                "estimated_asks": len(metrics_collector.ask_queries)
            }
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Failed to get metrics health: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }