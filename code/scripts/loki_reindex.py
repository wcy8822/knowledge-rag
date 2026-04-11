#!/usr/bin/env python3
"""
Loki Phase 1 — 摘要重建
对已入库的文档用 qwen2.5:7b 生成摘要，重新embed提升搜索质量
策略:
  - .md/.pdf/.docx 叙述类: qwen摘要 → embed
  - .py/.sql/.sh  代码类: 提取函数名+注释 → embed
  - .xlsx         表格类: 提取sheet+表头 → embed
断点续跑: state文件记录已处理的ID

加固 2026-04-07:
  - subprocess级硬超时(60s)，防止qwen卡死
  - 互斥锁(flock)，防止pipeline和reindex并发写ChromaDB
  - 单条异常不阻塞，强制跳过并记录
"""

import sys, os, time, json, hashlib, logging, requests, fcntl, signal
from datetime import datetime
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired

import pymysql
import chromadb
from sentence_transformers import SentenceTransformer

BGE_PATH   = "/Users/didi/Work/projects/knowledge-rag-知识库/bge-m3-model/bge-m3/BAAI/bge-m3"
CHROMA_DIR = "/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge"
LOG_DIR    = Path("/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs")
STATE_FILE = LOG_DIR / "loki_reindex_state.json"

COLLECTION  = "doc_knowledge_bge_m3"
OLLAMA_URL  = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"
BATCH_SIZE  = 5
MAX_CHARS   = 3000
OLLAMA_HARD_TIMEOUT = 60  # 秒，subprocess级硬超时
LOCK_FILE   = Path("/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge/.loki_write.lock")

# 日志
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"loki_reindex_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger('reindex')


def load_state() -> set:
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()))
        except Exception:
            pass
    return set()

def save_state(done: set):
    STATE_FILE.write_text(json.dumps(list(done)))


class ChromaLock:
    """文件锁，防止pipeline和reindex并发写ChromaDB"""
    def __init__(self):
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(LOCK_FILE, 'w')

    def acquire(self):
        try:
            fcntl.flock(self._fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._fp.write(f"reindex:{os.getpid()}\n")
            self._fp.flush()
            return True
        except (IOError, OSError):
            return False

    def release(self):
        try:
            fcntl.flock(self._fp, fcntl.LOCK_UN)
            self._fp.close()
        except Exception:
            pass


def ollama_summarize(fname: str, text: str) -> str:
    """qwen2.5:7b 生成摘要，双重超时保护：requests 90s + subprocess 硬杀 60s"""
    prompt = f"""请用3-5句中文总结以下文档的核心内容，提取关键术语、主要结论和业务含义：

文件名: {fname}
内容:
{text[:2500]}

摘要（只输出摘要，不要解释）："""

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 250}
    })

    # subprocess 硬超时：即使 ollama 卡死也能杀掉
    try:
        proc = Popen(
            ['curl', '-s', '-m', str(OLLAMA_HARD_TIMEOUT),
             '-H', 'Content-Type: application/json',
             '-d', '@-', OLLAMA_URL],
            stdin=PIPE, stdout=PIPE, stderr=PIPE
        )
        stdout, stderr = proc.communicate(input=payload.encode(), timeout=OLLAMA_HARD_TIMEOUT + 10)

        if proc.returncode == 0 and stdout:
            data = json.loads(stdout)
            summary = data.get('response', '').strip()
            if len(summary) > 20:
                return summary
    except TimeoutExpired:
        proc.kill()
        proc.wait()
        log.warning(f"  ⏰ 硬超时({OLLAMA_HARD_TIMEOUT}s)跳过: {fname}")
    except Exception as e:
        log.warning(f"  ollama失败: {e}")
    return None


def extract_code_signature(text: str, ext: str) -> str:
    """代码文件提取关键签名，不调LLM"""
    lines = text.split('\n')
    sigs = []
    for line in lines:
        s = line.strip()
        # Python: def/class/注释
        if ext == '.py' and (s.startswith('def ') or s.startswith('class ') or s.startswith('#')):
            sigs.append(s[:100])
        # SQL: CREATE/SELECT/注释
        elif ext in ('.sql',) and (s.upper().startswith(('CREATE', 'SELECT', 'INSERT', 'ALTER', '--', '/*'))):
            sigs.append(s[:100])
        # Shell: 注释和主命令
        elif ext == '.sh' and (s.startswith('#') or s.startswith('function ')):
            sigs.append(s[:100])
        if len(sigs) >= 30:
            break
    return '\n'.join(sigs) if sigs else text[:500]


def extract_excel_structure(path: str) -> str:
    """Excel提取结构"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parts = []
        for ws in wb.worksheets:
            parts.append(f"Sheet: {ws.title}")
            # 只取前3行作为表头样本
            for i, row in enumerate(ws.iter_rows(max_row=3, values_only=True)):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    parts.append('  ' + ' | '.join(cells[:10]))
        return '\n'.join(parts)
    except Exception:
        return ''


def build_embed_text(doc_id: str, doc_text: str, meta: dict) -> str:
    """根据文件类型构建高质量的embed文本"""
    path = meta.get('path', '')
    name = meta.get('name', Path(path).name if path else '')
    ext  = meta.get('ext', Path(path).suffix.lower() if path else '')

    # 读原文
    try:
        raw = Path(path).read_text(encoding='utf-8', errors='ignore') if path and Path(path).exists() else doc_text
    except Exception:
        raw = doc_text

    raw = raw.strip()
    if not raw:
        return doc_text

    # 代码类: 提取签名，不调LLM
    if ext in ('.py', '.sql', '.sh', '.js', '.ts'):
        sig = extract_code_signature(raw, ext)
        return f"文件:{name}\n类型:代码({ext})\n关键内容:\n{sig}"

    # Excel: 提取结构
    if ext == '.xlsx' and path and Path(path).exists():
        struct = extract_excel_structure(path)
        return f"文件:{name}\n{struct}" if struct else doc_text

    # 叙述类(.md/.pdf/.docx/.txt): 调qwen摘要
    summary = ollama_summarize(name, raw)
    if summary:
        return f"文件:{name}\n摘要:{summary}\n原文片段:{raw[:300]}"

    # 摘要失败，用原文前500字
    return f"文件:{name}\n{raw[:500]}"


def run_reindex():
    log.info("=" * 60)
    log.info(f"Loki Phase 1 重建摘要 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 互斥锁：防止和pipeline并发写ChromaDB
    lock = ChromaLock()
    if not lock.acquire():
        log.error("❌ 无法获取写锁，pipeline可能正在运行。退出。")
        sys.exit(1)
    log.info("🔒 已获取ChromaDB写锁")

    log.info("加载 BGE-M3...")
    model = SentenceTransformer(BGE_PATH)

    client = chromadb.PersistentClient(CHROMA_DIR)
    col = client.get_collection(COLLECTION)
    total = col.count()
    log.info(f"当前库: {total} 条")

    done = load_state()
    log.info(f"已重建: {len(done)} 条")

    # 分批读取所有记录
    page_size = 200
    offset = 0
    success = failed = skipped = 0

    while offset < total:
        batch_r = col.get(limit=page_size, offset=offset,
                          include=['documents', 'metadatas'])
        ids     = batch_r['ids']
        docs    = batch_r['documents']
        metas   = batch_r['metadatas']
        offset += len(ids)

        if not ids:
            break

        # 过滤已处理
        todo_idx = [i for i, id_ in enumerate(ids) if id_ not in done]
        skipped += len(ids) - len(todo_idx)

        if not todo_idx:
            continue

        log.info(f"  处理 offset={offset-len(ids)}, 本批待处理 {len(todo_idx)}/{len(ids)}")

        # 小批次处理
        for i in range(0, len(todo_idx), BATCH_SIZE):
            mini = todo_idx[i:i+BATCH_SIZE]
            u_ids, u_docs, u_metas = [], [], []

            for idx in mini:
                doc_id  = ids[idx]
                doc_txt = docs[idx] or ''
                meta    = metas[idx] or {}
                name    = meta.get('name', meta.get('path', doc_id))[:40]

                try:
                    new_text = build_embed_text(doc_id, doc_txt, meta)
                    u_ids.append(doc_id)
                    u_docs.append(new_text[:MAX_CHARS])
                    u_metas.append(meta)
                    log.info(f"  [{offset-len(ids)+idx+1}/{total}] {name}")
                except Exception as e:
                    log.error(f"  FAIL {name}: {e}")
                    failed += 1
                    done.add(doc_id)

            if not u_ids:
                continue

            try:
                embeddings = model.encode(u_docs, normalize_embeddings=True,
                                          show_progress_bar=False).tolist()
                col.upsert(ids=u_ids, documents=u_docs, metadatas=u_metas,
                           embeddings=embeddings)
                for id_ in u_ids:
                    done.add(id_)
                success += len(u_ids)
                save_state(done)
                log.info(f"  ✅ 入库 {len(u_ids)} 条 (已完成 {len(done)}/{total})")
            except Exception as e:
                log.error(f"  FAIL 入库: {e}")
                failed += len(u_ids)

    log.info("=" * 60)
    log.info(f"Phase 1 完成: 成功={success} 失败={failed} 跳过={skipped}")
    log.info(f"库总量: {col.count()}")
    log.info(f"日志: {log_file}")
    lock.release()
    log.info("🔓 已释放ChromaDB写锁")


if __name__ == '__main__':
    run_reindex()
