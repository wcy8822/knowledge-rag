#!/bin/bash

# BGE-M3 模型下载脚本 - 使用国内镜像和替代方案

echo "=========================================="
echo "BGE-M3 模型下载工具"
echo "=========================================="
echo ""

# 方案 1：尝试使用 huggingface_hub（如果 modelscope 失败）
echo "方案 1: 使用 huggingface_hub + 国内镜像"
echo "----------------------------------------"
echo "安装依赖..."
pip3 install -U huggingface-hub

# 设置国内镜像源
export HF_ENDPOINT=https://hf-mirror.com

echo "从 HF 镜像下载 BGE-M3 模型..."
huggingface-cli download BAAI/bge-m3 \
  --local-dir ~/models/bge-m3 \
  --local-dir-use-symlinks False \
  --resume-download

echo ""
echo "下载完成！"
echo "模型位置: ~/models/bge-m3"
