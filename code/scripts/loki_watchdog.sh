#!/bin/bash
# Loki Watchdog — 持续守护向量化流水线
# 崩溃自动重启，每轮完成后休眠再跑（全量扫描增量处理）
# 用法: nohup bash loki_watchdog.sh &

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE="$SCRIPT_DIR/loki_pipeline.py"
LOG_DIR="$SCRIPT_DIR/logs"
WATCHDOG_LOG="$LOG_DIR/loki_watchdog.log"
PID_FILE="$LOG_DIR/loki.pid"

PYTHON="/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python"
# 每轮完成后休眠时间（秒）。3600=1小时后再扫一次增量
SLEEP_INTERVAL=3600
# 最大连续失败次数，超过则等更长时间
MAX_FAIL=3

mkdir -p "$LOG_DIR"
echo $$ > "$PID_FILE"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$WATCHDOG_LOG"
}

log "=== Loki Watchdog 启动 PID=$$ ==="
log "流水线: $PIPELINE"
log "每轮间隔: ${SLEEP_INTERVAL}秒"

fail_count=0

while true; do
    log "--- 启动流水线 ---"
    "$PYTHON" "$PIPELINE" all >> "$WATCHDOG_LOG" 2>&1
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        fail_count=0
        log "流水线正常完成 (exit=0)，等待 ${SLEEP_INTERVAL}s 后增量扫描"
        sleep $SLEEP_INTERVAL
    else
        fail_count=$((fail_count + 1))
        log "流水线异常退出 (exit=$EXIT_CODE) 连续失败=$fail_count"

        if [ $fail_count -ge $MAX_FAIL ]; then
            WAIT=$((SLEEP_INTERVAL * 2))
            log "连续失败${fail_count}次，等待更长时间 ${WAIT}s"
            sleep $WAIT
            fail_count=0
        else
            log "30秒后重试..."
            sleep 30
        fi
    fi
done
