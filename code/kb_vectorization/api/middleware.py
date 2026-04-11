"""
本地知识库全量向量化自动化系统 - API 中间件
版本: v1.0
日期: 2026-03-01
"""

import time
from typing import Callable
from flask import Flask, request, g, jsonify

from ..core.config import Config


def setup_middleware(app: Flask, config: Config) -> None:
    """
    设置中间件

    Args:
        app: Flask 应用
        config: 配置对象
    """
    # 只允许本机访问
    if config.localhost_only:
        app.before_request(_localhost_only)

    # 访问日志
    if config.get("api.log_requests", True):
        app.before_request(_log_request)
        app.after_request(_log_response)

    # IP 白名单
    if config.get("security.enable_ip_whitelist", False):
        app.before_request(_ip_whitelist(config))


def _localhost_only() -> None:
    """只允许本机访问"""
    if request.remote_addr != "127.0.0.1" and request.remote_addr != "::1":
        from .schemas import create_error_response
        response = create_error_response(
            code="FORBIDDEN",
            message="仅限本机访问"
        )
        return jsonify(response.to_dict()), 403


def _ip_whitelist(config: Config) -> None:
    """IP 白名单检查"""
    whitelist = config.ip_whitelist
    remote_addr = request.remote_addr

    if remote_addr not in whitelist:
        from .schemas import create_error_response
        response = create_error_response(
            code="FORBIDDEN",
            message=f"IP 地址不在白名单中: {remote_addr}"
        )
        return jsonify(response.to_dict()), 403


def _log_request() -> None:
    """记录请求"""
    g.start_time = time.time()

    from ..core.utils import setup_logger
    logger = setup_logger("api")

    logger.info(f"请求: {request.method} {request.path} from {request.remote_addr}")


def _log_response(response) -> object:
    """记录响应"""
    from ..core.utils import setup_logger
    logger = setup_logger("api")

    if hasattr(g, 'start_time'):
        duration = time.time() - g.start_time
        logger.info(f"响应: {response.status_code} ({duration:.3f}s)")

    return response


class RateLimiter:
    """简单的速率限制器"""

    def __init__(self, max_requests: int = 100, window: int = 60):
        """
        初始化速率限制器

        Args:
            max_requests: 最大请求数
            window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.window = window
        self._requests = {}

    def is_allowed(self, client_id: str) -> bool:
        """
        检查是否允许请求

        Args:
            client_id: 客户端ID

        Returns:
            是否允许
        """
        current_time = time.time()

        if client_id not in self._requests:
            self._requests[client_id] = []
        else:
            # 清理过期记录
            self._requests[client_id] = [
                t for t in self._requests[client_id]
                if current_time - t < self.window
            ]

        # 检查是否超限
        if len(self._requests[client_id]) >= self.max_requests:
            return False

        # 记录请求
        self._requests[client_id].append(current_time)
        return True

    def clear(self) -> None:
        """清除所有记录"""
        self._requests.clear()


def rate_limiter(max_requests: int = 100, window: int = 60) -> Callable:
    """
    速率限制装饰器

    Args:
        max_requests: 最大请求数
        window: 时间窗口（秒）

    Returns:
        装饰器函数
    """
    limiter = RateLimiter(max_requests, window)

    def decorator(f: Callable) -> Callable:
        def wrapped(*args, **kwargs):
            client_id = request.remote_addr

            if not limiter.is_allowed(client_id):
                from .schemas import create_error_response
                response = create_error_response(
                    code="RATE_LIMIT_EXCEEDED",
                    message=f"请求过于频繁，请稍后再试"
                )
                return jsonify(response.to_dict()), 429

            return f(*args, **kwargs)

        wrapped.__name__ = f.__name__
        return wrapped

    return decorator
