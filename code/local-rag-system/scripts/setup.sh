#!/bin/bash

# 本地RAG系统环境设置脚本

set -e

echo "🚀 Setting up Local RAG System..."

# 检查Python版本
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python $required_version+ is required. Current version: $python_version"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# 升级pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# 安装依赖
echo "📚 Installing dependencies..."
pip install -r requirements.txt

if [ -f "requirements-dev.txt" ]; then
    echo "📚 Installing development dependencies..."
    pip install -r requirements-dev.txt
fi

# 创建必要的目录
echo "📁 Creating directories..."
mkdir -p data/{chroma,qdrant,metadata,uploads,logs}
mkdir -p logs

# 复制配置文件
if [ ! -f "config.yaml" ] && [ -f "config.yaml.template" ]; then
    echo "⚙️ Copying configuration template..."
    cp config.yaml.template config.yaml
    echo "📝 Please edit config.yaml according to your environment"
fi

# 创建环境变量文件
if [ ! -f ".env" ]; then
    echo "🔐 Creating environment file..."
    cat > .env << EOF
# Local RAG System Environment Variables

# 应用配置
APP_NAME=Local RAG System
DEBUG=false
HOST=0.0.0.0
PORT=8000

# 数据存储
DATA_BASE_DIR=./data
CHROMA_DIR=./data/chroma
METADATA_DIR=./data/metadata

# 嵌入配置
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cpu

# 向量数据库
VECTOR_DB_PROVIDER=chroma

# 安全配置
ALLOW_CLOUD_EMBEDDING=false

# 日志配置
LOG_LEVEL=INFO
EOF
fi

# 设置权限
echo "🔐 Setting permissions..."
chmod +x scripts/*.sh

# 检查模型下载
echo "🤖 Checking embedding model availability..."
python3 -c "
from transformers import AutoTokenizer
try:
    tokenizer = AutoTokenizer.from_pretrained('BAAI/bge-m3', trust_remote_code=True)
    print('✅ BGE-M3 tokenizer accessible')
except Exception as e:
    print(f'⚠️ BGE-M3 tokenizer not immediately accessible: {e}')
    print('   Models will be downloaded on first use')
"

# 创建日志文件
touch logs/app.log
touch logs/access.log

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Edit config.yaml for your environment"
echo "2. Run: ./scripts/serve.sh"
echo "3. Visit: http://localhost:8000"
echo "4. Check API docs: http://localhost:8000/docs"
echo ""
echo "Configuration files:"
echo "- config.yaml (main configuration)"
echo "- .env (environment variables)"
echo ""
echo "Data directories:"
echo "- data/uploads (for document upload)"
echo "- data/chroma (vector database)"
echo "- data/metadata (metadata storage)"
echo "- logs/ (application logs)"