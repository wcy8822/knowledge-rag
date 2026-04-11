#!/bin/bash
# 本地知识库全量向量化自动化系统 - 停止 API 服务脚本
# 版本: v1.0
# 日期: 2026-03-01

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$PROJECT_DIR/.api.pid"

echo "========================================"
echo "  停止 API 服务"
echo "========================================"
echo ""

# 读取 PID
if [ -f "$PID_FILE" ]; then
    API_PID=$(cat "$PID_FILE")
    echo "读取到 PID: $API_PID"

    # 检查进程是否存在
    if ps -p $API_PID > /dev/null 2>&1; then
        echo "正在停止进程 $API_PID..."
        kill $API_PID

        # 等待进程结束
        for i in {1..10}; do
            if ! ps -p $API_PID > /dev/null 2>&1; then
                echo "进程已停止"
                break
            fi
            echo "等待进程结束... ($i/10)"
            sleep 1
        done

        # 强制杀死
        if ps -p $API_PID > /dev/null 2>&1; then
            echo "强制停止进程..."
            kill -9 $API_PID
        fi
    else
        echo "进程 $API_PID 不存在"
    fi

    # 删除 PID 文件
    rm -f "$PID_FILE"
else
    echo "未找到 PID 文件，尝试按名称查找进程..."

    # 查找 Python API 进程
    PIDS=$(pgrep -f "api.server")

    if [ -n "$PIDS" ]; then
        echo "找到进程: $PIDS"
        echo $PIDS | xargs kill
        echo "进程已停止"
    else
        echo "未找到运行中的 API 服务"
    fi
fi

echo ""
echo "========================================"
echo "  API 服务已停止"
echo "========================================"
