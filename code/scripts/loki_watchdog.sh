#!/bin/bash
# Loki Watchdog — 持续守护向量化流水线
# 崩溃自动重启，每轮完成后休眠再跑（全量扫描增量处理）
# 用法: nohup bash loki_watchdog.sh &

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE="$SCRIPT_DIR/loki_pipeline.py"
LOG_DIR="$SCRIPT_DIR/logs"
WATCHDOG_LOG="$LOG_DIR/loki_watchdog.log"
PID_FILE="$LOG_DIR/loki.pid"

PYTHON="/opt/homebrew/bin/python3"
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
        # 提取本轮统计
        DOC_COUNT=$(grep -o '文档库: [0-9]*' "$WATCHDOG_LOG" | tail -1 | grep -o '[0-9]*')
        DDL_COUNT=$(grep -o 'DDL库:  [0-9]*' "$WATCHDOG_LOG" | tail -1 | grep -o '[0-9]*')
        NEW_DOCS=$(grep -c '✅ 批次入库' "$LOG_DIR"/loki_$(date +%Y%m%d)*.log 2>/dev/null || echo 0)
        SUMMARY="文档${DOC_COUNT:-?} DDL${DDL_COUNT:-?} 本轮入库${NEW_DOCS}批"
        log "流水线正常完成 (exit=0)，${SUMMARY}，等待 ${SLEEP_INTERVAL}s"
        osascript -e "display notification \"${SUMMARY}\" with title \"Loki ✅\" subtitle \"下次扫描 1h 后\"" 2>/dev/null
        sleep $SLEEP_INTERVAL
    else
        fail_count=$((fail_count + 1))
        log "流水线异常退出 (exit=$EXIT_CODE) 连续失败=$fail_count"
        osascript -e "display notification \"exit=$EXIT_CODE 连续失败$fail_count\" with title \"Loki ❌\" subtitle \"流水线异常\"" 2>/dev/null

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
