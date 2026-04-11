#!/bin/bash

# 本地RAG系统启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Local RAG System...${NC}"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found. Please run ./scripts/setup.sh first${NC}"
    exit 1
fi

# 激活虚拟环境
echo -e "${YELLOW}🔄 Activating virtual environment...${NC}"
source venv/bin/activate

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    if [ -f "config.yaml.template" ]; then
        echo -e "${YELLOW}📝 Creating config.yaml from template...${NC}"
        cp config.yaml.template config.yaml
    else
        echo -e "${RED}❌ Configuration file not found${NC}"
        exit 1
    fi
fi

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}🔐 Creating .env file...${NC}"
    cat > .env << EOF
# Local RAG System Environment Variables
APP_NAME=Local RAG System
DEBUG=false
HOST=0.0.0.0
PORT=8000
DATA_BASE_DIR=./data
CHROMA_DIR=./data/chroma
METADATA_DIR=./data/metadata
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cpu
VECTOR_DB_PROVIDER=chroma
ALLOW_CLOUD_EMBEDDING=false
LOG_LEVEL=INFO
EOF
fi

# 设置PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# 创建日志目录
mkdir -p logs

# 检查端口是否被占用
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️ Port 8000 is already in use${NC}"
    read -p "Do you want to kill the process and continue? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}🔄 Killing process on port 8000...${NC}"
        lsof -ti:8000 | xargs kill -9 2>/dev/null || true
        sleep 2
    else
        echo -e "${RED}❌ Please choose a different port or stop the conflicting process${NC}"
        exit 1
    fi
fi

# 健康检查函数
health_check() {
    local max_attempts=30
    local attempt=1
    
    echo -e "${BLUE}🏥 Waiting for service to be healthy...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/health >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Service is healthy!${NC}"
            return 0
        fi
        
        echo -e "${YELLOW}⏳ Attempt $attempt/$max_attempts...${NC}"
        sleep 2
        ((attempt++))
    done
    
    echo -e "${RED}❌ Service failed to become healthy${NC}"
    return 1
}

# 启动服务的函数
start_service() {
    echo -e "${GREEN}🚀 Starting Local RAG System API...${NC}"
    echo -e "${BLUE}📊 API will be available at: http://localhost:8000${NC}"
    echo -e "${BLUE}📚 API Documentation: http://localhost:8000/docs${NC}"
    echo -e "${BLUE}📊 Alternative Docs: http://localhost:8000/redoc${NC}"
    echo -e "${YELLOW}🛑 Press Ctrl+C to stop the service${NC}"
    echo ""
    
    # 启动API服务器
    cd "$(pwd)"
    python3 -m uvicorn src.serve.api.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --log-level info \
        --access-log \
        --reload
}

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down Local RAG System...${NC}"
    
    # 清理临时文件
    rm -f /tmp/rag-system-*.pid
    
    echo -e "${GREEN}✅ Service stopped${NC}"
    exit 0
}

# 设置信号处理
trap cleanup SIGINT SIGTERM

# 检查依赖是否正确安装
echo -e "${BLUE}🔍 Checking dependencies...${NC}"
python3 -c "
import sys
sys.path.insert(0, 'src')
try:
    from src.config import config
    from src.serve.api.main import app
    print('✅ Dependencies loaded successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'⚠️ Warning: {e}')
"

# 创建必要的目录
mkdir -p data/{chroma,qdrant,metadata,uploads,logs}

# 启动服务
if [ "$1" = "--no-health-check" ]; then
    start_service
else
    # 后台启动并执行健康检查
    start_service &
    SERVICE_PID=$!
    
    # 等待几秒让服务启动
    sleep 3
    
    # 执行健康检查
    if health_check; then
        echo -e "${GREEN}🎉 Local RAG System started successfully!${NC}"
        echo ""
        echo -e "${BLUE}📊 Service Information:${NC}"
        echo -e "   • API Endpoint: ${BLUE}http://localhost:8000${NC}"
        echo -e "   • API Docs: ${BLUE}http://localhost:8000/docs${NC}"
        echo -e "   • Health Check: ${BLUE}http://localhost:8000/health${NC}"
        echo -e "   • System Info: ${BLUE}http://localhost:8000/info${NC}"
        echo ""
        echo -e "${BLUE}📝 Logs:${NC}"
        echo -e "   • Application: ${YELLOW}logs/app.log${NC}"
        echo -e "   • Access: ${YELLOW}logs/access.log${NC}"
        echo ""
        echo -e "${GREEN}🔍 API Testing Examples:${NC}"
        echo -e "   • Health: ${BLUE}curl http://localhost:8000/health${NC}"
        echo -e "   • Search: ${BLUE}curl -X POST http://localhost:8000/api/v1/search \\${NC}"
        echo -e "     ${BLUE}  -H 'Content-Type: application/json' \\${NC}"
        echo -e "     ${BLUE}  -d '{\"query\": \"test\", \"top_k\": 5}'${NC}"
        echo ""
        
        # 等待服务进程
        wait $SERVICE_PID
    else
        echo -e "${RED}❌ Failed to start service${NC}"
        kill $SERVICE_PID 2>/dev/null || true
        exit 1
    fi
fi