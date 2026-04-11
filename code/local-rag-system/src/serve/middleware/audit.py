from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any, Optional
import logging
import time
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class AuditMiddleware(BaseHTTPMiddleware):
    """审计日志中间件"""
    
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
    
    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)
        
        start_time = time.time()
        
        # 记录请求信息
        audit_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "request_size": len(await request.body()) if request.method in ["POST", "PUT"] else 0
        }
        
        # 处理请求
        response = await call_next(request)
        
        # 计算处理时间
        process_time = time.time() - start_time
        
        # 记录响应信息
        audit_data.update({
            "status_code": response.status_code,
            "response_size": response.headers.get("content-length", 0),
            "process_time_ms": process_time * 1000,
            "success": 200 <= response.status_code < 400
        })
        
        # 记录审计日志
        await self._log_audit(audit_data, request, response)
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP地址"""
        # 尝试从各种头部获取真实IP
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # 从连接信息获取
        if hasattr(request, 'client') and request.client:
            return request.client.host
        
        return "unknown"
    
    async def _log_audit(self, audit_data: Dict[str, Any], request: Request, response: Response):
        """记录审计日志"""
        try:
            # 根据重要性过滤敏感信息
            sanitized_data = self._sanitize_audit_data(audit_data, request, response)
            
            # 结构化日志
            logger.info("audit", extra=sanitized_data)
            
        except Exception as e:
            logger.error(f"Failed to log audit data: {e}")
    
    def _sanitize_audit_data(self, audit_data: Dict[str, Any], 
                           request: Request, response: Response) -> Dict[str, Any]:
        """清理审计数据中的敏��信息"""
        sanitized = audit_data.copy()
        
        # 移除或模糊化敏感的请求体
        if request.method in ["POST", "PUT"] and "query_params" in sanitized:
            # 模糊化密码等敏感字段
            query_params = sanitized["query_params"].copy()
            sensitive_fields = ["password", "token", "secret", "key", "auth"]
            
            for field in sensitive_fields:
                if field in query_params:
                    query_params[field] = "***REDACTED***"
            
            sanitized["query_params"] = query_params
        
        # 检查是否为敏感路径
        sensitive_paths = ["/admin", "/config", "/auth", "/api/v1/admin"]
        if any(path in sanitized["path"] for path in sensitive_paths):
            sanitized["is_sensitive"] = True
            # 对于敏感路径，可以进一步清理信息
        
        return sanitized