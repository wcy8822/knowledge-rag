#!/usr/bin/env python3
"""Loki ↔ Claude 反馈闭环 Phase 2: 周报分析器

读取 ~/Work/projects/knowledge-rag-知识库/logs/queries.jsonl，
按 7 天窗口聚合：
  - 高频 query (top N)
  - 0 结果 query
  - 慢查询 (latency_ms 超阈值)
  - 高命中文件 (top_files 出现次数)
  - 30 天零命中文件 (KB 中存在但近 30 天未被任何 query 命中)

输出 OB 笔记到 ~/Work/docs/obsidian-vault/obsidian/Inbox/<ts>+Loki周报-...md。

CLI:
  python loki_query_analyzer.py [--dry-run] [--log-path PATH] [--out-dir DIR]
                                [--days 7] [--cold-days 30] [--top 10]
                                [--no-cold] [--slow-ms 5000]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_LOG_PATH = Path.home() / "Work/projects/knowledge-rag-知识库/logs/queries.jsonl"
DEFAULT_OUT_DIR = Path.home() / "Work/docs/obsidian-vault/obsidian/Inbox"
SLOW_LATENCY_MS_DEFAULT = 5000


@dataclass
class Report:
    window_days: int
    cold_days: int
    total_queries: int = 0
    by_tool: dict = field(default_factory=dict)
    top_queries: list = field(default_factory=list)
    zero_hit_queries: list = field(default_factory=list)
    slow_queries: list = field(default_factory=list)
    top_files: list = field(default_factory=list)
    cold_files: list = field(default_factory=list)
    cold_files_skipped_reason: Optional[str] = None
    generated_at: str = ""


# ----------------------------- 日志读取 -----------------------------

def parse_ts(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def load_entries(log_path: Path) -> list:
    """读 JSONL，跳过坏行。"""
    if not log_path.exists():
        return []
    entries = []
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries


def filter_window(entries: Iterable[dict], days: int, now: Optional[datetime] = None) -> list:
    """筛选最近 N 天的条目（基于 ts 字段，去 tz 比较）。"""
    if now is None:
        now = datetime.now()
    cutoff = now - timedelta(days=days)
    out = []
    for e in entries:
        dt = parse_ts(e.get("ts", ""))
        if dt is None:
            continue
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        if dt >= cutoff:
            out.append(e)
    return out


# ----------------------------- 聚合 -----------------------------

def compute_top_queries(entries: list, top: int = 10) -> list:
    c = Counter(e.get("query", "") for e in entries if e.get("query"))
    return c.most_common(top)


def compute_zero_hit_queries(entries: list, top: int = 10) -> list:
    zero = [e.get("query", "") for e in entries if int(e.get("n_returned", 0)) == 0 and e.get("query")]
    return Counter(zero).most_common(top)


def compute_slow_queries(entries: list, threshold_ms: int = SLOW_LATENCY_MS_DEFAULT, top: int = 10) -> list:
    slow = [
        (e.get("query", ""), int(e.get("latency_ms", 0)), e.get("ts", ""))
        for e in entries
        if int(e.get("latency_ms", 0)) >= threshold_ms
    ]
    slow.sort(key=lambda x: x[1], reverse=True)
    return slow[:top]


def compute_top_files(entries: list, top: int = 10) -> list:
    c = Counter()
    for e in entries:
        for f in e.get("top_files", []) or []:
            if f:
                c[f] += 1
    return c.most_common(top)


def compute_by_tool(entries: list) -> dict:
    return dict(Counter(e.get("tool", "?") for e in entries))


def compute_cold_files(
    entries: list,
    cold_days: int,
    kb_files_loader=None,
    now: Optional[datetime] = None,
) -> tuple:
    """KB 中近 cold_days 没出现在任何 top_files 的文件。

    返回 (cold_files_list, skipped_reason)；若无法获取 KB 清单则 ([], reason)。
    """
    if kb_files_loader is None:
        return [], "未提供 KB 文件清单加载器"
    try:
        kb_files = set(kb_files_loader())
    except Exception as e:
        return [], f"KB 文件清单加载失败: {e}"
    if not kb_files:
        return [], "KB 文件清单为空"

    if now is None:
        now = datetime.now()
    cutoff = now - timedelta(days=cold_days)

    seen = set()
    for e in entries:
        dt = parse_ts(e.get("ts", ""))
        if dt is None:
            continue
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        if dt < cutoff:
            continue
        for f in e.get("top_files", []) or []:
            if f:
                seen.add(f)

    cold = sorted(kb_files - seen)
    return cold, None


def load_kb_files_from_chroma() -> list:
    """从 ChromaDB 拉取所有文档的 source_file。失败返回 []。"""
    try:
        import chromadb
    except Exception:
        return []
    chroma_path = str(Path.home() / "Work/data/vectors/data/chroma-doc-knowledge-bge")
    client = chromadb.PersistentClient(path=chroma_path)
    files = set()
    for col_name in ["doc_knowledge_bge_m3", "doc_knowledge_chunks", "ddl_schema_bge_m3"]:
        try:
            col = client.get_collection(col_name)
            offset = 0
            batch = 5000
            while True:
                got = col.get(include=["metadatas"], limit=batch, offset=offset)
                metas = got.get("metadatas") or []
                if not metas:
                    break
                for m in metas:
                    if not m:
                        continue
                    f = m.get("source_file") or m.get("path") or m.get("table")
                    if f:
                        files.add(str(f))
                if len(metas) < batch:
                    break
                offset += batch
        except Exception:
            continue
    return sorted(files)


# ----------------------------- 报告生成 -----------------------------

def build_report(
    entries_all: list,
    days: int,
    cold_days: int,
    top: int,
    slow_threshold_ms: int,
    kb_files_loader=None,
    now: Optional[datetime] = None,
) -> Report:
    if now is None:
        now = datetime.now()

    window = filter_window(entries_all, days, now=now)
    cold_window = filter_window(entries_all, cold_days, now=now)

    cold_files, cold_skipped = compute_cold_files(
        cold_window, cold_days, kb_files_loader=kb_files_loader, now=now
    )

    return Report(
        window_days=days,
        cold_days=cold_days,
        total_queries=len(window),
        by_tool=compute_by_tool(window),
        top_queries=compute_top_queries(window, top=top),
        zero_hit_queries=compute_zero_hit_queries(window, top=top),
        slow_queries=compute_slow_queries(window, threshold_ms=slow_threshold_ms, top=top),
        top_files=compute_top_files(window, top=top),
        cold_files=cold_files[:50],
        cold_files_skipped_reason=cold_skipped,
        generated_at=now.strftime("%Y-%m-%d %H:%M"),
    )


def render_markdown(r: Report) -> str:
    lines = []
    lines.append("---")
    lines.append("type: report")
    lines.append("category: loki-feedback-loop")
    lines.append(f"generated_at: {r.generated_at}")
    lines.append(f"window_days: {r.window_days}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Loki 周报 ({r.window_days} 天窗口)")
    lines.append("")
    lines.append(f"生成时间: **{r.generated_at}**")
    lines.append("")
    lines.append("## 摘要")
    lines.append(f"- 总调用数: **{r.total_queries}**")
    if r.by_tool:
        lines.append("- 工具分布: " + ", ".join(f"{k}={v}" for k, v in sorted(r.by_tool.items(), key=lambda x: -x[1])))
    lines.append("")

    lines.append(f"## 高频 query (Top {len(r.top_queries)})")
    if r.top_queries:
        for q, c in r.top_queries:
            lines.append(f"- `{q}` × {c}")
    else:
        lines.append("- (无)")
    lines.append("")

    lines.append("## 零结果 query")
    if r.zero_hit_queries:
        for q, c in r.zero_hit_queries:
            lines.append(f"- `{q}` × {c} ⚠️")
    else:
        lines.append("- (无 — 检索覆盖率良好)")
    lines.append("")

    lines.append("## 慢查询 (≥5s)")
    if r.slow_queries:
        for q, ms, ts in r.slow_queries:
            lines.append(f"- `{q}` — {ms}ms @ {ts}")
    else:
        lines.append("- (无)")
    lines.append("")

    lines.append(f"## 高命中文件 (Top {len(r.top_files)})")
    if r.top_files:
        for f, c in r.top_files:
            lines.append(f"- `{f}` × {c}")
    else:
        lines.append("- (无)")
    lines.append("")

    lines.append(f"## 冷文件: KB 中近 {r.cold_days} 天零命中")
    if r.cold_files_skipped_reason:
        lines.append(f"- 跳过：{r.cold_files_skipped_reason}")
    elif r.cold_files:
        lines.append(f"- 共 **{len(r.cold_files)}** 个 (展示前 50)")
        for f in r.cold_files:
            lines.append(f"  - `{f}`")
    else:
        lines.append("- (无 — 全部文件均被命中过)")
    lines.append("")

    return "\n".join(lines) + "\n"


def write_report(md: str, out_dir: Path, now: Optional[datetime] = None) -> Path:
    if now is None:
        now = datetime.now()
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = now.strftime("%Y%m%d%H%M") + "+Loki周报-反馈闭环.md"
    p = out_dir / fname
    p.write_text(md, encoding="utf-8")
    return p


# ----------------------------- CLI -----------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Loki 周报分析器")
    ap.add_argument("--log-path", default=str(DEFAULT_LOG_PATH))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--cold-days", type=int, default=30)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--slow-ms", type=int, default=SLOW_LATENCY_MS_DEFAULT)
    ap.add_argument("--no-cold", action="store_true", help="跳过冷文件分析（不查 KB）")
    ap.add_argument("--dry-run", action="store_true", help="只打印报告到 stdout，不写文件")
    args = ap.parse_args(argv)

    log_path = Path(args.log_path)
    entries = load_entries(log_path)

    loader = None if args.no_cold else load_kb_files_from_chroma
    report = build_report(
        entries_all=entries,
        days=args.days,
        cold_days=args.cold_days,
        top=args.top,
        slow_threshold_ms=args.slow_ms,
        kb_files_loader=loader,
    )
    md = render_markdown(report)

    if args.dry_run:
        sys.stdout.write(md)
        return 0

    out_path = write_report(md, Path(args.out_dir))
    print(f"✅ 周报已写入: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
