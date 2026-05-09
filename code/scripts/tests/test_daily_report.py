#!/usr/bin/env python3
"""loki_daily_report 单元测试 — 解析/聚合/健康判断/格式渲染."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loki_daily_report import (
    PipelineStats,
    parse_loki_log,
    parse_wrapper_log,
    aggregate_errors,
    analyze_health,
    render_markdown,
    find_logs_for_date,
    build_report,
)


# ─── 测试 fixture ──────────────────────────────────────────────────────────

SAMPLE_LOKI_LOG = """\
2026-05-09 02:00:12,674 INFO Loki 启动 mode=all max_files=1500  2026-05-09 02:00:12
2026-05-09 02:00:18,127 INFO Loki Part 1: 文档向量化 (MD/PDF/Office/SQL)
2026-05-09 02:00:40,139 INFO   ⚠️  --max-files=1500 触发：本次只处理前 1500 个，剩余 10001 个待下次跑
2026-05-09 02:01:07,759 INFO Part 1 完成: 成功=32 失败=0 content跳过=1468 库总量=11101
2026-05-09 02:01:07,781 INFO Part 2: 长文档分块向量化 (>3KB 文件按语义切块)
2026-05-09 02:01:32,632 INFO   ⚠️  --max-files=1500 触发 (chunks)：本次只处理前 1500 个
2026-05-09 02:01:32,690 ERROR   FAIL finebi6.0.pdf: 解析失败(.pdf): No module named 'pdfminer'
2026-05-09 02:01:32,721 ERROR   FAIL 盈阳-0405.pdf: 解析失败(.pdf): No module named 'pdfminer'
2026-05-09 02:01:32,722 ERROR   FAIL 供应链业务Q3小结内容.pdf: 解析失败(.pdf): No module named 'pdfminer'
2026-05-09 02:47:27,140 INFO Part 2 完成: 文件=1337 失败=161 总chunk=17712 库总量=61354
2026-05-09 02:47:28,352 INFO Part 2 完成: 成功=2 失败=0 DDL总量=536
2026-05-09 02:48:23,602 INFO   cache 总命中: 55361/72991 (75%)
2026-05-09 02:48:43,935 INFO   BM25 索引 rebuild 完成: 72991 条, 总耗时 75.4s
2026-05-09 02:48:44,936 INFO Loki 完成 耗时=48.4分钟
"""

SAMPLE_WRAPPER_LOG = """\
Loki wrapper 启动 2026-05-09 02:00:02
  RSS 上限: 18432 MB（监控周期 30s）
  [watch] RSS=793MB (limit=18432MB)
  [watch] RSS=1653MB (limit=18432MB)
  [watch] RSS=4697MB (limit=18432MB)
Loki wrapper 结束 exit=0 2026-05-09 02:48:48
"""


# ─── 解析测试 ─────────────────────────────────────────────────────────────

class TestParseLokiLog:

    def test_parse_basic_fields(self):
        out = parse_loki_log(SAMPLE_LOKI_LOG, "2026-05-09")
        assert out["date_str"] == "2026-05-09"
        assert out["mode"] == "all"
        assert out["max_files"] == 1500

    def test_parse_part1(self):
        out = parse_loki_log(SAMPLE_LOKI_LOG, "2026-05-09")
        assert out["docs_success"] == 32
        assert out["docs_failed"] == 0
        assert out["docs_content_skip"] == 1468
        assert out["docs_total"] == 11101

    def test_parse_part2(self):
        out = parse_loki_log(SAMPLE_LOKI_LOG, "2026-05-09")
        assert out["chunks_files"] == 1337
        assert out["chunks_failed"] == 161
        assert out["chunks_added"] == 17712
        assert out["chunks_total"] == 61354

    def test_parse_ddl(self):
        out = parse_loki_log(SAMPLE_LOKI_LOG, "2026-05-09")
        assert out["ddl_success"] == 2
        assert out["ddl_failed"] == 0
        assert out["ddl_total"] == 536

    def test_parse_bm25(self):
        out = parse_loki_log(SAMPLE_LOKI_LOG, "2026-05-09")
        assert out["bm25_count"] == 72991
        assert out["bm25_duration_sec"] == 75.4
        assert out["bm25_cache_hit_pct"] == 75

    def test_parse_duration(self):
        out = parse_loki_log(SAMPLE_LOKI_LOG, "2026-05-09")
        assert out["duration_min"] == 48.4

    def test_parse_errors(self):
        out = parse_loki_log(SAMPLE_LOKI_LOG, "2026-05-09")
        assert len(out["error_lines"]) == 3
        assert "finebi6.0.pdf" in out["error_lines"][0]

    def test_parse_warnings(self):
        out = parse_loki_log(SAMPLE_LOKI_LOG, "2026-05-09")
        assert len(out["warning_lines"]) == 2  # 两条 max-files 触发


class TestParseWrapperLog:

    def test_parse_exit(self):
        out = parse_wrapper_log(SAMPLE_WRAPPER_LOG)
        assert out["wrapper_exit"] == 0

    def test_parse_rss_peak(self):
        out = parse_wrapper_log(SAMPLE_WRAPPER_LOG)
        assert out["rss_peak_mb"] == 4697  # max of [793, 1653, 4697]
        assert out["rss_limit_mb"] == 18432

    def test_parse_exit_nonzero(self):
        out = parse_wrapper_log("Loki wrapper 结束 exit=137 2026-05-08 04:49:34")
        assert out["wrapper_exit"] == 137


# ─── 聚合测试 ─────────────────────────────────────────────────────────────

class TestAggregateErrors:

    def test_aggregate_by_type(self):
        errors = (
            "FAIL a.pdf: 解析失败(.pdf): No module named 'pdfminer'",
            "FAIL b.pdf: 解析失败(.pdf): No module named 'pdfminer'",
            "FAIL c.docx: 解析失败(.docx): something else",
        )
        result = aggregate_errors(errors)
        assert len(result) == 2
        # 按 count 降序: pdfminer 2 在前
        assert result[0][1] == 2
        assert "pdfminer" in result[0][0]
        assert result[1][1] == 1


# ─── 健康判断测试 ─────────────────────────────────────────────────────────

class TestAnalyzeHealth:

    def test_all_green(self):
        stats = PipelineStats(
            date_str="2026-05-09", duration_min=48.4,
            docs_total=11101, docs_failed=0, chunks_failed=0, ddl_failed=0,
            bm25_count=72991, bm25_cache_hit_pct=75,
            rss_peak_mb=5000, rss_limit_mb=18432, wrapper_exit=0,
        )
        overall, signals = analyze_health(stats)
        assert "🟢" in overall
        assert any("✅ wrapper exit=0" in s for s in signals)

    def test_with_failures(self):
        stats = PipelineStats(
            date_str="2026-05-09", duration_min=48.4,
            chunks_failed=161, wrapper_exit=0,
            rss_peak_mb=5000, rss_limit_mb=18432,
            bm25_count=1, bm25_cache_hit_pct=75,
        )
        overall, signals = analyze_health(stats)
        assert any("失败 161" in s for s in signals)

    def test_wrapper_crash(self):
        stats = PipelineStats(date_str="2026-05-07", wrapper_exit=1)
        overall, signals = analyze_health(stats)
        assert "🔴" in overall or "🟡" in overall
        assert any("exit=1" in s for s in signals)

    def test_rss_near_limit(self):
        stats = PipelineStats(
            date_str="2026-05-09", wrapper_exit=0,
            rss_peak_mb=17000, rss_limit_mb=18432,
            bm25_count=1, bm25_cache_hit_pct=75,
        )
        overall, signals = analyze_health(stats)
        assert any("接近上限" in s for s in signals)


# ─── 渲染测试（关键 OB 格式合规）─────────────────────────────────────────

class TestRenderMarkdown:

    def _stats(self):
        return PipelineStats(
            date_str="2026-05-09", duration_min=48.4,
            docs_total=11101, chunks_total=61354, ddl_total=536,
            docs_success=32, chunks_files=1337, chunks_failed=161,
            chunks_added=17712, ddl_success=2,
            bm25_count=72991, bm25_duration_sec=75.4, bm25_cache_hit_pct=75,
            rss_peak_mb=4697, rss_limit_mb=18432, wrapper_exit=0,
        )

    def test_has_frontmatter(self):
        s = self._stats()
        overall, signals = analyze_health(s)
        md = render_markdown(s, None, overall, signals, [], Path("/tmp/w.log"), Path("/tmp/l.log"))
        assert md.startswith("---\n")
        assert "type: 日报" in md
        assert "date: 2026-05-09" in md
        assert "week:" in md
        assert "tags:" in md

    def test_has_summary_section(self):
        s = self._stats()
        overall, signals = analyze_health(s)
        md = render_markdown(s, None, overall, signals, [], Path("/tmp/w.log"), Path("/tmp/l.log"))
        assert "## 全景总结" in md
        # 全景总结正文应含核心数字
        assert "11101" in md
        assert "61354" in md

    def test_has_index_tags_section(self):
        """OB 规范: 全景总结后必须有"核心索引标签"段, 至少 5 个 #tag."""
        s = self._stats()
        overall, signals = analyze_health(s)
        md = render_markdown(s, None, overall, signals, [], Path("/tmp/w.log"), Path("/tmp/l.log"))
        assert "## 核心索引标签" in md
        # 提取 #tag 个数
        import re
        tags = re.findall(r"#\S+", md)
        assert len(tags) >= 5, f"标签应 ≥5 个, 实际 {len(tags)}"

    def test_renders_error_summary(self):
        s = self._stats()
        overall, signals = analyze_health(s)
        errors = [
            ("解析失败(.pdf): No module named 'pdfminer'", 161, ["a.pdf", "b.pdf"]),
        ]
        md = render_markdown(s, None, overall, signals, errors,
                             Path("/tmp/w.log"), Path("/tmp/l.log"))
        assert "## 四、错误聚合" in md
        assert "pdfminer" in md
        assert "×161" in md

    def test_no_errors_shows_ok(self):
        s = self._stats()
        overall, signals = analyze_health(s)
        md = render_markdown(s, None, overall, signals, [], Path("/tmp/w.log"), Path("/tmp/l.log"))
        assert "无报错" in md


# ─── 端到端测试 ────────────────────────────────────────────────────────────

class TestEndToEnd:

    def test_build_report_with_real_format(self, tmp_path):
        """用 fixture 日志在临时目录端到端跑."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "loki_20260509_020012.log").write_text(SAMPLE_LOKI_LOG, encoding="utf-8")
        (log_dir / "wrapper_20260509_020002.log").write_text(SAMPLE_WRAPPER_LOG, encoding="utf-8")

        report_dir = tmp_path / "daily-reports"
        md, stats, wlog, llog = build_report(
            "2026-05-09", log_dir=log_dir, report_dir=report_dir
        )
        assert "## 全景总结" in md
        assert stats.docs_total == 11101
        assert stats.wrapper_exit == 0
        assert wlog.name == "wrapper_20260509_020002.log"
        assert llog.name == "loki_20260509_020012.log"

    def test_find_logs_returns_none_if_missing(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        w, l = find_logs_for_date("2026-05-09", log_dir)
        assert w is None and l is None

    def test_prev_stats_contract_round_trip(self, tmp_path):
        """N 日的 stats 注释能被 N+1 日 load_prev_stats 正确解析回来。"""
        from loki_daily_report import load_prev_stats
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "loki_20260508_020016.log").write_text(SAMPLE_LOKI_LOG.replace(
            "2026-05-09", "2026-05-08").replace("11101", "11082").replace(
            "61354", "43775").replace("536", "534").replace(
            "72991", "55391").replace("48.4", "169.0"), encoding="utf-8")
        (log_dir / "wrapper_20260508_020005.log").write_text(SAMPLE_WRAPPER_LOG.replace(
            "2026-05-09", "2026-05-08"), encoding="utf-8")
        report_dir = tmp_path / "daily-reports"

        # 先生成 5-8
        from loki_daily_report import build_report, write_report
        md_8, _, _, _ = build_report("2026-05-08", log_dir=log_dir, report_dir=report_dir)
        write_report(md_8, "2026-05-08", report_dir=report_dir, do_symlink=False)

        # 5-9 加载 5-8 应能拿到对比数据
        prev = load_prev_stats("2026-05-09", report_dir)
        assert prev is not None
        assert prev["docs_total"] == 11082
        assert prev["chunks_total"] == 43775
        assert prev["bm25_count"] == 55391
