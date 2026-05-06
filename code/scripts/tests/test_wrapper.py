#!/usr/bin/env python3
"""loki_pipeline_wrapper.sh 守护逻辑 sanity 测试。

不真跑 pipeline（太慢），只做静态检查 + 关键守护点存在性。
完整端到端验收靠 Step 4 灰度跑实测。
"""

import re
import subprocess
from pathlib import Path

WRAPPER = Path(__file__).parent.parent / "loki_pipeline_wrapper.sh"


class TestWrapperSyntax:
    def test_file_exists(self):
        assert WRAPPER.exists(), f"wrapper 不存在: {WRAPPER}"

    def test_bash_syntax_ok(self):
        r = subprocess.run(["bash", "-n", str(WRAPPER)],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"bash 语法错: {r.stderr}"

    def test_executable(self):
        import os
        assert os.access(WRAPPER, os.X_OK), "wrapper 应有执行权限"


class TestWrapperGuards:
    """防 33GB 内存爆事故关键守护点必须存在。"""

    @classmethod
    def setup_class(cls):
        cls.content = WRAPPER.read_text(encoding="utf-8")

    def test_has_rss_monitor_loop(self):
        """必须有 RSS 监控循环。"""
        assert "ps -o rss=" in self.content, "缺 RSS 监控"
        assert "kill -TERM" in self.content, "超限必须 SIGTERM"
        assert "kill -KILL" in self.content, "SIGTERM 后必须 SIGKILL 兜底"

    def test_has_mem_limit(self):
        """必须有内存上限常量，且在合理范围。"""
        m = re.search(r"MEM_LIMIT_MB=(\d+)", self.content)
        assert m, "缺 MEM_LIMIT_MB"
        limit = int(m.group(1))
        assert 4096 <= limit <= 20480, f"MEM_LIMIT_MB={limit} 应在 4-20GB 之间（当前 M5 24GB 物理）"

    def test_has_cpu_time_limit(self):
        """必须有 CPU 时间上限（macOS 唯一可用 ulimit）。"""
        assert "ulimit -t" in self.content, "缺 ulimit -t CPU 时间上限"

    def test_does_not_use_dangerous_high_watermark(self):
        """绝不能设 PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0（官方警告会致系统崩）。

        允许注释里提及（警示），不允许 export/赋值激活。
        """
        for line in self.content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue  # 注释 OK
            assert "HIGH_WATERMARK_RATIO=0" not in stripped, \
                f"危险设置出现在非注释行: {stripped}"

    def test_default_max_files_injected(self):
        """如未传 --max-files，wrapper 必须注入默认上限。"""
        assert "--max-files" in self.content
        assert "HAS_MAX" in self.content, "缺 --max-files 自动注入逻辑"
