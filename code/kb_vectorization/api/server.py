"""
本地知识库全量向量化自动化系统 - API 服务器
版本: v1.0
日期: 2026-03-01

本模块实现：
- REST API 服务
- 请求处理
- 响应封装
"""

import os
import threading
import time
from datetime import datetime
from typing import Optional

from flask import Flask, request, jsonify
from werkzeug.exceptions import NotFound, BadRequest

# 导入本地模块
from ..core.config import Config
from ..core.scanner import FileScanner, ScanResult
from ..core.vectorizer import Vectorizer
from ..core.storage import create_vector_store, VectorStore
from ..core.retriever import Retriever, RetrievalResult
from ..core.updater import FileUpdater
from ..core.utils import setup_logger, check_memory, sanitize_text

from .schemas import (
    SearchRequest,
    SearchResponse,
    SearchResponseItem,
    ScanResponse,
    VectorizeResponse,
    StatsResponse,
    HealthResponse,
    create_error_response,
    create_success_response,
    ErrorCode
)
from .middleware import setup_middleware, rate_limiter


class APIServer:
    """API 服务器"""

    def __init__(self, config: Optional[Config] = None):
        """
        初始化 API 服务器

        Args:
            config: 配置对象
        """
        self.config = config or Config()
        self.logger = setup_logger("api", self.config.log_dir, self.config.log_level)

        # 核心组件
        self._store: Optional[VectorStore] = None
        self._retriever: Optional[Retriever] = None
        self._scanner: Optional[FileScanner] = None
        self._vectorizer: Optional[Vectorizer] = None
        self._updater: Optional[FileUpdater] = None

        # 服务器状态
        self._app: Optional[Flask] = None
        self._start_time: float = time.time()
        self._running = False
        self._server_thread: Optional[threading.Thread] = None

        # 初始化
        self._init_components()

    def _init_components(self) -> None:
        """初始化核心组件"""
        try:
            # 初始化向量存储
            self._store = create_vector_store(self.config)
            self.logger.info(f"向量存储初始化: {self.config.store_type}")

            # 初始化检索器
            self._retriever = Retriever(self._store, self.config)
            self.logger.info("检索器初始化完成")

            # 初始化扫描器
            self._scanner = FileScanner(self.config)
            self.logger.info("文件扫描器初始化完成")

            # 初始化向量化器
            self._vectorizer = Vectorizer(self.config)
            self.logger.info("向量化器初始化完成")

            # 初始化更新器（可选）
            if self.config.get("monitor.enable_watchdog", False):
                self._updater = FileUpdater(self.config, self._vectorizer, self._store)
                self.logger.info("文件更新器初始化完成")

        except Exception as e:
            self.logger.error(f"初始化组件失败: {e}")

    def create_app(self) -> Flask:
        """
        创建 Flask 应用

        Returns:
            Flask 应用实例
        """
        if self._app:
            return self._app

        app = Flask(__name__)

        # 设置中间件
        setup_middleware(app, self.config)

        # 注册路由
        self._register_routes(app)

        # 错误处理
        self._register_error_handlers(app)

        self._app = app
        return app

    def _register_routes(self, app: Flask) -> None:
        """注册路由"""

        # ===== 基础路由 =====
        @app.route('/')
        def index():
            """根路径"""
            return jsonify({
                "name": self.config.system_name,
                "version": self.config.system_version,
                "description": "本地知识库全量向量化自动化系统",
                "endpoints": {
                    "search": f"{self.config.api_prefix}/search",
                    "scan": f"{self.config.api_prefix}/scan",
                    "vectorize": f"{self.config.api_prefix}/vectorize",
                    "stats": f"{self.config.api_prefix}/stats",
                    "health": f"{self.config.api_prefix}/health"
                }
            })

        # ===== 健康检查 =====
        @app.route(f'{self.config.api_prefix}/health', methods=['GET'])
        def health():
            """健康检查"""
            components = {}

            # 检查向量存储
            if self._store:
                try:
                    stats = self._store.get_stats()
                    components["store"] = "ok"
                    components["vectors"] = stats.get("total_vectors", 0)
                except Exception as e:
                    components["store"] = f"error: {str(e)}"
            else:
                components["store"] = "not initialized"

            # 检查检索器
            components["retriever"] = "ok" if self._retriever else "not initialized"

            # 检查内存
            try:
                mem_ok = check_memory(self.config.memory_limit, raise_on_exceed=False)
                components["memory"] = "ok" if mem_ok else "warning"
            except Exception:
                components["memory"] = "error"

            response = HealthResponse(
                status="healthy" if "error" not in components.values() else "degraded",
                version=self.config.system_version,
                uptime=time.time() - self._start_time,
                components=components
            )

            return jsonify(response.to_dict())

        # ===== 搜索接口 =====
        @app.route(f'{self.config.api_prefix}/search', methods=['POST'])
        @rate_limiter(
            max_requests=self.config.get("api.rate_limit", 100),
            window=60
        )
        def search():
            """搜索文档"""
            try:
                data = request.get_json()
                if not data:
                    raise BadRequest("请求数据为空")

                search_request = SearchRequest(
                    query=data.get("query", ""),
                    top_k=data.get("top_k"),
                    search_type=data.get("search_type", "hybrid"),
                    filters=data.get("filters")
                )

                # 验证请求
                if not search_request.query:
                    raise BadRequest("查询文本不能为空")

                if search_request.search_type not in ["keyword", "vector", "hybrid"]:
                    raise BadRequest("不支持的搜索类型")

                # 执行搜索
                result: RetrievalResult = self._retriever.search(
                    query=search_request.query,
                    top_k=search_request.top_k,
                    search_type=search_request.search_type,
                    filters=search_request.filters
                )

                # 转换结果
                results = [
                    SearchResponseItem(
                        id=r.id,
                        file_path=r.file_path,
                        file_name=r.file_name,
                        category=r.category,
                        chunk_index=r.chunk_index,
                        chunk_text=r.chunk_text,
                        similarity=float(r.similarity),
                        metadata=r.metadata
                    )
                    for r in result.results
                ]

                response = SearchResponse(
                    success=True,
                    query=result.query,
                    type=result.type,
                    total=result.total,
                    query_time=result.query_time,
                    results=results,
                    message=f"找到 {result.total} 个相关结果"
                )

                return jsonify(response.to_dict())

            except BadRequest as e:
                response = create_error_response(
                    code=ErrorCode.INVALID_REQUEST,
                    message=str(e)
                )
                return jsonify(response.to_dict()), 400
            except Exception as e:
                self.logger.error(f"搜索失败: {e}")
                response = create_error_response(
                    code=ErrorCode.SEARCH_FAILED,
                    message="搜索失败",
                    details=str(e)
                )
                return jsonify(response.to_dict()), 500

        # ===== 扫描接口 =====
        @app.route(f'{self.config.api_prefix}/scan', methods=['POST'])
        @rate_limiter(max_requests=10, window=60)
        def scan():
            """扫描文件"""
            try:
                data = request.get_json() or {}
                directories = data.get("directories")

                # 执行扫描
                result: ScanResult = self._scanner.scan(
                    directories=directories
                )

                response = ScanResponse(
                    success=True,
                    total_files=result.total_files,
                    total_size=result.total_size,
                    by_type=result.by_type,
                    by_category=result.by_category,
                    scan_time=result.scan_time,
                    message=f"扫描完成，找到 {result.total_files} 个文件"
                )

                return jsonify(response.to_dict())

            except Exception as e:
                self.logger.error(f"扫描失败: {e}")
                response = create_error_response(
                    code=ErrorCode.SCAN_FAILED,
                    message="扫描失败",
                    details=str(e)
                )
                return jsonify(response.to_dict()), 500

        # ===== 向量化接口 =====
        @app.route(f'{self.config.api_prefix}/vectorize', methods=['POST'])
        @rate_limiter(max_requests=5, window=60)
        def vectorize():
            """批量向量化"""
            try:
                data = request.get_json()
                if not data:
                    raise BadRequest("请求数据为空")

                files = data.get("files", [])
                if not files:
                    raise BadRequest("文件列表不能为空")

                # 检查内存
                if not check_memory(self.config.memory_limit, raise_on_exceed=False):
                    raise RuntimeError("内存使用量过高，请稍后再试")

                # 执行向量化
                chunks, stats = self._vectorizer.vectorize_batch(files)

                # 添加到存储
                if chunks and self._store:
                    self._store.add_vectors(chunks)

                response = VectorizeResponse(
                    success=True,
                    processed_files=stats.processed_files,
                    total_chunks=stats.processed_chunks,
                    failed_files=stats.failed_files,
                    duration=stats.duration,
                    message=f"处理完成，生成 {stats.processed_chunks} 个向量"
                )

                return jsonify(response.to_dict())

            except BadRequest as e:
                response = create_error_response(
                    code=ErrorCode.INVALID_REQUEST,
                    message=str(e)
                )
                return jsonify(response.to_dict()), 400
            except RuntimeError as e:
                response = create_error_response(
                    code=ErrorCode.VECTORIZATION_FAILED,
                    message=str(e)
                )
                return jsonify(response.to_dict()), 429
            except Exception as e:
                self.logger.error(f"向量化失败: {e}")
                response = create_error_response(
                    code=ErrorCode.VECTORIZATION_FAILED,
                    message="向量化失败",
                    details=str(e)
                )
                return jsonify(response.to_dict()), 500

        # ===== 统计接口 =====
        @app.route(f'{self.config.api_prefix}/stats', methods=['GET'])
        def stats():
            """获取统计信息"""
            try:
                store_stats = {}
                if self._store:
                    store_stats = self._store.get_stats()

                response = StatsResponse(
                    success=True,
                    stats={
                        "system": {
                            "name": self.config.system_name,
                            "version": self.config.system_version,
                            "uptime": time.time() - self._start_time
                        },
                        "storage": store_stats,
                        "config": {
                            "scan_dirs": self.config.get_scan_dirs(),
                            "file_types": self.config.get_file_types(),
                            "batch_size": self.config.batch_size,
                            "vector_dim": self.config.vector_dim
                        }
                    }
                )

                return jsonify(response.to_dict())

            except Exception as e:
                self.logger.error(f"获取统计信息失败: {e}")
                response = create_error_response(
                    code=ErrorCode.UNKNOWN_ERROR,
                    message="获取统计信息失败",
                    details=str(e)
                )
                return jsonify(response.to_dict()), 500

        # ===== 启动监控接口 =====
        @app.route(f'{self.config.api_prefix}/monitor/start', methods=['POST'])
        def start_monitor():
            """启动文件监控"""
            try:
                if not self._updater:
                    response = create_error_response(
                        code=ErrorCode.NOT_FOUND,
                        message="文件更新器未初始化"
                    )
                    return jsonify(response.to_dict()), 404

                self._updater.start_monitor()

                response = create_success_response(
                    message="文件监控已启动"
                )
                return jsonify(response.to_dict())

            except Exception as e:
                self.logger.error(f"启动监控失败: {e}")
                response = create_error_response(
                    code=ErrorCode.UNKNOWN_ERROR,
                    message="启动监控失败",
                    details=str(e)
                )
                return jsonify(response.to_dict()), 500

        # ===== 停止监控接口 =====
        @app.route(f'{self.config.api_prefix}/monitor/stop', methods=['POST'])
        def stop_monitor():
            """停止文件监控"""
            try:
                if not self._updater:
                    response = create_error_response(
                        code=ErrorCode.NOT_FOUND,
                        message="文件更新器未初始化"
                    )
                    return jsonify(response.to_dict()), 404

                self._updater.stop_monitor()

                response = create_success_response(
                    message="文件监控已停止"
                )
                return jsonify(response.to_dict())

            except Exception as e:
                self.logger.error(f"停止监控失败: {e}")
                response = create_error_response(
                    code=ErrorCode.UNKNOWN_ERROR,
                    message="停止监控失败",
                    details=str(e)
                )
                return jsonify(response.to_dict()), 500

    def _register_error_handlers(self, app: Flask) -> None:
        """注册错误处理器"""

        @app.errorhandler(404)
        def not_found(e):
            """404 处理"""
            response = create_error_response(
                code=ErrorCode.NOT_FOUND,
                message="接口不存在"
            )
            return jsonify(response.to_dict()), 404

        @app.errorhandler(405)
        def method_not_allowed(e):
            """405 处理"""
            response = create_error_response(
                code=ErrorCode.METHOD_NOT_ALLOWED,
                message="不支持的请求方法"
            )
            return jsonify(response.to_dict()), 405

        @app.errorhandler(400)
        def bad_request(e):
            """400 处理"""
            response = create_error_response(
                code=ErrorCode.INVALID_REQUEST,
                message=str(e.description) if e.description else "无效请求"
            )
            return jsonify(response.to_dict()), 400

        @app.errorhandler(500)
        def internal_error(e):
            """500 处理"""
            self.logger.error(f"内部错误: {e}")
            response = create_error_response(
                code=ErrorCode.UNKNOWN_ERROR,
                message="服务器内部错误"
            )
            return jsonify(response.to_dict()), 500

    def run(self, host: Optional[str] = None, port: Optional[int] = None, debug: bool = False) -> None:
        """
        运行服务器

        Args:
            host: 监听地址
            port: 监听端口
            debug: 调试模式
        """
        if self._running:
            self.logger.warning("服务器已在运行")
            return

        app = self.create_app()

        host = host or self.config.api_host
        port = port or self.config.api_port
        debug = debug or self.config.debug

        self._running = True
        self._start_time = time.time()

        self.logger.info(f"启动 API 服务器: http://{host}:{port}")
        self.logger.info(f"API 前缀: {self.config.api_prefix}")

        app.run(host=host, port=port, debug=debug, threaded=True)

    def run_background(self, host: Optional[str] = None, port: Optional[int] = None, debug: bool = False) -> None:
        """
        在后台运行服务器

        Args:
            host: 监听地址
            port: 监听端口
            debug: 调试模式
        """
        if self._running:
            self.logger.warning("服务器已在运行")
            return

        app = self.create_app()

        host = host or self.config.api_host
        port = port or self.config.api_port
        debug = debug or self.config.debug

        self._running = True
        self._start_time = time.time()

        def run_server():
            app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()

        self.logger.info(f"API 服务器已在后台启动: http://{host}:{port}")

    def stop(self) -> None:
        """停止服务器"""
        self._running = False

        if self._updater:
            self._updater.stop_monitor()

        self.logger.info("API 服务器已停止")


def create_app(config: Optional[Config] = None) -> Flask:
    """
    创建 Flask 应用（快捷方式）

    Args:
        config: 配置对象

    Returns:
        Flask 应用实例
    """
    server = APIServer(config)
    return server.create_app()


def run_server(config: Optional[Config] = None, host: Optional[str] = None, port: Optional[int] = None, debug: bool = False) -> None:
    """
    运行 API 服务器（快捷方式）

    Args:
        config: 配置对象
        host: 监听地址
        port: 监听端口
        debug: 调试模式
    """
    server = APIServer(config)
    server.run(host=host, port=port, debug=debug)
