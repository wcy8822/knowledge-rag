#!/usr/bin/env python3
"""loki_scan_filter 单元测试 (J.2)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loki_scan_filter import (  # noqa: E402
    filter_paths,
    is_excluded_path,
    is_low_value_file,
)


class TestLowValuePyFilter:
    """2026-04-28 防 33GB 内存爆事故：拦低价值 test/临时 .py。"""

    def test_test_prefix(self):
        assert is_low_value_file("/foo/test_something.py")
        assert is_low_value_file("test_120k_complete.py")
        assert is_low_value_file("/x/y/test_decision_logic.py")

    def test_test_suffix(self):
        assert is_low_value_file("foo_test.py")
        assert is_low_value_file("/a/b/end_to_end_verifier_test.py")

    def test_numbered_test_suffix(self):
        assert is_low_value_file("downstream_integration_tester_1.py")
        assert is_low_value_file("foo_test_3.py")

    def test_specific_low_value_names(self):
        assert is_low_value_file("bulletproof_validation_test.py")
        assert is_low_value_file("standalone_test_runner.py")
        assert is_low_value_file("reliable_validation_test.py")
        assert is_low_value_file("autonomous_local_test_suite.py")
        assert is_low_value_file("ultra_stable_prod_test.py")
        assert is_low_value_file("check_sheets.py")
        assert is_low_value_file("read_headers.py")
        assert is_low_value_file("inspect_final_sheet.py")
        assert is_low_value_file("monitor_test_progress.py")

    def test_high_value_py_kept(self):
        # 真业务代码不应被误杀
        assert not is_low_value_file("loki_pipeline.py")
        assert not is_low_value_file("server.py")
        assert not is_low_value_file("merchant_image_radar.py")
        assert not is_low_value_file("/path/to/main.py")

    def test_non_py_ignored(self):
        # 非 .py 直接放行，由 is_excluded_path 决定
        assert not is_low_value_file("test_foo.md")
        assert not is_low_value_file("test_something.sql")
        assert not is_low_value_file("foo_test.txt")

    def test_case_insensitive(self):
        assert is_low_value_file("Test_Foo.PY")
        assert is_low_value_file("FOO_TEST.py")


class TestExcludedThirdParty:
    def test_site_packages(self):
        assert is_excluded_path("/Users/x/proj/.venv/lib/python3.12/site-packages/foo.py")
        assert is_excluded_path(
            "/Users/didi/Work/projects/glm-openclaw/code/python-sdk/python3.13.2/lib/python3.13/site-packages/README.txt"
        )

    def test_dist_packages(self):
        assert is_excluded_path("/usr/lib/python3/dist-packages/anything.py")

    def test_venv(self):
        assert is_excluded_path("/Users/didi/Work/projects/qcc-dashboard/.venv/bin/runxlrd.py")
        assert is_excluded_path("/some/proj/venv/lib/x.py")

    def test_python_sdk(self):
        assert is_excluded_path(
            "/Users/didi/Work/projects/glm-openclaw/code/python-sdk/python3.13.2/lib/python3.13/threading.py"
        )

    def test_python_framework(self):
        assert is_excluded_path("/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/abc.py")


class TestExcludedNodeFront:
    def test_node_modules(self):
        assert is_excluded_path("/Users/x/proj/node_modules/react/index.js")

    def test_next_build(self):
        assert is_excluded_path("/Users/x/proj/.next/server/foo.js")
        assert is_excluded_path("/Users/x/proj/dist/bundle.js")
        assert is_excluded_path("/Users/x/proj/build/index.html")


class TestExcludedVcsAndCache:
    def test_git(self):
        assert is_excluded_path("/proj/.git/objects/abc")

    def test_pycache(self):
        assert is_excluded_path("/proj/x/__pycache__/foo.pyc")

    def test_pytest_cache(self):
        assert is_excluded_path("/proj/.pytest_cache/v/cache/lastfailed")

    def test_ds_store(self):
        assert is_excluded_path("/Users/x/Work/.DS_Store")


class TestExcludedArchives:
    def test_archives(self):
        assert is_excluded_path("/proj/archives/2024/x.md")

    def test_bak(self):
        assert is_excluded_path("/proj/server.py.bak.20260426")

    def test_trash(self):
        assert is_excluded_path("/Users/x/.Trash/x.md")


class TestExcludedModelStorage:
    def test_bge_model(self):
        assert is_excluded_path("/Users/x/proj/bge-m3-model/bge-m3/foo.bin")

    def test_chroma_dir(self):
        assert is_excluded_path("/Users/x/Work/data/vectors/data/chroma-doc-knowledge-bge/x.bin")


class TestNotExcluded:
    def test_obsidian_note(self):
        assert not is_excluded_path("/Users/didi/Work/docs/obsidian-vault/obsidian/_MOC/外部笔记索引.md")

    def test_loki_source(self):
        assert not is_excluded_path("/Users/didi/Work/projects/knowledge-rag-知识库/code/scripts/loki_pipeline.py")

    def test_project_doc(self):
        assert not is_excluded_path("/Users/didi/Work/projects/fgw/README.md")

    def test_safe_keyword_in_filename(self):
        # "build_strategy.md" 不应被 /build/ 误伤（关键是要 /build/ 是路径段）
        assert not is_excluded_path("/Users/x/Work/docs/build_strategy.md")
        # "venv-research.md" 也不该被命中
        assert not is_excluded_path("/Users/x/Work/docs/venv-research.md")


class TestFilterPaths:
    def test_single_path_list(self):
        paths = ["/proj/loki.py", "/proj/.venv/x.py", "/proj/note.md"]
        out = filter_paths(paths)
        assert out == ["/proj/loki.py", "/proj/note.md"]

    def test_tuple_with_extras(self):
        paths = [
            ("/proj/loki.py", 12345.0),
            ("/proj/.venv/x.py", 12346.0),
            ("/proj/note.md", 12347.0),
        ]
        out = filter_paths(paths)
        assert len(out) == 2
        assert out[0][0] == "/proj/loki.py"
        assert out[1][0] == "/proj/note.md"

    def test_empty(self):
        assert filter_paths([]) == []

    def test_pathlib_path(self):
        paths = [Path("/proj/loki.py"), Path("/proj/.venv/x.py")]
        out = filter_paths(paths)
        assert len(out) == 1
        assert str(out[0]) == "/proj/loki.py"
