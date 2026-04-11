#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BGE-M3 MCP 服务器 - 标准 MCP 协议实现
使用官方 mcp 库，支持 Claude 无缝集成
"""

import sys
import json
import logging
import asyncio
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types
except ImportError:
    logger.error("❌ MCP 库未找到，正在安装...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mcp"])
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types

# 导入 BGE-M3 搜索器
try:
    from ..search.bge_m3_searcher import BGE_M3_Searcher, create_searcher
except ImportError:
    logger.error("❌ BGE-M3 搜索器导入失败")
    raise


class BGE_M3_MCP_Server:
    """BGE-M3 MCP 服务器 - 标准 MCP 协议实现"""

    def __init__(
        self,
        server_name: str = "knowledge-base-bge-m3",
        db_path: str = "/Users/didi/Downloads/panth/data/chroma",
        collection_name: str = "bge-m3-documents"
    ):
        """
        初始化 MCP 服务器

        Args:
            server_name: MCP 服务器名称
            db_path: ChromaDB 数据库路径
            collection_name: Collection 名称
        """
        self.server_name = server_name
        self.db_path = db_path
        self.collection_name = collection_name

        # 创建 MCP Server 实例
        self.server = Server(server_name)

        # 搜索器
        self.searcher: Optional[BGE_M3_Searcher] = None

        # 审计日志
        self.audit_log = []

        logger.info("=" * 80)
        logger.info("🚀 BGE-M3 MCP 服务器初始化")
        logger.info("=" * 80)
        logger.info(f"服务器名: {server_name}")
        logger.info(f"数据库: {db_path}")
        logger.info(f"Collection: {collection_name}")

        # 注册工具
        self._register_tools()

        logger.info("✅ MCP 服务器初始化完成")

    def _register_tools(self):
        """注册 MCP 工具"""

        @self.server.list_tools()
        async def list_tools():
            """列出所有可用工具"""
            return [
                types.Tool(
                    name="search_knowledge",
                    description="""使用 BGE-M3 搜索本地知识库
支持：
- 向量相似度搜索 (1024D)
- 混合搜索 (向量 + BM25)
- 结果重排优化

返回最相关的文档及其相关性评分。
适用于：文档检索、问答、语义搜索等。""",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜索查询 (支持中文和英文)"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "返回的结果数量",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 20
                            },
                            "use_reranking": {
                                "type": "boolean",
                                "description": "是否使用结果重排优化",
                                "default": True
                            }
                        },
                        "required": ["query"]
                    }
                ),
                types.Tool(
                    name="get_knowledge_stats",
                    description="""获取知识库统计信息

返回：
- 文档总数
- 向量维度
- 模型信息
- 搜索统计
- 系统状态""",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                )
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> str:
            """处理工具调用"""
            logger.info(f"🔧 工具调用: {name}")
            self._audit_log("tool_call", name, arguments)

            if name == "search_knowledge":
                return self._handle_search_knowledge(arguments)
            elif name == "get_knowledge_stats":
                return self._handle_get_knowledge_stats()
            else:
                error_msg = f"❌ 未知工具: {name}"
                logger.error(error_msg)
                return json.dumps({"error": error_msg})

        logger.info("✅ 工具注册完成 (2 个工具)")

    def _handle_search_knowledge(self, arguments: dict) -> str:
        """处理搜索工具"""
        try:
            if not self.searcher:
                return self._error_response("知识库未初始化")

            query = arguments.get("query", "")
            top_k = arguments.get("top_k", 5)
            use_reranking = arguments.get("use_reranking", True)

            if not query:
                return self._error_response("query 参数不能为空")

            # 执行搜索
            results = self.searcher.search(
                query=query,
                top_k=top_k,
                use_reranking=use_reranking
            )

            # 格式化结果
            formatted_results = []
            for r in results:
                formatted_results.append({
                    "rank": r["rank"],
                    "file_name": r["file_name"],
                    "file_path": r["file_path"],
                    "relevance_score": round(r["relevance_score"], 4),
                    "content_preview": r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"],
                    "search_method": r["search_method"]
                })

            response = {
                "status": "success",
                "query": query,
                "results_count": len(formatted_results),
                "results": formatted_results,
                "timestamp": datetime.now().isoformat()
            }

            self._audit_log("search", query, {"results_count": len(results), "top_k": top_k})
            logger.info(f"✅ 搜索成功: {len(results)} 个结果")

            return json.dumps(response, ensure_ascii=False, indent=2)

        except Exception as e:
            error_msg = f"❌ 搜索失败: {str(e)}"
            logger.error(error_msg)
            return self._error_response(error_msg)

    def _handle_get_knowledge_stats(self) -> str:
        """处理统计工具"""
        try:
            if not self.searcher:
                return self._error_response("知识库未初始化")

            stats = self.searcher.get_stats()
            stats["server_name"] = self.server_name
            stats["mcp_protocol_version"] = "v1"
            stats["timestamp"] = datetime.now().isoformat()

            self._audit_log("stats_request", "get_knowledge_stats", {})
            logger.info("✅ 统计请求处理成功")

            return json.dumps(stats, ensure_ascii=False, indent=2)

        except Exception as e:
            error_msg = f"❌ 获取统计失败: {str(e)}"
            logger.error(error_msg)
            return self._error_response(error_msg)

    def _error_response(self, message: str) -> str:
        """生成错误响应"""
        return json.dumps({
            "status": "error",
            "message": message,
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False)

    def _audit_log(self, event_type: str, event_name: str, details: dict):
        """记录审计日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "event_name": event_name,
            "details": details
        }
        self.audit_log.append(log_entry)

        # 定期保存审计日志
        if len(self.audit_log) % 10 == 0:
            self._save_audit_log()

    def _save_audit_log(self):
        """保存审计日志到文件"""
        try:
            log_dir = Path("/Users/didi/Downloads/panth/logs")
            log_dir.mkdir(parents=True, exist_ok=True)

            log_file = log_dir / f"mcp_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(self.audit_log, f, ensure_ascii=False, indent=2)

            logger.info(f"✓ 审计日志已保存: {log_file}")
        except Exception as e:
            logger.warning(f"⚠️  保存审计日志失败: {e}")

    def initialize_searcher(self) -> bool:
        """初始化搜索器"""
        try:
            logger.info("\n📦 初始化搜索器...")
            self.searcher = create_searcher(
                db_path=self.db_path,
                collection_name=self.collection_name
            )

            if self.searcher and self.searcher.health_check():
                logger.info("✅ 搜索器就绪")
                return True
            else:
                logger.error("❌ 搜索器初始化失败")
                return False

        except Exception as e:
            logger.error(f"❌ 搜索器初始化异常: {e}")
            return False

    async def run(self):
        """运行 MCP 服务器（stdio 模式）"""
        try:
            # 初始化搜索器
            if not self.initialize_searcher():
                logger.error("❌ 无法继续：搜索器初始化失败")
                return False

            logger.info("\n🚀 启动 MCP 服务器（stdio 模式）...")
            logger.info(f"服务器名: {self.server_name}")
            logger.info("等待 Claude 连接...")

            # 运行 MCP 服务器
            async with stdio_server(self.server) as (read_stream, write_stream):
                logger.info("✅ MCP 服务器运行中...")
                await self.server.run(
                    read_stream,
                    write_stream,
                    self.server.create_initialization_options()
                )

            return True

        except KeyboardInterrupt:
            logger.info("⏸️  服务器被用户中断")
            # 保存审计日志
            self._save_audit_log()
            return True

        except Exception as e:
            logger.error(f"❌ 服务器运行异常: {e}")
            # 保存审计日志
            self._save_audit_log()
            return False


async def main():
    """异步主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="BGE-M3 MCP 服务器 - Claude 知识库集成"
    )
    parser.add_argument(
        "--db-path",
        default="/Users/didi/Downloads/panth/data/chroma",
        help="ChromaDB 数据库路径"
    )
    parser.add_argument(
        "--collection",
        default="bge-m3-documents",
        help="ChromaDB collection 名称"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别"
    )

    args = parser.parse_args()

    # 设置日志级别
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info("=" * 80)
    logger.info("🚀 BGE-M3 MCP 服务器启动")
    logger.info("=" * 80)
    logger.info(f"数据库: {args.db_path}")
    logger.info(f"Collection: {args.collection}")
    logger.info(f"日志级别: {args.log_level}")

    # 创建和运行服务器
    server = BGE_M3_MCP_Server(
        db_path=args.db_path,
        collection_name=args.collection
    )

    success = await server.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
