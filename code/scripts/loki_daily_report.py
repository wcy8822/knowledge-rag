#!/usr/bin/env python3
"""Loki daily 工作总结生成器.

每天 02:00 launchd 跑完 daily pipeline 后由 wrapper 末尾调用本脚本。
解析 wrapper log + loki log，对比前一天，生成 OB 规范的 markdown 报告。

输出:
  1. 项目内: daily-reports/YYYY-MM-DD-loki-daily.md (固定文件名, 主备份)
  2. 软链到 OB Inbox/YYYYMMDDHHmm+loki-daily-YYYY-MM-DD.md (按用户全局规则)

用法:
  python3 loki_daily_report.py [--date YYYY-MM-DD] [--no-symlink]
  默认 --date=今天 (basename of latest wrapper log)

设计:
  纯函数解析 + 副作用隔离, 易测. wrapper 调用失败不影响 pipeline 退出码.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, date as date_cls, timedelta
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent.parent
LOG_DIR = SCRIPT_DIR / "logs"
REPORT_DIR = PROJECT_DIR / "daily-reports"
OB_INBOX = Path.home() / "Work" / "docs" / "obsidian-vault" / "obsidian" / "Inbox"


# ─── 数据模型 ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PipelineStats:
    """单次 pipeline 跑的关键统计."""
    date_str: str  # YYYY-MM-DD
    start_ts: str = ""
    end_ts: str = ""
    duration_min: float = 0.0
    mode: str = "all"
    max_files: int = 0
    docs_total: int = 0
    docs_success: int = 0
    docs_failed: int = 0
    docs_content_skip: int = 0
    chunks_total: int = 0
    chunks_files: int = 0
    chunks_failed: int = 0
    chunks_added: int = 0
    ddl_total: int = 0
    ddl_success: int = 0
    ddl_failed: int = 0
    bm25_count: int = 0
    bm25_duration_sec: float = 0.0
    bm25_cache_hit_pct: int = 0
    rss_peak_mb: int = 0
    rss_limit_mb: int = 18432
    wrapper_exit: int = -1
    error_lines: tuple = field(default_factory=tuple)  # 报错原文 (限 200 条)
    warning_lines: tuple = field(default_factory=tuple)


# ─── 纯解析函数 ─────────────────────────────────────────────────────────────

def parse_loki_log(text: str, date_str: str) -> dict:
    """从 loki log 文本提取关键字段, 返回 dict (向 PipelineStats 喂参)."""
    out: dict = {"date_str": date_str}

    m = re.search(r"Loki 启动 mode=(\S+) max_files=(\d+)\s+(\S+ \S+)", text)
    if m:
        out["mode"] = m.group(1)
        out["max_files"] = int(m.group(2))
        out["start_ts"] = m.group(3)

    # Part 1 完成: 成功=32 失败=0 content跳过=1468 库总量=11101
    m = re.search(
        r"Part 1 完成: 成功=(\d+) 失败=(\d+) content跳过=(\d+) 库总量=(\d+)", text
    )
    if m:
        out["docs_success"] = int(m.group(1))
        out["docs_failed"] = int(m.group(2))
        out["docs_content_skip"] = int(m.group(3))
        out["docs_total"] = int(m.group(4))

    # Part 2 完成: 文件=1337 失败=161 总chunk=17712 库总量=61354
    m = re.search(
        r"Part 2 完成: 文件=(\d+) 失败=(\d+) 总chunk=(\d+) 库总量=(\d+)", text
    )
    if m:
        out["chunks_files"] = int(m.group(1))
        out["chunks_failed"] = int(m.group(2))
        out["chunks_added"] = int(m.group(3))
        out["chunks_total"] = int(m.group(4))

    # Part 2 完成: 成功=2 失败=0 DDL总量=536  (DDL 行写法相同前缀, 用末尾区分)
    m = re.search(r"Part 2 完成: 成功=(\d+) 失败=(\d+) DDL总量=(\d+)", text)
    if m:
        out["ddl_success"] = int(m.group(1))
        out["ddl_failed"] = int(m.group(2))
        out["ddl_total"] = int(m.group(3))

    # BM25 索引 rebuild 完成: 72991 条, 总耗时 75.4s
    m = re.search(r"BM25 索引 rebuild 完成: (\d+) 条, 总耗时 ([\d.]+)s", text)
    if m:
        out["bm25_count"] = int(m.group(1))
        out["bm25_duration_sec"] = float(m.group(2))

    # cache 总命中: 55361/72991 (75%)
    m = re.search(r"cache 总命中: \d+/\d+ \((\d+)%\)", text)
    if m:
        out["bm25_cache_hit_pct"] = int(m.group(1))

    # Loki 完成 耗时=48.4分钟
    m = re.search(r"Loki 完成 耗时=([\d.]+)分钟", text)
    if m:
        out["duration_min"] = float(m.group(1))

    # 提取所有 ERROR 报错行 (聚合时按错误类型分类)
    errors = re.findall(r".*ERROR\s+(FAIL [^\n]+|.+?(?=\n))", text)
    out["error_lines"] = tuple(errors[:200])

    # 提取 ⚠️ 警告
    warnings = re.findall(r"⚠️\s+([^\n]+)", text)
    out["warning_lines"] = tuple(warnings[:50])

    return out


def parse_wrapper_log(text: str) -> dict:
    """从 wrapper log 文本提取 RSS 峰值 + exit code."""
    out: dict = {}

    # exit=0 / exit=137 / etc
    m = re.search(r"Loki wrapper 结束 exit=(\d+)", text)
    if m:
        out["wrapper_exit"] = int(m.group(1))

    # [watch] RSS=8270MB (limit=18432MB)
    rss_values = [int(x) for x in re.findall(r"\[watch\] RSS=(\d+)MB", text)]
    if rss_values:
        out["rss_peak_mb"] = max(rss_values)

    m = re.search(r"limit=(\d+)MB", text)
    if m:
        out["rss_limit_mb"] = int(m.group(1))

    return out


def find_logs_for_date(date_str: str, log_dir: Path) -> tuple[Path | None, Path | None]:
    """找 YYYY-MM-DD 当日的 wrapper log 和 loki log 各一个 (取最新)."""
    yyyymmdd = date_str.replace("-", "")
    wrappers = sorted(log_dir.glob(f"wrapper_{yyyymmdd}_*.log"), reverse=True)
    lokis = sorted(log_dir.glob(f"loki_{yyyymmdd}_*.log"), reverse=True)
    return (wrappers[0] if wrappers else None, lokis[0] if lokis else None)


def load_prev_stats(date_str: str, report_dir: Path) -> Optional[dict]:
    """读前一天报告, 提取数据用于增量对比. 没有就返回 None.

    解析报告末尾的隐藏机器契约注释:
      <!-- stats: docs_total=11082 chunks_total=43775 ... -->
    """
    prev = (datetime.strptime(date_str, "%Y-%m-%d").date() - timedelta(days=1)
            ).strftime("%Y-%m-%d")
    prev_md = report_dir / f"{prev}-loki-daily.md"
    if not prev_md.exists():
        return None
    text = prev_md.read_text(encoding="utf-8")
    m = re.search(r"<!-- stats:\s*([^>]+?)\s*-->", text)
    if not m:
        return None
    out = {}
    for kv in m.group(1).split():
        if "=" not in kv:
            continue
        k, v = kv.split("=", 1)
        try:
            out[k] = float(v) if "." in v else int(v)
        except ValueError:
            continue
    return out or None


def aggregate_errors(error_lines: tuple) -> list[tuple[str, int, list[str]]]:
    """报错按类型聚合: [(error_type, count, [sample_files...])]."""
    by_type: dict[str, list[str]] = {}
    for line in error_lines:
        # 形如 "FAIL filename.pdf: 解析失败(.pdf): No module named 'pdfminer'"
        m = re.match(r"FAIL ([^:]+):\s*(.+)", line)
        if m:
            fname, reason = m.group(1).strip(), m.group(2).strip()
            by_type.setdefault(reason, []).append(fname)
        else:
            by_type.setdefault(line[:80], []).append("")
    # 按 count 降序
    result = sorted(
        [(k, len(v), v[:5]) for k, v in by_type.items()],
        key=lambda x: -x[1]
    )
    return result


# ─── 健康判断 ──────────────────────────────────────────────────────────────

def analyze_health(stats: PipelineStats) -> tuple[str, list[str]]:
    """返回 (overall_status, [detail_signals])."""
    signals: list[str] = []
    issues = 0

    if stats.wrapper_exit != 0:
        signals.append(f"❌ wrapper exit={stats.wrapper_exit} (非 0 = 异常)")
        issues += 1
    else:
        signals.append("✅ wrapper exit=0")

    if stats.rss_peak_mb >= stats.rss_limit_mb * 0.9:
        signals.append(f"⚠️ RSS 峰值 {stats.rss_peak_mb}MB 接近上限 {stats.rss_limit_mb}MB")
        issues += 1
    else:
        signals.append(
            f"✅ RSS 峰值 {stats.rss_peak_mb}MB / {stats.rss_limit_mb}MB"
            f" ({100 * stats.rss_peak_mb // max(stats.rss_limit_mb, 1)}%)"
        )

    total_failed = stats.docs_failed + stats.chunks_failed + stats.ddl_failed
    if total_failed > 0:
        signals.append(f"⚠️ 失败 {total_failed} 个 (docs={stats.docs_failed} "
                       f"chunks={stats.chunks_failed} ddl={stats.ddl_failed})")
        issues += 1
    else:
        signals.append("✅ 失败 0")

    if stats.duration_min > 60:
        signals.append(f"⚠️ 耗时 {stats.duration_min} 分钟 (超 60 分钟)")
    else:
        signals.append(f"✅ 耗时 {stats.duration_min} 分钟")

    if stats.bm25_cache_hit_pct < 50 and stats.bm25_count > 0:
        signals.append(f"⚠️ BM25 cache 命中 {stats.bm25_cache_hit_pct}% (低于 50%)")
    elif stats.bm25_count > 0:
        signals.append(f"✅ BM25 cache 命中 {stats.bm25_cache_hit_pct}%")

    if issues == 0:
        overall = "🟢 健康"
    elif issues == 1:
        overall = "🟡 注意"
    else:
        overall = "🔴 异常"
    return overall, signals


# ─── 渲染 ──────────────────────────────────────────────────────────────────

def render_markdown(stats: PipelineStats, prev: Optional[dict],
                    overall: str, signals: list, error_summary: list,
                    wrapper_log: Path, loki_log: Path) -> str:
    """生成 OB 规范 markdown 报告."""
    d = stats.date_str
    week = datetime.strptime(d, "%Y-%m-%d").isocalendar()[1]

    # 增量对比
    def delta(curr, prev_key):
        if prev is None or prev_key not in prev:
            return "N/A"
        diff = curr - prev[prev_key]
        sign = "+" if diff >= 0 else ""
        return f"{sign}{diff}"

    # 全景总结 (~300 字)
    summary_health = overall.split()[1] if " " in overall else overall
    summary = (
        f"{d} 02:00 launchd 自动跑 daily pipeline 用时 {stats.duration_min} 分钟"
        f"，wrapper exit={stats.wrapper_exit}，整体状态 {overall}。"
        f"文档库 {stats.docs_total} ({delta(stats.docs_total, 'docs_total')})，"
        f"chunk 库 {stats.chunks_total} ({delta(stats.chunks_total, 'chunks_total')})，"
        f"DDL 库 {stats.ddl_total} ({delta(stats.ddl_total, 'ddl_total')})，"
        f"BM25 索引 {stats.bm25_count} 条 rebuild "
        f"({stats.bm25_duration_sec}s，cache 命中 {stats.bm25_cache_hit_pct}%)。"
        f"RSS 峰值 {stats.rss_peak_mb}MB / {stats.rss_limit_mb}MB 上限。"
        f"本日处理 docs 成功 {stats.docs_success}/失败 {stats.docs_failed}/"
        f"content跳过 {stats.docs_content_skip}，"
        f"chunks 文件 {stats.chunks_files}/失败 {stats.chunks_failed}/新增 chunk {stats.chunks_added}，"
        f"DDL 成功 {stats.ddl_success}/失败 {stats.ddl_failed}。"
    )
    if error_summary:
        top_err = error_summary[0]
        summary += f"主要异常：{top_err[0]} ×{top_err[1]}。"

    # 标签 (≥5 个) — chunk 增量首日没前文件时显示"首日"
    if prev and "chunks_total" in prev:
        chunk_delta = stats.chunks_total - int(prev["chunks_total"])
        chunk_tag = f"chunk增量{chunk_delta:+d}" if chunk_delta else "chunk持平"
    else:
        chunk_tag = "首日"
    tags = [
        "Loki日报",
        "daily_pipeline",
        f"week{week}",
        chunk_tag,
        f"耗时{int(stats.duration_min)}分钟",
        f"BM25_{stats.bm25_count}条",
        summary_health,
    ]
    if stats.docs_failed + stats.chunks_failed + stats.ddl_failed > 0:
        tags.append("有失败")
    if stats.wrapper_exit != 0:
        tags.append("wrapper异常")

    yyyymmdd_hm = datetime.now().strftime("%Y%m%d%H%M")

    out = []
    out.append("---")
    out.append("type: 日报")
    out.append(f"date: {d}")
    out.append(f"week: {week}")
    out.append("project: Loki知识库RAG")
    out.append("tags:")
    for t in tags:
        out.append(f"  - {t}")
    prev_link = (datetime.strptime(d, "%Y-%m-%d").date() - timedelta(days=1)
                 ).strftime("%Y-%m-%d")
    out.append("related:")
    out.append(f'  - "[[{prev_link}-loki-daily]]"')
    out.append("---")
    out.append("")
    out.append("## 全景总结")
    out.append("")
    out.append(summary)
    out.append("")
    out.append("## 核心索引标签")
    out.append("")
    out.append(" ".join(f"#{t}" for t in tags[:7]))
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 一、健康总览")
    out.append("")
    out.append(f"**整体状态**：{overall}")
    out.append("")
    for s in signals:
        out.append(f"- {s}")
    out.append("")
    out.append("## 二、运行结果对比")
    out.append("")
    out.append("| 指标 | 当日 | 前日 | 增量 |")
    out.append("|---|---|---|---|")
    p = lambda k: prev.get(k, "N/A") if prev else "N/A"
    out.append(f"| docs_total | {stats.docs_total} | {p('docs_total')} "
               f"| {delta(stats.docs_total, 'docs_total')} |")
    out.append(f"| chunks_total | {stats.chunks_total} | {p('chunks_total')} "
               f"| {delta(stats.chunks_total, 'chunks_total')} |")
    out.append(f"| ddl_total | {stats.ddl_total} | {p('ddl_total')} "
               f"| {delta(stats.ddl_total, 'ddl_total')} |")
    out.append(f"| bm25_count | {stats.bm25_count} | {p('bm25_count')} "
               f"| {delta(stats.bm25_count, 'bm25_count')} |")
    out.append(f"| duration_min | {stats.duration_min} | {p('duration_min')} | - |")
    out.append("")
    out.append("## 三、阶段细节")
    out.append("")
    out.append(f"### Part 1 文档向量化")
    out.append(f"- 库总量: **{stats.docs_total}**")
    out.append(f"- 本次成功: {stats.docs_success}")
    out.append(f"- 失败: {stats.docs_failed}")
    out.append(f"- content 重复跳过: {stats.docs_content_skip}")
    out.append("")
    out.append(f"### Part 2 长文档分块")
    out.append(f"- 库总量: **{stats.chunks_total}**")
    out.append(f"- 本次处理文件: {stats.chunks_files}")
    out.append(f"- 失败: {stats.chunks_failed}")
    out.append(f"- 新增 chunk: {stats.chunks_added}")
    out.append("")
    out.append(f"### Part 3 DDL")
    out.append(f"- 库总量: **{stats.ddl_total}**")
    out.append(f"- 本次成功: {stats.ddl_success}")
    out.append(f"- 失败: {stats.ddl_failed}")
    out.append("")
    out.append(f"### BM25 索引 rebuild")
    out.append(f"- 总条数: **{stats.bm25_count}**")
    out.append(f"- 耗时: {stats.bm25_duration_sec}s")
    out.append(f"- cache 命中: {stats.bm25_cache_hit_pct}%")
    out.append("")

    if error_summary:
        out.append("## 四、错误聚合（按类型）")
        out.append("")
        for err_type, count, samples in error_summary[:10]:
            out.append(f"### {err_type} (×{count})")
            for s in samples:
                if s:
                    out.append(f"- {s}")
            out.append("")
    else:
        out.append("## 四、错误聚合")
        out.append("")
        out.append("无报错 ✅")
        out.append("")

    if stats.warning_lines:
        out.append("## 五、警告")
        out.append("")
        for w in stats.warning_lines[:20]:
            out.append(f"- {w}")
        out.append("")

    def _rel(p: Path) -> str:
        if p is None or str(p) == "N/A":
            return "N/A"
        try:
            return str(p.relative_to(PROJECT_DIR))
        except ValueError:
            return p.name  # tmp 路径 fallback

    out.append("## 六、原始日志")
    out.append("")
    out.append(f"- wrapper: `{_rel(wrapper_log)}`")
    out.append(f"- loki: `{_rel(loki_log)}`")
    out.append("")
    out.append("---")
    out.append("")
    out.append("*本报告由 `code/scripts/loki_daily_report.py` 自动生成*")
    out.append("")
    # 机器契约注释 — 给次日 load_prev_stats 解析增量
    out.append(
        f"<!-- stats: docs_total={stats.docs_total} chunks_total={stats.chunks_total} "
        f"ddl_total={stats.ddl_total} bm25_count={stats.bm25_count} "
        f"duration_min={stats.duration_min} wrapper_exit={stats.wrapper_exit} -->"
    )
    out.append("")
    return "\n".join(out)


# ─── 主流程 ──────────────────────────────────────────────────────────────

def build_report(date_str: str, log_dir: Path = LOG_DIR,
                 report_dir: Path = REPORT_DIR) -> tuple[str, PipelineStats, Path, Path]:
    """端到端: 找 log → 解析 → 渲染 → 返回 (markdown, stats, wrapper_log, loki_log)."""
    wrapper_log, loki_log = find_logs_for_date(date_str, log_dir)
    if loki_log is None:
        raise FileNotFoundError(f"找不到 {date_str} 的 loki log 在 {log_dir}")

    loki_text = loki_log.read_text(encoding="utf-8", errors="replace")
    wrapper_text = wrapper_log.read_text(encoding="utf-8", errors="replace") if wrapper_log else ""

    fields = parse_loki_log(loki_text, date_str)
    fields.update(parse_wrapper_log(wrapper_text))
    stats = PipelineStats(**{k: v for k, v in fields.items()
                             if k in PipelineStats.__dataclass_fields__})
    prev = load_prev_stats(date_str, report_dir)
    error_summary = aggregate_errors(stats.error_lines)
    overall, signals = analyze_health(stats)
    md = render_markdown(stats, prev, overall, signals, error_summary,
                         wrapper_log or Path("N/A"), loki_log)
    return md, stats, wrapper_log, loki_log


def write_report(md: str, date_str: str, report_dir: Path = REPORT_DIR,
                 ob_inbox: Path = OB_INBOX, do_symlink: bool = True) -> Path:
    """写报告 + 软链 OB."""
    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / f"{date_str}-loki-daily.md"
    out_path.write_text(md, encoding="utf-8")

    if do_symlink and ob_inbox.exists():
        yyyymmdd_hm = datetime.now().strftime("%Y%m%d%H%M")
        ob_link = ob_inbox / f"{yyyymmdd_hm}+loki-daily-{date_str}.md"
        # 已存在就先删 (用户全局规则: ln -sf 强制覆盖)
        if ob_link.is_symlink() or ob_link.exists():
            ob_link.unlink()
        os.symlink(out_path, ob_link)

    return out_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Loki daily 工作总结生成器")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD, 默认今天")
    ap.add_argument("--no-symlink", action="store_true", help="不软链到 OB Inbox")
    args = ap.parse_args(argv)

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    try:
        md, stats, wrapper_log, loki_log = build_report(date_str)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    out_path = write_report(md, date_str, do_symlink=not args.no_symlink)
    print(f"✅ Loki daily 报告: {out_path}")
    print(f"   docs={stats.docs_total} chunks={stats.chunks_total} "
          f"ddl={stats.ddl_total} bm25={stats.bm25_count} "
          f"duration={stats.duration_min}min exit={stats.wrapper_exit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
