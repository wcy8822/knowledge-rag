#!/usr/bin/env python3
"""
Loki Health Check -- 系统健康检查
用法: python3 loki_health.py
"""

import os, sys, json, time, subprocess
from pathlib import Path
from datetime import datetime

CHROMA_DIR   = "/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge"
LOG_DIR      = Path("/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs")
LOCK_FILE    = Path(CHROMA_DIR) / ".loki_write.lock"
BGE_PATH     = "/Users/didi/Work/projects/knowledge-rag-知识库/bge-m3-model/bge-m3/BAAI/bge-m3"
SCRIPTS_DIR  = Path("/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts")

STATE_FILES = {
    'pipeline': LOG_DIR / "loki_state.json",
    'reindex':  LOG_DIR / "loki_reindex_state.json",
    'chunk':    LOG_DIR / "loki_chunk_state.json",
}

COLLECTIONS = ['doc_knowledge_bge_m3', 'ddl_schema_bge_m3', 'doc_knowledge_chunks']


def check_chromadb():
    """检查 ChromaDB 状态"""
    print("\n[ChromaDB]")
    try:
        import chromadb
        client = chromadb.PersistentClient(CHROMA_DIR)
        total = 0
        for name in COLLECTIONS:
            try:
                col = client.get_collection(name)
                count = col.count()
                total += count
                print(f"  OK  {name}: {count} records")
            except Exception:
                print(f"  --  {name}: NOT FOUND")

        print(f"  Total: {total} records")

        # 磁盘大小
        db_size = sum(f.stat().st_size for f in Path(CHROMA_DIR).rglob('*') if f.is_file())
        print(f"  Disk: {db_size / 1024 / 1024:.1f} MB")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def check_ollama():
    """检查 Ollama 状态"""
    print("\n[Ollama]")
    try:
        result = subprocess.run(['curl', '-s', 'http://localhost:11434/api/tags'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            models = data.get('models', [])
            for m in models:
                name = m.get('name', '?')
                size_gb = m.get('size', 0) / 1024 / 1024 / 1024
                print(f"  OK  {name} ({size_gb:.1f} GB)")
            return True
        else:
            print(f"  FAIL: curl returned {result.returncode}")
            return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def check_processes():
    """检查 Loki 相关进程"""
    print("\n[Processes]")
    found = False
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'loki_' in line and 'grep' not in line:
                parts = line.split()
                pid = parts[1]
                cpu = parts[2]
                mem = parts[3]
                cmd = ' '.join(parts[10:])
                # 提取脚本名
                for script in ['loki_pipeline', 'loki_reindex', 'loki_chunk', 'loki_watchdog']:
                    if script in cmd:
                        nice = ''
                        try:
                            ni = subprocess.run(['ps', '-p', pid, '-o', 'ni='],
                                                capture_output=True, text=True)
                            nice = f" NI={ni.stdout.strip()}"
                        except Exception:
                            pass
                        print(f"  RUN  PID={pid} CPU={cpu}% MEM={mem}%{nice} {script}")
                        found = True
                        break
    except Exception:
        pass

    if not found:
        print(f"  --  No Loki processes running")

    # 检查 launchd
    try:
        result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
        if 'com.didi.loki' in result.stdout:
            print(f"  OK  launchd com.didi.loki loaded")
        else:
            print(f"  --  launchd com.didi.loki NOT loaded")
    except Exception:
        pass


def check_state_files():
    """检查 state 文件"""
    print("\n[State Files]")
    for name, path in STATE_FILES.items():
        if path.exists():
            try:
                data = json.loads(path.read_text())
                mtime = datetime.fromtimestamp(path.stat().st_mtime)
                print(f"  OK  {name}: {len(data)} entries (updated {mtime.strftime('%Y-%m-%d %H:%M')})")
            except Exception as e:
                print(f"  WARN {name}: exists but parse failed: {e}")
        else:
            print(f"  --  {name}: not found")


def check_lock():
    """检查写锁状态"""
    print("\n[Write Lock]")
    if LOCK_FILE.exists():
        try:
            content = LOCK_FILE.read_text().strip()
            if content:
                print(f"  LOCK held by: {content}")
            else:
                print(f"  OK  lock file exists, not held")
        except Exception:
            print(f"  OK  lock file exists")
    else:
        print(f"  OK  no lock file")


def check_logs():
    """检查最新日志"""
    print("\n[Latest Logs]")
    patterns = ['loki_2*.log', 'loki_reindex_2*.log', 'loki_chunk_2*.log']
    for pattern in patterns:
        logs = sorted(LOG_DIR.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
        if logs:
            latest = logs[0]
            mtime = datetime.fromtimestamp(latest.stat().st_mtime)
            size_kb = latest.stat().st_size / 1024
            # 读最后一行看状态
            try:
                lines = latest.read_text(encoding='utf-8', errors='ignore').strip().split('\n')
                last = lines[-1] if lines else '(empty)'
                print(f"  {latest.name} ({size_kb:.0f}KB, {mtime.strftime('%m-%d %H:%M')})")
                print(f"    last: {last[:100]}")
            except Exception:
                print(f"  {latest.name} ({size_kb:.0f}KB)")


def check_model():
    """检查 BGE-M3 模型"""
    print("\n[BGE-M3 Model]")
    model_path = Path(BGE_PATH)
    if model_path.exists():
        size = sum(f.stat().st_size for f in model_path.rglob('*') if f.is_file())
        print(f"  OK  {size / 1024 / 1024 / 1024:.1f} GB at {BGE_PATH}")
    else:
        print(f"  FAIL: model not found at {BGE_PATH}")


def main():
    print("=" * 60)
    print(f"Loki Health Check  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    check_chromadb()
    check_ollama()
    check_processes()
    check_state_files()
    check_lock()
    check_logs()
    check_model()

    print("\n" + "=" * 60)
    print("Health check complete.")


if __name__ == '__main__':
    main()
