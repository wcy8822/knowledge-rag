"""
Pytest配置文件

提供所有测试共享的fixtures和配置
"""

import os
import sys
import pytest
import shutil
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock

# 添加src到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def project_root():
    """项目根目录"""
    return Path(__file__).parent.parent


@pytest.fixture(scope="function")
def temp_dir():
    """临时目录"""
    temp = tempfile.mkdtemp()
    yield temp
    shutil.rmtree(temp)


@pytest.fixture(scope="function")
def sample_notes_dir(temp_dir):
    """包含示例笔记的目录"""
    notes_dir = Path(temp_dir) / "sample_notes"
    notes_dir.mkdir()

    # 创建示例笔记文件
    (notes_dir / "note1.md").write_text("# 工作总结\n这是第一个笔记。", encoding='utf-8')
    (notes_dir / "note2.md").write_text("# 技术方案\n这是第二个笔记。", encoding='utf-8')
    (notes_dir / "note3.txt").write_text("项目进展情况", encoding='utf-8')

    return notes_dir


def pytest_configure(config):
    """Pytest配置"""
    config.addinivalue_line("markers", "unit: 单元测试")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "performance: 性能测试")
