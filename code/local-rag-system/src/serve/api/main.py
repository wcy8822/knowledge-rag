from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging
import time
from typing import Dict, Any
import uvicorn

from .endpoints import ingest, search, admin, metrics
from ..middleware import auth, cors, audit
from ..utils.logger import setup_logging
from ..utils.metrics import metrics_collector
from ..config import config

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

class LocalRAGAPI(FastAPI):
    """本地RAG系统API应用"""
    
    def __init__(self):
        super().__init__(
            title="Local RAG System API",
            description="本地知识库向量化系统API",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # 添加中间件
        self._add_middleware()
        
        # 注册路由
        self._register_routes()
        
        # 启动事件
        self._setup_events()
    
    def _add_middleware(self):
        """添加中间件"""
        # CORS中间件
        cors_config = config.get('security', {}).get('cors', {})
        self.add_middleware(
            CORSMiddleware,
            allow_origins=cors_config.get('allowed_origins', ["*"]),
            allow_credentials=cors_config.get('allow_credentials', True),
            allow_methods=cors_config.get('allowed_methods', ["*"]),
            allow_headers=cors_config.get('allowed_headers', ["*"]),
        )
        
        # 信任主机中间件
        trusted_hosts = config.get('security', {}).get('trusted_hosts', ["*"])
        if trusted_hosts != ["*"]:
            self.add_middleware(
                TrustedHostMiddleware,
                allowed_hosts=trusted_hosts
            )
        
        # 认证中间件
        if config.get('security', {}).get('authentication_enabled', False):
            self.add_middleware(auth.AuthMiddleware)
        
        # 审计中间件
        if config.get('monitoring', {}).get('audit_log_enabled', True):
            self.add_middleware(audit.AuditMiddleware)
        
        # 请求日志中间件
        @self.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()
            
            # 记录请求
            logger.info(f"Request: {request.method} {request.url.path}")
            
            # 处理请求
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            # 记录响应
            logger.info(f"Response: {response.status_code} in {process_time:.4f}s")
            
            # 收集指标
            metrics_collector.record_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                process_time=process_time
            )
            
            return response
    
    def _register_routes(self):
        """注册API路由"""
        # API v1 路由
        api_prefix = "/api/v1"
        
        # 摄入端点
        self.include_router(
            ingest.router,
            prefix=f"{api_prefix}/ingest",
            tags=["Ingest"]
        )
        
        # 搜索端点
        self.include_router(
            search.router,
            prefix=f"{api_prefix}/search",
            tags=["Search"]
        )
        
        # 管理端点
        self.include_router(
            admin.router,
            prefix=f"{api_prefix}/admin",
            tags=["Admin"]
        )
        
        # 指标端点
        self.include_router(
            metrics.router,
            prefix=f"{api_prefix}/metrics",
            tags=["Metrics"]
        )
        
        # 根路径
        @self.get("/")
        async def root():
            return {
                "message": "Local RAG System API",
                "version": "1.0.0",
                "docs": "/docs",
                "health": "/health"
            }
        
        # 健康检查端点
        @self.get("/health")
        async def health():
            return await self._health_check()
        
        # API信息端点
        @self.get("/info")
        async def info():
            return {
                "title": "Local RAG System API",
                "version": "1.0.0",
                "description": "本地知识库向量化系统API",
                "endpoints": {
                    "docs": "/docs",
                    "redoc": "/redoc",
                    "ingest": "/api/v1/ingest",
                    "search": "/api/v1/search",
                    "admin": "/api/v1/admin",
                    "metrics": "/api/v1/metrics"
                }
            }
    
    def _setup_events(self):
        """设置启动和关闭事件"""
        
        @self.on_event("startup")
        async def startup_event():
            logger.info("Local RAG System API starting up...")
            
            try:
                # 初始化各个模块
                from ..search.hybrid_searcher import hybrid_searcher
                
                init_success = hybrid_searcher.initialize()
                if not init_success:
                    logger.error("Failed to initialize hybrid searcher")
                
                logger.info("Local RAG System API startup completed")
                
            except Exception as e:
                logger.error(f"Failed to startup: {e}")
                raise
        
        @self.on_event("shutdown")
        async def shutdown_event():
            logger.info("Local RAG System API shutting down...")
            
            # 清理资源
            try:
                # 保存指标
                metrics_collector.save_metrics()
                logger.info("Local RAG System API shutdown completed")
                
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
    
    async def _health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            health_status = {
                "status": "healthy",
                "timestamp": time.time(),
                "version": "1.0.0"
            }
            
            # 检查各个模块健康状态
            from ..search.hybrid_searcher import hybrid_searcher
            from ..store.embedding_service import embedding_service
            from ..store.metadata_store import metadata_store
            from ..search.reranker import reranker
            
            # 混合搜索器健康检查
            hybrid_health = hybrid_searcher.health_check()
            health_status["hybrid_searcher"] = hybrid_health
            
            # 嵌入服务健康检查
            embedding_health = embedding_service.health_check()
            health_status["embedding_service"] = embedding_health
            
            # 元数据存储健康检查
            metadata_health = metadata_store.health_check()
            health_status["metadata_store"] = metadata_health
            
            # 重排序器健康检查
            reranker_health = reranker.health_check()
            health_status["reranker"] = reranker_health
            
            # 确定整体状态
            components = ["hybrid_searcher", "embedding_service", "metadata_store", "reranker"]
            unhealthy_components = []
            
            for component in components:
                if component in health_status:
                    component_health = health_status[component]
                    if isinstance(component_health, dict) and component_health.get('status') in ['unhealthy', 'error']:
                        unhealthy_components.append(component)
            
            if unhealthy_components:
                health_status["status"] = "degraded" if len(unhealthy_components) < len(components) else "unhealthy"
                health_status["unhealthy_components"] = unhealthy_components
            
            return health_status
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "timestamp": time.time(),
                "error": str(e)
            }

# 创建FastAPI应用实例
app = LocalRAGAPI()

def run_server():
    """运行API服务器"""
    uvicorn_config = {
        "app": app,
        "host": config.settings.host,
        "port": config.settings.port,
        "log_level": config.settings.log_level.lower(),
        "reload": config.settings.debug,
        "access_log": True
    }
    
    logger.info(f"Starting Local RAG System API on {config.settings.host}:{config.settings.port}")
    uvicorn.run(**uvicorn_config)

if __name__ == "__main__":
    run_server()