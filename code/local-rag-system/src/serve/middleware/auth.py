from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import logging
import time
import jwt
from functools import wraps

logger = logging.getLogger(__name__)

# 简单的Bearer token认证
security = HTTPBearer(auto_error=False)

class AuthMiddleware:
    """认证中间件"""
    
    def __init__(self, app, secret_key: str = None, require_auth: bool = False):
        self.app = app
        self.secret_key = secret_key or "your-secret-key-change-in-production"
        self.require_auth = require_auth
        
        # 公共路径（不需要认证）
        self.public_paths = {
            "/", "/health", "/info", "/docs", "/redoc", "/openapi.json",
            "/api/v1/metrics", "/api/v1/search/suggestions"
        }
    
    async def __call__(self, request: Request, call_next):
        # 检查是否为公共路径
        path = request.url.path
        if path in self.public_paths or path.startswith("/docs") or path.startswith("/redoc"):
            return await call_next(request)
        
        # 如果不需要认证，直接通过
        if not self.require_auth:
            # 设置默认用户信息
            request.state.user = {"user_id": "anonymous", "role": "user"}
            return await call_next(request)
        
        # 获取Authorization header
        authorization = request.headers.get("authorization")
        if not authorization:
            request.state.user = None
            return await call_next(request)
        
        try:
            # 验证token
            user_info = self.verify_token(authorization)
            request.state.user = user_info
            
        except Exception as e:
            logger.warning(f"Auth failed: {e}")
            request.state.user = None
        
        return await call_next(request)
    
    def verify_token(self, authorization: str) -> Optional[Dict[str, Any]]:
        """验证JWT token"""
        try:
            # 移除Bearer前缀
            if authorization.startswith("Bearer "):
                token = authorization[7:]
            else:
                token = authorization
            
            # 解码JWT
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=["HS256"],
                options={"verify_exp": True}
            )
            
            return {
                "user_id": payload.get("user_id"),
                "username": payload.get("username"),
                "role": payload.get("role", "user"),
                "permissions": payload.get("permissions", [])
            }
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None

async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """获取当前用户（需要认证）"""
    if hasattr(request.state, 'user') and request.state.user:
        return request.state.user
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """获取当前用户（可选认证）"""
    if hasattr(request.state, 'user'):
        return request.state.user
    return None

def require_permission(permission: str):
    """权限装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 尝试从kwargs中获取request对象
            request = None
            for arg in args:
                if hasattr(arg, 'url'):
                    request = arg
                    break
            
            if not request:
                request = kwargs.get('request')
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not determine request context"
                )
            
            # 检查用户权限
            user = getattr(request.state, 'user', None)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            user_permissions = user.get('permissions', [])
            if permission not in user_permissions and 'admin' not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission}' required"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator

def create_test_token(user_data: Dict[str, Any]) -> str:
    """创建测试JWT token"""
    payload = {
        "user_id": user_data.get("user_id", "test_user"),
        "username": user_data.get("username", "test_user"),
        "role": user_data.get("role", "user"),
        "permissions": user_data.get("permissions", []),
        "exp": int(time.time()) + 3600  # 1小时过期
    }
    
    return jwt.encode(payload, "your-secret-key-change-in-production", algorithm="HS256")