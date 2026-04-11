#!/bin/bash
# 本地知识库全量向量化自动化系统 - API 启动脚本
# 版本: v1.0
# 日期: 2026-03-01

set -e

# 配置
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="$PROJECT_DIR/config"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/.api.pid"
API_HOST="127.0.0.1"
API_PORT=8000

# 颜色定义
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
NC='\033[0m'

# 打印函数
print_color() {
    local color=$1
    shift
    echo -e "${color}$*$2${NC}"
    shift
}

print_header() {
    echo ""
    print_color "$GREEN" "╔════════════════════════════╗"
    print_color "$GREEN" "║      M3 Mac 本地知识库 - API 服务           ║"
    print_color "$GREEN" "║      地址: http://$API_HOST:$API_PORT       ║"
    print_color "$GREEN" "║      机器: $(uname -s)                   ║"
    print_color "$GREEN" "║      内存限制: 12GB                      ║"
    print_color "$GREEN" "╚════════════════════════════╝"
    echo ""
}

# 检查环境
check_environment() {
    print_color "$GREEN" "─────────── 环境检查 ───────────"

    # 检查 Python
    if ! command -v python3 &>/dev/null; then
        print_color "$RED" "错误: 未找到 python3，请先安装依赖"
        exit 1
    fi

    # 检查项目目录
    if [ ! -d "$PROJECT_DIR" ]; then
        print_color "$RED" "错误: 项目目录不存在: $PROJECT_DIR"
        exit 1
    fi

    # 检查配置文件
    if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
        print_color "$YELLOW" "警告: 配置文件不存在: $CONFIG_DIR/config.yaml"
    fi

    # 检查端口占用
    if lsof -i ":$API_PORT" 2>/dev/null | grep -q LISTEN | grep -q ":$API_PORT"; then
        print_color "$RED" "错误: 端口 $API_PORT 已被占用"
        print_color "$YELLOW" "占用进程:"
        lsof -i ":$API_PORT" | grep ":$API_PORT" | head -5
        exit 1
    fi

    print_color "$GREEN" "───────── 环境检查完成 ✓"
    echo ""
}

# 启动 API 服务
start_api() {
    print_header

    # 激活虚拟环境（如果存在）
    if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
        source "$PROJECT_DIR/venv/bin/activate"
        print_color "$YELLOW" "已激活虚拟环境"
        echo ""
    fi

    # 进入项目目录
    cd "$PROJECT_DIR"

    # 使用后台模式启动
    print_color "$GREEN" "启动 API 服务（后台模式）..."

    # 检查是否已有进程在运行
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
        if ps -p "$OLD_PID" >/dev/null 2>/dev/null; then
            print_color "$YELLOW" "警告: 检测到已有进程运行 (PID: $OLD_PID)"
            print_color "$YELLOW" "是否停止旧进程？[y/N] (默认: 不停止）"
            read -r -n 1 -p 15
            if [[ $REPLY == [yY] ]]; then
                print_color "$YELLOW" "正在停止旧进程..."
                kill -9 "$OLD_PID" 2>/dev/null || true
            else
                print_color "$YELLOW" "将继续启动新进程"
            fi
        else
            print_color "$YELLOW" "PID 文件存在但进程已不存在，将覆盖"
        rm -f "$PID_FILE"
    fi

    # 启动 API 服务
    python3 -c "
from core.config import Config
from api.server import APIServer

config = Config()
server = APIServer(config)
server.run_background(
    host='$API_HOST',
    port=$API_PORT,
    debug=False
)
" &

    # 保存 PID
    echo "$!" > "$PID_FILE"
    API_PID=$!

    print_color "$GREEN" "API 服务已启动"
    print ""
    print_color "$GREEN" "┌─────────────────────────────────────────────────────────────────────┐"
    print_color "$GREEN" │ API 服务: http://$API_HOST:$API_PORT                           │"
    print_color "$GREEN" │ 健康检查: curl http://$API_HOST:$API_PORT/api/v1/health          │"
    print_color "$GREEN" │ 查看日志: tail -f $LOG_DIR/api.log                           │"
    print_color "$GREEN" │ 停止服务: ./scripts/stop_api.sh                    │"
    print_color "$GREEN" │ 查看状态: ./scripts/check_status.sh                      │"
    print_color "$GREEN" └─────────────────────────────────────────────────────────────────────┘"
    echo ""

    # 显示启动后的服务状态
    sleep 2
    if ps -p "$API_PID" >/dev/null; then
        print_color "$GREEN" "─────────────────────────────────────────────────────────────────────"
        print_color "$GREEN" │ 服务状态: 运行中"
        print_color "$GREEN" │ 进程 PID: $API_PID"
        print_color "$GREEN" │ 内存使用: $(ps -p $API_PID -o rss | awk '{print $1/1024" / 1024} MB')"
        print_color "$GREEN" │ 运行时间: $(ps -o etime=etimes=-p $API_PID | awk '{print $1}') 秒"
        print_color "$GREEN" └─────────────────────────────────────────────────────────────┘"
    else
        print_color "$RED" "API 服务启动失败"
        print_color "$YELLOW" "请查看日志: tail -100 $LOG_DIR/api.log"
    fi
}

# 停止 API 服务
stop_api() {
    print_color "$YELLOW" "停止 API 服务..."

    if [ -f "$PID_FILE" ]; then
        API_PID=$(cat "$PID_FILE" 2>/dev/null)
    if ps -p "$API_PID" >/dev/null 2>/dev/null; then
            print_color "$YELLOW" "正在停止进程 (PID: $API_PID)..."
            kill -9 "$API_PID" 2>/dev/null || true

            # 等待进程完全停止
            for i in {1..10}; do
                if ! ps -p "$API_PID" >/dev/null; then
                    break
                fi
                sleep 1
            done

            rm -f "$PID_FILE"
            print_color "$GREEN" "API 服务已停止"
        else
            print_color "$YELLOW" "未找到运行中的 API 服务"
        fi
    else
        print_color "$YELLOW" "未找到 PID 文件，服务可能未启动"
    fi
}

# 显示帮助
show_help() {
    echo ""
    echo "╔═══════════════════════════════════╗"
    echo "║      M3 Mac 本地知识库 - API 服务帮助                ║"
    echo "╚═════════════════════════════════╝"
    echo ""
    echo "命令："
    echo "  $0 run         ── 启动服务（前台运行）"
    echo "  $0 start       ── 启动服务（后台运行）"
    echo "  $0 stop        ── 停止服务"
    echo "  $0 status       ── 查看状态"
    echo "  $0 help         ── 显示此帮助"
    echo ""
    echo "API 接口："
    echo "  └─ GET  http://127.0.0.1:8000/api/v1/health       ── 健康检查"
    echo "  └─ POST http://127.0.0.1:8000/api/v1/search      ── 搜索文档"
    echo "  └─ POST http://127.0.0.1:8000/api/v1/scan         ── 扫描文件"
    echo "  └─ POST http://127.0.0.1:8000/api/v1/vectorize    ── 批量向量化"
    echo "  └─ GET  http://127.0.0.1:8000/api/v1/stats         ── 获取统计"
    echo ""
    echo "快捷命令："
    echo "  $0 curl -X POST 'http://127.0.0.1:8000/api/v1/search' \\"
    "              -H 'Content-Type: application/json' \\"
    "              -d '{\"query\": \"商户画像\"}'"
    echo ""
}

# 主程序
main() {
    case "$1" in
        run)
            start_api
            ;;
        start)
            start_api
            ;;
        stop)
            stop_api
            ;;
        status)
            # 显示服务状态
            echo "────────────── 服务状态 ───────────────"
            echo ""

            # 检查进程
            if [ -f "$PID_FILE" ]; then
                PID=$(cat "$PID_FILE" 2>/dev/null)
                if ps -p "$PID" >/dev/null 2>/dev/null; then
                    echo "服务状态: 运行中"
                    echo "进程 PID: $PID"
                    echo "运行时间: $(ps -o etimes=-p $PID | awk '{print $1}') 秒"
                    echo ""
                    echo "内存使用: $(ps -p $PID -o rss | awk '{print $1/1024/1024}') MB)"
                    echo ""
                    echo "─────────────────────────────────────────────────────────────────────"
                else
                    echo "服务状态: 未运行"
                fi
            else
                echo "服务状态: 未启动"
            fi

            # 检查 API 接口
            echo "API 接口测试："
            curl -s http://127.0.0.1:8000/api/v1/health 2>&1 || echo "API 接口无法访问"
            echo ""
            echo "─────────────────────────────────────────────────────────────────────"
            ;;
        help)
            show_help
            ;;
        *)
            echo "未知命令: $1"
            show_help
            ;;
    esac
}

# 如果脚本被直接执行，运行主程序
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
