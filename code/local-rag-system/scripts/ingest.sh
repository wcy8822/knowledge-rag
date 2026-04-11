#!/bin/bash

# 本地RAG系统文档摄入脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认参数
INPUT_DIR="./data/uploads"
FORCE_REPROCESS=false
BATCH_SIZE=100
VERBOSE=false

# 显示帮助信息
show_help() {
    echo "Local RAG System Document Ingestion Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -i, --input-dir DIR     Input directory containing documents (default: ./data/uploads)"
    echo "  -f, --force-force     Force reprocess existing documents"
    echo "  -b, --batch-size NUM   Batch size for processing (default: 100)"
    echo "  -v, --verbose         Verbose output"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Process default directory"
    echo "  $0 -i /path/to/documents              # Process specific directory"
    echo "  $0 -f -b 50                        # Force reprocess with batch size 50"
    echo "  $0 -i ./docs -v                      # Verbose processing"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--input-dir)
            INPUT_DIR="$2"
            shift 2
            ;;
        -f|--force-reprocess)
            FORCE_REPROCESS=true
            shift
            ;;
        -b|--batch-size)
            BATCH_SIZE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 验证参数
if [ ! -d "$INPUT_DIR" ]; then
    echo -e "${RED}❌ Input directory does not exist: $INPUT_DIR${NC}"
    exit 1
fi

if [[ ! $BATCH_SIZE =~ ^[0-9]+$ ]] || [ $BATCH_SIZE -lt 1 ]; then
    echo -e "${RED}❌ Invalid batch size: $BATCH_SIZE${NC}"
    exit 1
fi

echo -e "${BLUE}📚 Local RAG System Document Ingestion${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# 显示配置信息
echo -e "${YELLOW}⚙️ Configuration:${NC}"
echo -e "   Input Directory: ${GREEN}$INPUT_DIR${NC}"
echo -e "   Force Reprocess: ${GREEN}$FORCE_REPROCESS${NC}"
echo -e "   Batch Size: ${GREEN}$BATCH_SIZE${NC}"
echo -e "   Verbose: ${GREEN}$VERBOSE${NC}"
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found. Please run ./scripts/setup.sh first${NC}"
    exit 1
fi

# 激活虚拟环境
echo -e "${YELLOW}🔄 Activating virtual environment...${NC}"
source venv/bin/activate

# 设置PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo -e "${RED}❌ Configuration file not found. Please run ./scripts/setup.sh first${NC}"
    exit 1
fi

# 统计文件数量
FILE_COUNT=$(find "$INPUT_DIR" -type f \( -name "*.pdf" -o -name "*.xlsx" -o -name "*.pptx" -o -name "*.md" -o -name "*.docx" -o -name "*.txt" -o -name "*.html" -o -name "*.py" -o -name "*.js" -o -name "*.java" -o -name "*.cpp" -o -name "*.c" -o -name "*.go" -o -name "*.rs" \) | wc -l)

echo -e "${BLUE}📊 Found ${GREEN}$FILE_COUNT${NC} supported files to process"

if [ $FILE_COUNT -eq 0 ]; then
    echo -e "${YELLOW}⚠️ No supported files found in $INPUT_DIR${NC}"
    echo "Supported file types: PDF, Excel, PowerPoint, Markdown, Word, Text, HTML, Python, JavaScript, Java, C++, C, Go, Rust"
    exit 0
fi

# 创建Python脚本用于文档摄入
cat > /tmp/ingest_documents.py << 'EOF'
import sys
import os
import time
from pathlib import Path
import argparse
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Ingest documents into Local RAG System')
    parser.add_argument('--input-dir', required=True, help='Input directory')
    parser.add_argument('--force-reprocess', action='store_true', help='Force reprocess')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    try:
        # 导入必要的模块
        from src.config import config
        from src.ingest.processor import DocumentProcessor
        
        # 初始化处理器
        processor = DocumentProcessor(config.get('document', {}))
        
        # 查找支持的文件
        input_path = Path(args.input_dir)
        supported_extensions = ['.pdf', '.xlsx', '.pptx', '.md', '.docx', '.txt', '.html', '.py', '.js', '.java', '.cpp', '.c', '.go', '.rs']
        
        file_paths = []
        for ext in supported_extensions:
            file_paths.extend(input_path.glob(f'*{ext}'))
            file_paths.extend(input_path.glob(f'*{ext.upper()}'))
        
        if not file_paths:
            logger.warning(f"No supported files found in {args.input_dir}")
            return
        
        logger.info(f"Found {len(file_paths)} files to process")
        
        # 分批处理文件
        file_paths_str = [str(fp) for fp in file_paths]
        
        start_time = time.time()
        total_processed = 0
        total_failed = 0
        
        for i in range(0, len(file_paths_str), args.batch_size):
            batch_files = file_paths_str[i:i + args.batch_size]
            batch_num = i // args.batch_size + 1
            
            logger.info(f"Processing batch {batch_num} ({len(batch_files)} files)")
            
            try:
                from src.models import IngestRequest
                request = IngestRequest(
                    file_paths=batch_files,
                    force_reprocess=args.force_reprocess,
                    batch_id=f"batch_{int(time.time())}_{batch_num}"
                )
                
                response = processor.process_request(request)
                
                logger.info(f"Batch {batch_num} completed:")
                logger.info(f"  Successful: {response.successful}")
                logger.info(f"  Failed: {response.failed}")
                logger.info(f"  Time: {response.processing_time_seconds:.2f}s")
                
                total_processed += response.successful
                total_failed += response.failed
                
                if response.failed_files and args.verbose:
                    for failed_file in response.failed_files:
                        logger.error(f"  Failed: {failed_file['file_path']} - {failed_file['error']}")
                
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {e}")
                total_failed += len(batch_files)
        
        total_time = time.time() - start_time
        
        # 输出总结
        logger.info("=" * 50)
        logger.info("Ingestion Summary:")
        logger.info(f"  Total files: {len(file_paths_str)}")
        logger.info(f"  Successful: {total_processed}")
        logger.info(f"  Failed: {total_failed}")
        logger.info(f"  Total time: {total_time:.2f}s")
        logger.info(f"  Average time per file: {total_time/len(file_paths_str):.2f}s")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Fatal error during ingestion: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

# 运行文档摄入
echo -e "${GREEN}🚀 Starting document ingestion...${NC}"
echo ""

INGESTION_START=$(date +%s)

python3 /tmp/ingest_documents.py \
    --input-dir "$INPUT_DIR" \
    $(if [ "$FORCE_REPROCESS" = true ]; then echo "--force-reprocess"; fi) \
    --batch-size "$BATCH_SIZE" \
    $(if [ "$VERBOSE" = true ]; then echo "--verbose"; fi)

INGESTION_END=$(date +%s)
INGESTION_DURATION=$((INGESTION_END - INGESTION_START))

# 清理临时文件
rm -f /tmp/ingest_documents.py

# 显示完成信息
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Document ingestion completed successfully!${NC}"
    echo -e "${YELLOW}⏱️ Total time: ${GREEN}$INGESTION_DURATION${NC} seconds"
    echo ""
    echo -e "${BLUE}📊 Next steps:${NC}"
    echo -e "   • Start the API server: ${YELLOW}./scripts/serve.sh${NC}"
    echo -e "   • Visit the API docs: ${BLUE}http://localhost:8000/docs${NC}"
    echo -e "   • Test with: ${BLUE}curl -X POST http://localhost:8000/api/v1/search \\${NC}"
    echo -e "     ${BLUE}  -H 'Content-Type: application/json' \\${NC}"
    echo -e "     ${BLUE}  -d '{\"query\": \"your search query\"}'${NC}"
else
    echo -e "${RED}❌ Document ingestion failed${NC}"
    echo ""
    echo -e "${YELLOW}🔍 Check the logs above for error details${NC}"
    exit 1
fi