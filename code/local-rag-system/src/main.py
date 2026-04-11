"""
Local RAG System - 主入口文件
本地知识库向量化系统主程序
"""

import sys
import os
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

import argparse
import logging
from typing import Dict, Any

from src.config import config
from src.serve.api.main import run_server

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=getattr(logging, config.settings.log_level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/app.log')
        ]
    )

def start_server():
    """启动API服务器"""
    print("🚀 Starting Local RAG System API Server...")
    print(f"📊 Host: {config.settings.host}")
    print(f"📊 Port: {config.settings.port}")
    print(f"🔧 Debug: {config.settings.debug}")
    
    run_server()

def run_ingestion(input_dir: str, force_reprocess: bool = False):
    """运行文档摄入"""
    print(f"📚 Running document ingestion from: {input_dir}")
    
    try:
        from src.ingest.processor import DocumentProcessor
        from pathlib import Path
        
        # 初始化处理器
        processor = DocumentProcessor(config.get('document', {}))
        
        # 查找文件
        input_path = Path(input_dir)
        if not input_path.exists():
            print(f"❌ Input directory does not exist: {input_dir}")
            return
        
        supported_files = []
        for ext in processor.get_supported_formats():
            supported_files.extend(input_path.glob(f"*{ext}"))
            supported_files.extend(input_path.glob(f"*{ext.upper()}"))
        
        if not supported_files:
            print("❌ No supported files found")
            print(f"Supported formats: {processor.get_supported_formats()}")
            return
        
        # 处理文件
        from src.models import IngestRequest
        request = IngestRequest(
            file_paths=[str(f) for f in supported_files],
            force_reprocess=force_reprocess
        )
        
        response = processor.process_request(request)
        
        print(f"✅ Ingestion completed:")
        print(f"   Total files: {response.total_files}")
        print(f"   Successful: {response.successful}")
        print(f"   Failed: {response.failed}")
        print(f"   Time: {response.processing_time_seconds:.2f}s")
        
    except Exception as e:
        print(f"❌ Ingestion failed: {e}")

def check_health():
    """检查系统健康状态"""
    print("🏥 Checking system health...")
    
    try:
        from src.search.hybrid_searcher import hybrid_searcher
        from src.store.embedding_service import embedding_service
        from src.store.metadata_store import metadata_store
        from src.search.reranker import reranker
        
        # 初始化混合搜索器
        init_success = hybrid_searcher.initialize()
        
        # 检查各组件
        embedding_health = embedding_service.health_check()
        metadata_health = metadata_store.health_check()
        reranker_health = reranker.health_check()
        hybrid_health = hybrid_searcher.health_check() if init_success else {"status": "failed"}
        
        # 输出健康状态
        print("\n📊 Component Health Status:")
        print(f"   Embedding Service: {embedding_health.get('status', 'unknown')}")
        print(f"   Metadata Store: {metadata_health.get('status', 'unknown')}")
        print(f"   Reranker: {reranker_health.get('status', 'unknown')}")
        print(f"   Hybrid Searcher: {hybrid_health.get('status', 'unknown')}")
        
        # 检查整体状态
        all_healthy = all(
            health.get('status') in ['healthy', 'initialized']
            for health in [embedding_health, metadata_health, reranker_health, hybrid_health]
        )
        
        if all_healthy:
            print("\n✅ All components are healthy!")
        else:
            print("\n⚠️ Some components have issues")
            
    except Exception as e:
        print(f"❌ Health check failed: {e}")

def show_info():
    """显示系统信息"""
    print("📋 Local RAG System Information")
    print("=" * 40)
    print(f"Version: {config.settings.app_version}")
    print(f"Name: {config.settings.app_name}")
    print(f"Debug: {config.settings.debug}")
    print(f"Data Directory: {config.settings.data_base_dir}")
    print(f"Upload Directory: {config.settings.upload_dir}")
    print(f"Chroma Directory: {config.settings.chroma_dir}")
    print(f"Embedding Provider: {config.get('embedding', {}).get('provider', 'local')}")
    print(f"Vector DB: {config.get('vector_db', {}).get('provider', 'chroma')}")
    
    # 显示支持的格式
    doc_config = config.get('document', {})
    if 'supported_formats' in doc_config:
        print(f"Supported Formats: {', '.join(doc_config['supported_formats'])}")
    
    print("=" * 40)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Local RAG System - 本地知识库向量化系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s serve                    # 启动API服务器
  %(prog)s ingest ./docs            # 摄入文档
  %(prog)s health                   # 检查系统健康状态
  %(prog)s info                     # 显示系统信息
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # serve命令
    serve_parser = subparsers.add_parser('serve', help='启动API服务器')
    serve_parser.add_argument('--host', default=None, help='服务器地址')
    serve_parser.add_argument('--port', type=int, default=None, help='服务器端口')
    
    # ingest命令
    ingest_parser = subparsers.add_parser('ingest', help='摄入文档')
    ingest_parser.add_argument('directory', help='文档目录路径')
    ingest_parser.add_argument('--force', action='store_true', help='强制重新处理')
    
    # health命令
    health_parser = subparsers.add_parser('health', help='检查系统健康状态')
    
    # info命令
    info_parser = subparsers.add_parser('info', help='显示系统信息')
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging()
    
    # 确保数据目录存在
    config.ensure_directories()
    
    # 执行命令
    if args.command == 'serve':
        # 更新配置
        if args.host:
            config.settings.host = args.host
        if args.port:
            config.settings.port = args.port
        
        start_server()
    
    elif args.command == 'ingest':
        run_ingestion(args.directory, args.force)
    
    elif args.command == 'health':
        check_health()
    
    elif args.command == 'info':
        show_info()
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()