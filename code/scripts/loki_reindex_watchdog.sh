#!/bin/bash
# Loki Reindex Watchdog — 崩溃自动重启 + 卡死检测
# 加固 2026-04-07: 除了崩溃重启，还检测日志超时(10分钟无更新=卡死)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python"
SCRIPT="$SCRIPT_DIR/loki_reindex.py"
LOG_DIR="$SCRIPT_DIR/logs"
STDOUT_LOG="$LOG_DIR/reindex_stdout.log"
WATCHDOG_LOG="$LOG_DIR/reindex_watchdog.log"

MAX_FAILURES=3           # 连续崩溃N次后等待
COOLDOWN=7200            # 等待2小时
STALL_TIMEOUT=600        # 10分钟无日志更新判定为卡死
CHECK_INTERVAL=30        # 每30秒检查一次

failures=0

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] $1" >> "$WATCHDOG_LOG"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] $1"
}

get_log_age() {
    # 返回最新reindex日志文件距今的秒数
    local latest_log=$(ls -t "$LOG_DIR"/loki_reindex_*.log 2>/dev/null | head -1)
    if [ -z "$latest_log" ]; then
        echo 0
        return
    fi
    local mod_epoch=$(stat -f %m "$latest_log" 2>/dev/null || echo 0)
    local now_epoch=$(date +%s)
    echo $(( now_epoch - mod_epoch ))
}

kill_stale() {
    # 杀掉卡死的reindex进程
    local pid=$1
    log "进程 $pid 卡死超过 ${STALL_TIMEOUT}s，强制杀掉"
    kill -9 "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
}

log "====== Reindex Watchdog 启动 ======"

while true; do
    log "启动 reindex (第 $((failures+1)) 次尝试)"
    $PYTHON "$SCRIPT" >> "$STDOUT_LOG" 2>&1 &
    PID=$!
    log "reindex PID=$PID"

    # 监控循环
    while true; do
        sleep $CHECK_INTERVAL

        # 检查进程是否还在
        if ! kill -0 "$PID" 2>/dev/null; then
            wait "$PID"
            EXIT_CODE=$?
            if [ $EXIT_CODE -eq 0 ]; then
                log "reindex 正常完成 (exit 0)"
                log "====== Watchdog 任务完成，退出 ======"
                exit 0
            else
                log "reindex 异常退出 (exit $EXIT_CODE)"
                failures=$((failures + 1))
                break
            fi
        fi

        # 检查是否卡死（日志超时）
        AGE=$(get_log_age)
        if [ "$AGE" -gt "$STALL_TIMEOUT" ]; then
            kill_stale "$PID"
            log "卡死超时，视为崩溃"
            failures=$((failures + 1))
            break
        fi
    done

    # 连续崩溃保护
    if [ $failures -ge $MAX_FAILURES ]; then
        log "连续崩溃 $failures 次，等待 ${COOLDOWN}s 后重试"
        sleep $COOLDOWN
        failures=0
    else
        log "30s 后重启..."
        sleep 30
    fi
done
