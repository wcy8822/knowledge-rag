#!/usr/bin/env python3
"""loki_text_extract 单元测试 (E.2)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loki_text_extract import (  # noqa: E402
    DEFAULT_MAX_CHARS_CODE,
    DEFAULT_MAX_CHARS_DOC,
    extract_for_embed,
    is_code_path,
    smart_code_extract,
)


class TestIsCodePath:
    def test_python(self):
        assert is_code_path("/x/y.py")
        assert is_code_path(Path("/x/y.py"))

    def test_shell(self):
        assert is_code_path("a.sh")

    def test_yaml(self):
        assert is_code_path("a.yaml")
        assert is_code_path("a.yml")

    def test_sql(self):
        assert is_code_path("a.sql")

    def test_doc_not_code(self):
        assert not is_code_path("a.md")
        assert not is_code_path("a.pdf")
        assert not is_code_path("a.txt")
        assert not is_code_path("a.docx")

    def test_uppercase(self):
        assert is_code_path("A.PY")


class TestSmartCodeExtract:
    def test_short_returns_unchanged(self):
        text = "import os\n" * 10
        assert smart_code_extract(text, max_chars=8000) == text

    def test_long_includes_head_and_tail(self):
        head = "\n".join(f"# head_line_{i}" for i in range(50))
        body = "\n".join(f"# middle_line_{i}" for i in range(2000))
        tail = "\n".join(f"# tail_line_{i}" for i in range(50))
        text = head + "\n" + body + "\n" + tail

        out = smart_code_extract(text, max_chars=2000)
        assert len(out) <= 2200
        assert "head_line_0" in out
        assert "tail_line_49" in out
        assert "[truncated" in out

    def test_includes_main_block_at_tail(self):
        head = "import os\nimport sys\n\nclass Foo:\n    def bar(self):\n        pass\n\n"
        body = "\n".join(f"    # padding line {i}" for i in range(2000))
        tail = '\nif __name__ == "__main__":\n    main()\n'
        text = head + body + tail

        out = smart_code_extract(text, max_chars=2000)
        assert "import os" in out
        assert "class Foo" in out
        assert '__name__ == "__main__"' in out

    def test_exactly_max_chars(self):
        text = "x" * 2000
        out = smart_code_extract(text, max_chars=2000)
        assert out == text

    def test_overlapping_falls_back_to_head(self):
        """边界：max_chars 极小（小于一行长度），fallback 到 head 截断。"""
        text = "x" * 100
        out = smart_code_extract(text, max_chars=10)
        assert len(out) <= 200

    def test_output_size_within_budget(self):
        text = "a" * 50000
        out = smart_code_extract(text, max_chars=8000)
        assert len(out) <= 8200


class TestExtractForEmbed:
    def test_doc_path_uses_head_truncation(self):
        text = "Hello\n" * 1000
        out = extract_for_embed("/x.md", text, max_chars_doc=100)
        assert len(out) == 100
        assert out == text[:100]

    def test_code_path_uses_smart(self):
        head = "import os\n" * 10
        body = "x\n" * 5000
        tail = "if __name__:\n    main()\n"
        text = head + body + tail
        out = extract_for_embed("/x.py", text, max_chars_code=2000)
        assert "import os" in out
        assert "[truncated" in out
        assert "__name__" in out

    def test_short_code_unchanged(self):
        text = "print('hi')\n"
        out = extract_for_embed("/x.py", text)
        assert out == text

    def test_default_max_chars_code(self):
        text = "a" * (DEFAULT_MAX_CHARS_CODE - 1)
        out = extract_for_embed("/x.py", text)
        assert out == text

    def test_default_max_chars_doc(self):
        text = "a" * (DEFAULT_MAX_CHARS_DOC + 1000)
        out = extract_for_embed("/x.md", text)
        assert len(out) == DEFAULT_MAX_CHARS_DOC

    def test_unknown_ext_treated_as_doc(self):
        text = "x" * 5000
        out = extract_for_embed("/x.zip", text, max_chars_doc=100)
        assert len(out) == 100
