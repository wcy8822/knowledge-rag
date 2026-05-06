#!/bin/bash
# Loki pipeline wrapper —— 系统层硬性内存上限兜底
# 2026-04-28 防 33GB 内存爆事故第三层
#
# 设计：哪怕 Python 代码 GC 失效（issue #154329 复发），ulimit 兜底
# kill 掉进程而不是让 macOS jetsam 把整机搞瘫痪。
#
# 用法: ./loki_pipeline_wrapper.sh [mode] [--max-files N]
# 默认: mode=all max_files=1500
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="/Users/didi/mlx-env/bin/python"
PIPELINE="$SCRIPT_DIR/loki_pipeline.py"
LOG_DIR="$SCRIPT_DIR/logs"

# 内存硬上限：18 GB RSS（M5 Pro 24GB 物理，用户指定跑满到 18G）
# macOS 注意：ulimit -v/-d/-m 在 Darwin 都不生效，必须用后台监控进程兜底
MEM_LIMIT_MB=18432           # 18 * 1024

# 监控周期：每 30 秒检查一次 RSS
WATCH_INTERVAL_SEC=30

# CPU 时间硬上限：90 分钟（防卡死无限跑）
CPU_LIMIT_SEC=5400

# 默认参数
MODE="${1:-all}"
shift 2>/dev/null || true
EXTRA_ARGS=("$@")

# 若用户没传 --max-files，默认全部处理（50000 > 当前 15876 文件总量）
HAS_MAX=false
for a in "${EXTRA_ARGS[@]:-}"; do
    [[ "${a:-}" == --max-files* ]] && HAS_MAX=true
done
if ! $HAS_MAX; then
    EXTRA_ARGS+=(--max-files 50000)
fi

mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d_%H%M%S)
WRAPPER_LOG="$LOG_DIR/wrapper_${TS}.log"

{
    echo "============================================"
    echo "Loki wrapper 启动 $(date '+%F %T')"
    echo "  mode=$MODE"
    echo "  args=${EXTRA_ARGS[*]}"
    echo "  RSS 上限: ${MEM_LIMIT_MB} MB（监控周期 ${WATCH_INTERVAL_SEC}s）"
    echo "  CPU 时间上限: $((CPU_LIMIT_SEC / 60)) 分钟"
    echo "============================================"
} | tee -a "$WRAPPER_LOG"

# CPU 时间兜底（macOS 唯一可用的 ulimit）
ulimit -t "$CPU_LIMIT_SEC" 2>/dev/null || \
    echo "⚠️  ulimit -t 设置失败" | tee -a "$WRAPPER_LOG"

# 关键 PyTorch 环境变量
export PYTHONUNBUFFERED=1
export PYTORCH_ENABLE_MPS_FALLBACK=1   # MPS 不支持的算子自动 fallback CPU
# 注意：不设 PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0（官方警告会致系统崩）

cd "$SCRIPT_DIR"

# 启动 pipeline 到后台
"$PYTHON" "$PIPELINE" "$MODE" "${EXTRA_ARGS[@]}" >> "$WRAPPER_LOG" 2>&1 &
PIPELINE_PID=$!
echo "  pipeline PID=$PIPELINE_PID" | tee -a "$WRAPPER_LOG"

# RSS 监控：每 N 秒检查一次，超限 SIGTERM 优雅退出
KILLED_BY_LIMIT=0
while kill -0 "$PIPELINE_PID" 2>/dev/null; do
    sleep "$WATCH_INTERVAL_SEC"
    RSS_KB=$(ps -o rss= -p "$PIPELINE_PID" 2>/dev/null | tr -d ' ' || echo 0)
    [[ -z "$RSS_KB" || "$RSS_KB" == "0" ]] && continue
    RSS_MB=$((RSS_KB / 1024))
    echo "  [watch] RSS=${RSS_MB}MB (limit=${MEM_LIMIT_MB}MB)" >> "$WRAPPER_LOG"
    if [[ "$RSS_MB" -gt "$MEM_LIMIT_MB" ]]; then
        echo "  ❌ RSS ${RSS_MB}MB 超过上限 ${MEM_LIMIT_MB}MB → SIGTERM" | tee -a "$WRAPPER_LOG"
        kill -TERM "$PIPELINE_PID" 2>/dev/null || true
        sleep 5
        kill -KILL "$PIPELINE_PID" 2>/dev/null || true
        KILLED_BY_LIMIT=1
        break
    fi
done

wait "$PIPELINE_PID" 2>/dev/null
EXIT_CODE=$?
[[ "$KILLED_BY_LIMIT" -eq 1 ]] && EXIT_CODE=137  # 标记内存超限退出
echo "Loki wrapper 结束 exit=$EXIT_CODE $(date '+%F %T')" | tee -a "$WRAPPER_LOG"
exit "$EXIT_CODE"
