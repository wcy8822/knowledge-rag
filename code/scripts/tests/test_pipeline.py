#!/usr/bin/env python3
"""Pipeline 的单元测试"""
import sys, os, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestMemoryHygiene:
    """2026-04-28 防 33GB 内存爆：GC + torch.mps.empty_cache 必须不抛错。"""

    def test_free_mps_memory_safe_on_any_backend(self):
        """无论 MPS 是否可用都不能抛异常。"""
        from loki_pipeline import _free_mps_memory
        # 不应抛任何异常
        _free_mps_memory()
        _free_mps_memory(verbose=True)

    def test_constants_optimized(self):
        """BATCH_SIZE / SLEEP_BATCH 按 M5+24G 性能压榨调整。"""
        from loki_pipeline import BATCH_SIZE, SLEEP_BATCH, _MODEL_RELOAD
        assert BATCH_SIZE >= 8, "BATCH_SIZE 应 ≥ 8 充分利用 M5 GPU"
        assert 0 < SLEEP_BATCH < 0.5, "SLEEP_BATCH 应 < 0.5s，MPS leak 已修"
        assert _MODEL_RELOAD is False, "模型重建已关闭"


class TestParseArgs:
    """2026-04-28 防 33GB 内存爆：--max-files 单次硬上限。"""

    def test_default(self):
        from loki_pipeline import _parse_args
        mode, mf = _parse_args(["loki_pipeline.py"])
        assert mode == 'all'
        assert mf is None

    def test_mode_only(self):
        from loki_pipeline import _parse_args
        mode, mf = _parse_args(["loki_pipeline.py", "docs"])
        assert mode == 'docs'
        assert mf is None

    def test_max_files_equals(self):
        from loki_pipeline import _parse_args
        mode, mf = _parse_args(["loki_pipeline.py", "--max-files=200"])
        assert mode == 'all'
        assert mf == 200

    def test_max_files_space(self):
        from loki_pipeline import _parse_args
        mode, mf = _parse_args(["loki_pipeline.py", "--max-files", "500"])
        assert mode == 'all'
        assert mf == 500

    def test_mode_and_max_files(self):
        from loki_pipeline import _parse_args
        mode, mf = _parse_args(["loki_pipeline.py", "docs", "--max-files=1500"])
        assert mode == 'docs'
        assert mf == 1500

    def test_max_files_then_mode(self):
        from loki_pipeline import _parse_args
        mode, mf = _parse_args(["loki_pipeline.py", "--max-files", "300", "ddl"])
        assert mode == 'ddl'
        assert mf == 300


class TestGetMysqlPassword:
    def test_from_env(self):
        from loki_pipeline import _get_mysql_password
        os.environ['MYSQL_ROOT_PASSWORD'] = 'test_pw_123'
        try:
            assert _get_mysql_password() == 'test_pw_123'
        finally:
            del os.environ['MYSQL_ROOT_PASSWORD']

    def test_from_secrets_file(self):
        from loki_pipeline import _get_mysql_password
        # 保存并清除环境变量
        old = os.environ.pop('MYSQL_ROOT_PASSWORD', None)
        try:
            # _get_mysql_password 会读 ~/.secrets.env
            # 这里只验证不崩溃，实际值取决于环境
            result = _get_mysql_password()
            assert isinstance(result, str)
        finally:
            if old:
                os.environ['MYSQL_ROOT_PASSWORD'] = old

    def test_empty_fallback(self):
        from loki_pipeline import _get_mysql_password
        old = os.environ.pop('MYSQL_ROOT_PASSWORD', None)
        # 临时改 HOME 让它找不到 secrets
        old_home = os.environ.get('HOME')
        os.environ['HOME'] = '/nonexistent'
        try:
            # 当前实现用 Path.home()，改 HOME 可能不够
            # 至少验证函数不崩溃
            result = _get_mysql_password()
            assert isinstance(result, str)
        finally:
            if old:
                os.environ['MYSQL_ROOT_PASSWORD'] = old
            if old_home:
                os.environ['HOME'] = old_home


class TestSupportedExt:
    def test_code_files_included(self):
        from loki_pipeline import SUPPORTED_EXT
        for ext in ['.py', '.sh', '.yaml', '.yml']:
            assert ext in SUPPORTED_EXT, f"{ext} 应在 SUPPORTED_EXT 中"

    def test_doc_files_included(self):
        from loki_pipeline import SUPPORTED_EXT
        for ext in ['.md', '.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.sql']:
            assert ext in SUPPORTED_EXT

    def test_excluded_dirs(self):
        from loki_pipeline import EXCLUDE_DIRS
        assert '.git' in EXCLUDE_DIRS
        assert '__pycache__' in EXCLUDE_DIRS
        assert 'logs' in EXCLUDE_DIRS


class TestFingerprint:
    def test_deterministic(self):
        from loki_pipeline import fingerprint
        fp1 = fingerprint("/test/file.py", 1234567890.123)
        fp2 = fingerprint("/test/file.py", 1234567890.123)
        assert fp1 == fp2

    def test_different_for_different_files(self):
        from loki_pipeline import fingerprint
        fp1 = fingerprint("/test/a.py", 1234567890.0)
        fp2 = fingerprint("/test/b.py", 1234567890.0)
        assert fp1 != fp2

    def test_different_for_different_mtime(self):
        from loki_pipeline import fingerprint
        fp1 = fingerprint("/test/a.py", 1234567890.0)
        fp2 = fingerprint("/test/a.py", 1234567891.0)
        assert fp1 != fp2

    def test_length(self):
        from loki_pipeline import fingerprint
        fp = fingerprint("/test/file.py", 1234567890.0)
        assert len(fp) == 32


class TestReadFile:
    def test_read_python(self):
        from loki_pipeline import read_file
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as f:
            f.write("def hello():\n    return 'world'\n")
            tmp = Path(f.name)
        try:
            content = read_file(tmp)
            assert "def hello" in content
        finally:
            tmp.unlink()

    def test_read_shell(self):
        from loki_pipeline import read_file
        with tempfile.NamedTemporaryFile(suffix='.sh', mode='w', delete=False) as f:
            f.write("#!/bin/bash\necho hello\n")
            tmp = Path(f.name)
        try:
            content = read_file(tmp)
            assert "echo hello" in content
        finally:
            tmp.unlink()

    def test_read_yaml(self):
        from loki_pipeline import read_file
        with tempfile.NamedTemporaryFile(suffix='.yaml', mode='w', delete=False) as f:
            f.write("key: value\nlist:\n  - a\n  - b\n")
            tmp = Path(f.name)
        try:
            content = read_file(tmp)
            assert "key: value" in content
        finally:
            tmp.unlink()

    def test_read_md(self):
        from loki_pipeline import read_file
        with tempfile.NamedTemporaryFile(suffix='.md', mode='w', delete=False) as f:
            f.write("# Title\nSome content\n")
            tmp = Path(f.name)
        try:
            content = read_file(tmp)
            assert "# Title" in content
        finally:
            tmp.unlink()


class TestContentFingerprint:
    def test_deterministic(self):
        from loki_pipeline import content_fingerprint
        fp1 = content_fingerprint("/x.md", b"hello world")
        fp2 = content_fingerprint("/x.md", b"hello world")
        assert fp1 == fp2

    def test_length_32(self):
        from loki_pipeline import content_fingerprint
        assert len(content_fingerprint("/x.md", b"abc")) == 32

    def test_path_changes_fp(self):
        from loki_pipeline import content_fingerprint
        fp1 = content_fingerprint("/a.md", b"same content")
        fp2 = content_fingerprint("/b.md", b"same content")
        assert fp1 != fp2

    def test_content_changes_fp(self):
        from loki_pipeline import content_fingerprint
        fp1 = content_fingerprint("/a.md", b"v1")
        fp2 = content_fingerprint("/a.md", b"v2")
        assert fp1 != fp2

    def test_independent_of_mtime(self):
        """v3 核心特性：不依赖 mtime"""
        from loki_pipeline import content_fingerprint, fingerprint
        # 同 path + 同 content → content_fp 不变
        cfp1 = content_fingerprint("/a.md", b"unchanged")
        cfp2 = content_fingerprint("/a.md", b"unchanged")
        assert cfp1 == cfp2
        # 但 mtime_fp 因 mtime 不同而变（旧体系的痛点）
        mfp1 = fingerprint("/a.md", 100.0)
        mfp2 = fingerprint("/a.md", 200.0)
        assert mfp1 != mfp2

    def test_empty_content(self):
        from loki_pipeline import content_fingerprint
        assert len(content_fingerprint("/x.md", b"")) == 32

    def test_chinese_content(self):
        from loki_pipeline import content_fingerprint
        fp = content_fingerprint("/x.md", "你好世界".encode("utf-8"))
        assert len(fp) == 32

    def test_different_from_mtime_fp(self):
        from loki_pipeline import content_fingerprint, fingerprint
        cfp = content_fingerprint("/a.md", b"hello")
        mfp = fingerprint("/a.md", 1234567890.0)
        # 极小概率碰撞，但实际算出来一定不同
        assert cfp != mfp


class TestParallelIOPipeline:
    """2026-05-07 回归防御：concurrent.futures.ThreadPoolExecutor 没有 .imap()，
    只能用 .map()。5-7 凌晨 02:00 launchd 整夜 pipeline 因 AttributeError crash。"""

    def test_threadpool_has_map_not_imap(self):
        """ThreadPoolExecutor 必须用 map（imap 是 multiprocessing.Pool 的 API）。"""
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            assert hasattr(pool, 'map'), "ThreadPoolExecutor 必须有 map"
            assert not hasattr(pool, 'imap'), \
                "ThreadPoolExecutor 不该有 imap（那是 multiprocessing.Pool 的 API）"

    def test_pipeline_source_uses_pool_map_not_imap(self):
        """源码静态扫描：禁止 pool.imap( 出现在 loki_pipeline.py。"""
        from pathlib import Path
        src = Path(__file__).parent.parent / "loki_pipeline.py"
        text = src.read_text(encoding="utf-8")
        assert "pool.imap(" not in text, \
            "loki_pipeline.py 仍含 pool.imap(，会触发 AttributeError；应用 pool.map("
        assert "pool.map(" in text, "loki_pipeline.py 应使用 pool.map( 做并行 I/O"

    def test_threadpool_map_streams_tuple_results_in_order(self):
        """sanity：ThreadPoolExecutor.map 能按提交顺序流式 yield tuple，与生产代码同型。"""
        import concurrent.futures

        def _read_one(item):
            i, val = item
            return (i, val.upper(), None)

        items = [(i, c) for i, c in enumerate(['a', 'b', 'c', 'd'])]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(_read_one, items))
        assert results == [(0, 'A', None), (1, 'B', None), (2, 'C', None), (3, 'D', None)], \
            "ThreadPoolExecutor.map 应按输入顺序返回结果"


class TestChunksMaxFilesLimit:
    """2026-05-07 chunks 限流：防 daily pipeline 撞 wrapper 90 分钟 CPU 上限。
    a32e321 引入 chunks 全量 backfill (9496 文件) 而无 max_files 限制，
    会让每天 02:00 launchd 必撞超时。run_chunks 应接受 max_files 参数。"""

    def test_run_chunks_accepts_max_files(self):
        """run_chunks 函数签名必须有 max_files 可选参数（默认 None 向后兼容）。"""
        import inspect
        from loki_pipeline import run_chunks
        sig = inspect.signature(run_chunks)
        assert 'max_files' in sig.parameters, \
            "run_chunks 必须接受 max_files 参数防 daily pipeline 超时"
        assert sig.parameters['max_files'].default is None, \
            "max_files 默认应为 None（不限流），保持向后兼容"

    def test_main_passes_max_files_to_run_chunks(self):
        """main() 必须把命令行的 max_files 同时传给 run_docs 和 run_chunks。"""
        from pathlib import Path
        src = Path(__file__).parent.parent / "loki_pipeline.py"
        text = src.read_text(encoding="utf-8")
        # 既要 run_docs 传 max_files，也要 run_chunks 传 max_files
        assert "run_chunks(model, col_chunks, state, max_files=max_files)" in text, \
            "main() 必须把 max_files 传给 run_chunks，否则 chunks 全量跑会撞超时"

    def test_run_chunks_has_max_files_truncation(self):
        """run_chunks 内部必须有 max_files 截断逻辑（与 run_docs 风格对齐）。"""
        from pathlib import Path
        src = Path(__file__).parent.parent / "loki_pipeline.py"
        text = src.read_text(encoding="utf-8")
        # 截断逻辑特征：max_files is not None 判断 + todo 切片
        assert "max_files is not None" in text, "应有 max_files is not None 判断"
        # chunks 限流日志特征
        assert "(chunks)" in text, "chunks 限流日志应可识别"
