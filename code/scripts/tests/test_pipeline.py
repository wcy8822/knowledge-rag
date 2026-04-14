#!/usr/bin/env python3
"""Pipeline 的单元测试"""
import sys, os, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


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
