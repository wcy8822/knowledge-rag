#!/usr/bin/env python3
"""
Loki Phase 2 -- 长文档分块向量化
策略: >3KB 文件按语义边界切块 → qwen摘要 → BGE-M3 embed → doc_knowledge_chunks collection
特性: 断点续跑 · 文件级state · GC孤儿清理 · 互斥锁 · subprocess硬超时
"""

import os, sys, re, time, json, hashlib, logging, fcntl, signal
from datetime import datetime
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired

import chromadb
from sentence_transformers import SentenceTransformer

# ========== 路径配置 ==========
BGE_PATH     = "/Users/didi/Work/projects/knowledge-rag-知识库/bge-m3-model/bge-m3/BAAI/bge-m3"
CHROMA_DIR   = "/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge"
LOG_DIR      = Path("/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/logs")
STATE_FILE   = LOG_DIR / "loki_chunk_state.json"
LOCK_FILE    = Path("/Users/didi/Work/data/vectors/data/chroma-doc-knowledge-bge/.loki_write.lock")

SCAN_DIRS = [
    "/Users/didi/Work/docs/obsidian-vault/obsidian",
    "/Users/didi/Work/docs",
    "/Users/didi/Work/projects",
    "/Users/didi/.allin_ai_safe/docs",
]
EXCLUDE_DIRS = {'.obsidian', 'Templates', 'node_modules', '__pycache__',
                '.git', 'venv', 'env', 'bge-m3-model', 'archives', 'chroma',
                '人事-简历', '_大文件归档'}
SUPPORTED_EXT = {'.md', '.pdf', '.docx', '.txt'}  # .sql/.xlsx 由 Phase 1 覆盖

COLLECTION_CHUNKS = "doc_knowledge_chunks"
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"

# ========== 分块参数 ==========
CHUNK_MIN       = 200       # 块最小字数（太短合并到上一块）
CHUNK_TARGET    = 1000      # 目标字数
CHUNK_MAX       = 2000      # 块最大字数（超过强制切）
OVERLAP         = 150       # 重叠窗口字数
MIN_FILE_SIZE   = 3000      # <3KB 不分块（Phase 1 已覆盖）
SKIP_SIZE       = 5_000_000  # 5MB+ 跳过
CURSOR_SKIP_SIZE = 10_000_000  # cursor 文件 10MB 上限

BATCH_SIZE      = 5
SLEEP_BATCH     = 0.3
OLLAMA_HARD_TIMEOUT = 60

# ========== 跳过黑名单 ==========
import fnmatch
SKIP_PATTERNS = [
    'backup_*.sql',
    '外部笔记索引.md',
    '*node_modules*',
    '*__pycache__*',
]

# ========== 日志 ==========
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"loki_chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger('loki_chunk')

# ========== 状态持久化（文件级） ==========
def load_state() -> set:
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text()))
        except Exception:
            pass
    return set()

def save_state(done: set):
    STATE_FILE.write_text(json.dumps(list(done)))

def fingerprint(path: str, mtime: float) -> str:
    return hashlib.sha256(f"{path}:{mtime:.3f}".encode()).hexdigest()[:32]

# ========== 文档解析 ==========
def read_file(path: Path) -> str:
    ext = path.suffix.lower()
    try:
        if ext in ('.md', '.txt'):
            return path.read_text(encoding='utf-8', errors='ignore')
        elif ext == '.pdf':
            from pdfminer.high_level import extract_text
            return extract_text(str(path)) or ''
        elif ext == '.docx':
            import docx
            doc = docx.Document(str(path))
            return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        raise RuntimeError(f"解析失败({ext}): {e}")
    return ''

# ========== 分块逻辑 ==========

def chunk_markdown(text: str, filename: str) -> list:
    """按 ## 标题切块，大段再按 CHUNK_MAX 强制切"""
    is_cursor = filename.startswith('cursor_')

    if is_cursor:
        return chunk_cursor(text)

    # 按 ## 标题切
    sections = re.split(r'\n(?=## )', text)
    chunks = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # 提取标题
        heading = ''
        lines = section.split('\n', 1)
        if lines[0].startswith('## '):
            heading = lines[0].strip()

        if len(section) <= CHUNK_MAX:
            if len(section) >= CHUNK_MIN:
                chunks.append({'text': section, 'heading': heading})
            elif chunks:
                # 太短，合并到上一个 chunk
                chunks[-1]['text'] += '\n\n' + section
            else:
                chunks.append({'text': section, 'heading': heading})
        else:
            # 大段强制切
            sub_chunks = force_split(section, heading)
            chunks.extend(sub_chunks)

    # 添加重叠窗口
    chunks = add_overlap(chunks)
    return chunks


def chunk_cursor(text: str) -> list:
    """cursor AI 对话日志按对话轮次切"""
    patterns = [
        r'\n(?=## (?:Human|Assistant|User))',
        r'\n(?=(?:Human|Assistant|User):)',
        r'\n(?=\*\*(?:Human|Assistant|User)\*\*)',
    ]
    # 尝试每种模式，选切出最多块的
    best_parts = [text]
    for pat in patterns:
        parts = re.split(pat, text)
        if len(parts) > len(best_parts):
            best_parts = parts

    chunks = []
    for part in best_parts:
        part = part.strip()
        if len(part) < CHUNK_MIN:
            # 太短，合并到上一个
            if chunks:
                chunks[-1]['text'] += '\n\n' + part
            continue
        if len(part) > CHUNK_MAX:
            sub = force_split(part, '')
            chunks.extend(sub)
        else:
            chunks.append({'text': part, 'heading': '', 'type': 'cursor'})

    return chunks


def chunk_pdf_pages(path: Path) -> list:
    """PDF 按页切块"""
    try:
        from pdfminer.high_level import extract_text
        from pdfminer.pdfpage import PDFPage
    except ImportError:
        # fallback: 整篇切
        text = read_file(path)
        return chunk_by_size(text)

    chunks = []
    try:
        with open(path, 'rb') as f:
            pages = list(PDFPage.get_pages(f))

        for i, _ in enumerate(pages):
            page_text = extract_text(str(path), page_numbers=[i])
            if page_text and len(page_text.strip()) >= CHUNK_MIN:
                chunks.append({
                    'text': page_text.strip(),
                    'heading': f'Page {i+1}',
                })
    except Exception as e:
        log.warning(f"  PDF按页切块失败，回退整篇: {e}")
        text = read_file(path)
        return chunk_by_size(text)

    return chunks


def chunk_docx(text: str) -> list:
    """docx 按段落合并切块"""
    paragraphs = text.split('\n')
    return merge_paragraphs(paragraphs)


def chunk_txt(text: str) -> list:
    """txt 按空行切块"""
    sections = re.split(r'\n\s*\n', text)
    return merge_paragraphs(sections)


def merge_paragraphs(parts: list) -> list:
    """合并短段落到 CHUNK_TARGET 左右"""
    chunks = []
    current = ''
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(current) + len(part) + 1 > CHUNK_MAX and current:
            if len(current) >= CHUNK_MIN:
                chunks.append({'text': current, 'heading': ''})
            current = part
        else:
            current = current + '\n' + part if current else part

    if current and len(current) >= CHUNK_MIN:
        chunks.append({'text': current, 'heading': ''})
    elif current and chunks:
        chunks[-1]['text'] += '\n' + current

    return chunks


def chunk_by_size(text: str) -> list:
    """通用按大小切块（fallback）"""
    chunks = []
    for i in range(0, len(text), CHUNK_MAX - OVERLAP):
        chunk = text[i:i + CHUNK_MAX]
        if len(chunk) >= CHUNK_MIN:
            chunks.append({'text': chunk, 'heading': ''})
    return chunks


def force_split(text: str, heading: str) -> list:
    """强制按 CHUNK_MAX 切，尽量在句号/换行处断"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_MAX
        if end >= len(text):
            chunk = text[start:]
            if len(chunk) >= CHUNK_MIN:
                chunks.append({'text': chunk, 'heading': heading if not chunks else ''})
            elif chunks:
                chunks[-1]['text'] += chunk
            break

        # 在 end 附近找断点（句号、换行）
        best_break = end
        for sep in ['\n\n', '\n', '。', '. ', '；', '; ']:
            pos = text.rfind(sep, start + CHUNK_MIN, end)
            if pos > start:
                best_break = pos + len(sep)
                break

        chunk = text[start:best_break]
        if len(chunk) >= CHUNK_MIN:
            chunks.append({'text': chunk, 'heading': heading if not chunks else ''})
        start = best_break - OVERLAP if OVERLAP < best_break - start else best_break

    return chunks


def add_overlap(chunks: list) -> list:
    """给相邻块添加重叠窗口"""
    if len(chunks) <= 1 or OVERLAP <= 0:
        return chunks

    result = []
    for i, chunk in enumerate(chunks):
        text = chunk['text']
        if i > 0 and len(chunks[i-1]['text']) > OVERLAP:
            # 前一个块的尾部作为当前块的开头
            prev_tail = chunks[i-1]['text'][-OVERLAP:]
            text = '...' + prev_tail + '\n' + text
        result.append({**chunk, 'text': text})
    return result


def get_chunks(path: Path, text: str) -> list:
    """根据文件类型选择分块策略"""
    ext = path.suffix.lower()
    name = path.name

    if ext == '.pdf':
        chunks = chunk_pdf_pages(path)
    elif ext == '.docx':
        chunks = chunk_docx(text)
    elif ext == '.txt':
        chunks = chunk_txt(text)
    elif ext == '.md':
        chunks = chunk_markdown(text, name)
    else:
        chunks = chunk_by_size(text)

    # 确保每个 chunk 有 type 字段
    for c in chunks:
        if 'type' not in c:
            c['type'] = 'cursor' if name.startswith('cursor_') else 'narrative'

    return chunks

# ========== qwen 摘要 ==========

def qwen_summarize(fname: str, chunk_text: str, chunk_type: str = 'narrative') -> str:
    """qwen2.5:7b 生成块级摘要，subprocess硬超时"""
    if chunk_type == 'cursor':
        prompt = f"""这是一段AI对话记录。请提取这轮对话中的关键决策点、结论或发现（1-2句）：

{chunk_text[:2000]}

提取（只输出结论，不要解释）："""
    else:
        prompt = f"""请用1-3句中文总结这段内容的核心信息和关键术语：

文件: {fname}
内容:
{chunk_text[:2000]}

摘要（只输出摘要，不要解释）："""

    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 150}
    })

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
            if len(summary) > 10:
                return summary
    except TimeoutExpired:
        proc.kill()
        proc.wait()
        log.warning(f"  timeout({OLLAMA_HARD_TIMEOUT}s): {fname}")
    except Exception as e:
        log.warning(f"  qwen failed: {e}")
    return None


# ========== 扫描文件 ==========

def should_skip(path: Path, size: int) -> bool:
    """判断是否跳过"""
    name = path.name
    for pat in SKIP_PATTERNS:
        if fnmatch.fnmatch(name, pat):
            return True
    # cursor 文件有更高的大小上限
    if name.startswith('cursor_') and path.suffix.lower() == '.md':
        return size > CURSOR_SKIP_SIZE
    return size > SKIP_SIZE


def scan_files() -> list:
    """扫描所有需要分块的文件（>3KB 且支持的格式）"""
    files = []
    for base in SCAN_DIRS:
        base_path = Path(base)
        if not base_path.exists():
            continue
        for f in base_path.rglob('*'):
            try:
                if f.suffix.lower() not in SUPPORTED_EXT:
                    continue
                if any(ex in f.parts for ex in EXCLUDE_DIRS):
                    continue
                st = f.stat()
                if st.st_size < MIN_FILE_SIZE:
                    continue  # <3KB 由 Phase 1 覆盖
                if should_skip(f, st.st_size):
                    continue
                files.append((f, st.st_mtime))
            except (FileNotFoundError, PermissionError, OSError):
                pass
    return files


# ========== 主流程 ==========

def run_chunks(model, col, done: set) -> set:
    log.info("=" * 60)
    log.info("Loki Phase 2: 分块向量化")

    all_files = scan_files()
    log.info(f"  扫描到 >3KB 文件: {len(all_files)}")

    todo = [(f, mt) for f, mt in all_files
            if fingerprint(str(f), mt) not in done]

    skipped = len(all_files) - len(todo)
    log.info(f"  待处理: {len(todo)} | 跳过已有: {skipped}")

    success = failed = total_chunks = 0

    for file_idx, (f, mt) in enumerate(todo):
        fp = fingerprint(str(f), mt)
        try:
            # 1. 读取文件
            if f.suffix.lower() == '.pdf':
                text = ''  # PDF 在 chunk_pdf_pages 内部读取
            else:
                text = read_file(f).strip()
                if len(text) < CHUNK_MIN:
                    log.info(f"  SKIP(短) {f.name}")
                    done.add(fp)
                    continue

            # 2. 分块
            if f.suffix.lower() == '.pdf':
                chunks = chunk_pdf_pages(f)
            else:
                chunks = get_chunks(f, text)

            if not chunks:
                log.info(f"  SKIP(无块) {f.name}")
                done.add(fp)
                continue

            # 3. 相对路径（用于 metadata）
            rel_path = str(f)
            for base in SCAN_DIRS:
                if rel_path.startswith(base):
                    rel_path = rel_path[len(base):].lstrip('/')
                    break

            # 4. 批量处理这个文件的所有 chunk
            ids, docs, metas = [], [], []
            for ci, chunk in enumerate(chunks):
                chunk_id = f"{fp}_chunk_{ci:03d}"
                chunk_text = chunk['text']
                chunk_type = chunk.get('type', 'narrative')
                heading = chunk.get('heading', '')

                # qwen 摘要：大文件(>100KB)或 chunks 过多(>50)时跳过，用 heading+原文前200字替代
                file_size = f.stat().st_size if f.exists() else 0
                if file_size > 100 * 1024 or len(chunks) > 50:
                    # 快速摘要：heading + 原文前200字
                    quick_summary = heading[:100] if heading else chunk_text[:200].split('\n')[0]
                    embed_text = f"文件:{f.name}\n块:{ci+1}/{len(chunks)}\n摘要:{quick_summary}\n---\n{chunk_text[:1500]}"
                else:
                    summary = qwen_summarize(f.name, chunk_text, chunk_type)
                    if summary:
                        embed_text = f"文件:{f.name}\n块:{ci+1}/{len(chunks)}\n摘要:{summary}\n---\n{chunk_text[:800]}"
                    else:
                        embed_text = f"文件:{f.name}\n块:{ci+1}/{len(chunks)}\n---\n{chunk_text[:1500]}"

                ids.append(chunk_id)
                docs.append(embed_text)
                metas.append({
                    'source_file': rel_path,
                    'chunk_index': ci,
                    'total_chunks': len(chunks),
                    'heading': heading[:200],
                    'ext': f.suffix.lower(),
                    'file_id': fp,
                    'type': chunk_type,
                    'char_count': len(chunk_text),
                    'source': 'loki_chunk',
                })

            # 5. 分批 embed + upsert
            for bi in range(0, len(ids), BATCH_SIZE):
                b_ids = ids[bi:bi+BATCH_SIZE]
                b_docs = docs[bi:bi+BATCH_SIZE]
                b_metas = metas[bi:bi+BATCH_SIZE]

                try:
                    embeddings = model.encode(b_docs, normalize_embeddings=True,
                                              show_progress_bar=False).tolist()
                    col.upsert(ids=b_ids, documents=b_docs, metadatas=b_metas,
                               embeddings=embeddings)
                except Exception as e:
                    log.error(f"  FAIL 入库 {f.name} batch {bi}: {e}")
                    failed += len(b_ids)
                    continue

            done.add(fp)
            total_chunks += len(chunks)
            success += 1
            save_state(done)
            log.info(f"  [{file_idx+1}/{len(todo)}] {f.name} -> {len(chunks)} chunks (total={col.count()})")

            if SLEEP_BATCH > 0:
                time.sleep(SLEEP_BATCH)

        except Exception as e:
            log.error(f"  FAIL {f.name}: {e}")
            failed += 1
            done.add(fp)  # 失败也记录，避免反复卡住
            save_state(done)

    log.info(f"Phase 2 完成: 文件={success} 失败={failed} 总chunk={total_chunks} 库总量={col.count()}")
    return done


def gc_orphans(col, done: set):
    """GC: 删除孤儿 chunk（文件已更新或删除的旧 chunk）"""
    log.info("=" * 60)
    log.info("GC: 清理孤儿 chunk")

    # 收集所有有效的 file_id
    valid_file_ids = set()
    for fp in done:
        # fingerprint 就是 file_id 前缀
        if '_chunk_' not in fp:
            valid_file_ids.add(fp)

    # 获取 collection 中所有记录
    try:
        total = col.count()
        if total == 0:
            log.info("  collection 为空，无需 GC")
            return

        # 分批获取所有 ID
        all_ids = []
        batch = 1000
        for offset in range(0, total, batch):
            result = col.get(limit=batch, offset=offset, include=[])
            all_ids.extend(result['ids'])

        # 找出孤儿（file_id 不在有效集合中）
        orphans = []
        for chunk_id in all_ids:
            file_id = chunk_id.split('_chunk_')[0] if '_chunk_' in chunk_id else chunk_id
            if file_id not in valid_file_ids:
                orphans.append(chunk_id)

        if orphans:
            # 分批删除
            for i in range(0, len(orphans), 100):
                col.delete(ids=orphans[i:i+100])
            log.info(f"  已删除 {len(orphans)} 条孤儿 chunk (库剩余 {col.count()})")
        else:
            log.info(f"  无孤儿 chunk (库总量 {total})")

    except Exception as e:
        log.error(f"  GC 失败: {e}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    log.info("=" * 60)
    log.info(f"Loki Phase 2 启动 mode={mode}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. 加载模型
    log.info("加载 BGE-M3...")
    model = SentenceTransformer(BGE_PATH)
    log.info(f"  维度: {model.get_sentence_embedding_dimension()}")

    # 2. 获取互斥锁
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_fp = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fp.write(f"chunk:{os.getpid()}\n"); lock_fp.flush()
        log.info("已获取ChromaDB写锁")
    except (IOError, OSError):
        log.error("无法获取写锁，其他 Loki 进程正在运行。退出。")
        lock_fp.close()
        sys.exit(1)

    # 3. 在锁保护下工作
    try:
        client = chromadb.PersistentClient(CHROMA_DIR)
        col = client.get_or_create_collection(COLLECTION_CHUNKS,
                  metadata={"hnsw:space": "cosine"})
        log.info(f"  chunks collection 现有: {col.count()} 条")

        done = load_state()
        log.info(f"  已处理文件: {len(done)}")

        t0 = time.time()

        if mode in ('all', 'chunk'):
            done = run_chunks(model, col, done)

        if mode in ('all', 'gc'):
            gc_orphans(col, done)

        save_state(done)
        elapsed = (time.time() - t0) / 60
        log.info("=" * 60)
        log.info(f"Loki Phase 2 完成 耗时={elapsed:.1f}分钟")
        log.info(f"  chunks库: {col.count()} 条")
        log.info(f"  日志: {log_file}")

    finally:
        fcntl.flock(lock_fp, fcntl.LOCK_UN); lock_fp.close()
        log.info("已释放ChromaDB写锁")


if __name__ == '__main__':
    main()
