#!/usr/bin/env python3
"""
工具函数模块
提供文件处理、日志记录、哈希计算等通用功能
"""

import os
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_file_hash(file_path: str) -> str:
    """
    计算文件的SHA256哈希值

    Args:
        file_path: 文件路径

    Returns:
        SHA256哈希值（hex格式）
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # 分块读取大文件
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希失败 {file_path}: {e}")
        return "error"


def get_file_size(file_path: str) -> int:
    """
    获取文件大小（字节）

    Args:
        file_path: 文件路径

    Returns:
        文件大小（字节）
    """
    try:
        return os.path.getsize(file_path)
    except Exception as e:
        logger.error(f"获取文件大小失败 {file_path}: {e}")
        return 0


def format_bytes(size_bytes: int) -> str:
    """
    格式化字节大小为人类可读格式

    Args:
        size_bytes: 字节数

    Returns:
        格式化的字符串（如 "1.5 MB"）
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def is_valid_note_file(file_path: str) -> bool:
    """
    检查文件是否为有效的笔记文件

    Args:
        file_path: 文件路径

    Returns:
        是否为有效笔记文件
    """
    # 排除条件
    path = Path(file_path)

    # 1. 排除隐藏文件和系统文件
    if path.name.startswith('.'):
        return False

    # 2. 排除系统目录
    exclude_dirs = [
        '.git', 'node_modules', '__pycache__', '.pytest_cache',
        'venv', 'env', '.venv', 'dist', 'build',
        'Library', 'Applications', '.cursor', '.vscode',
        'python-sdk', 'Music'
    ]

    for exclude_dir in exclude_dirs:
        if f"/{exclude_dir}/" in str(path) or str(path).startswith(f"{exclude_dir}/"):
            return False

    # 3. 检查文件扩展名
    valid_extensions = {'.md', '.txt', '.markdown', '.docx', '.pdf'}
    if path.suffix.lower() not in valid_extensions:
        return False

    # 4. 检查文件大小（排除过大或空文件）
    try:
        file_size = os.path.getsize(file_path)
        if file_size == 0 or file_size > 50 * 1024 * 1024:  # >50MB
            return False
    except:
        return False

    # 5. 排除特定文件名模式
    exclude_patterns = [
        'LICENSE', 'README', 'CHANGELOG', 'TODO',
        'package-lock', 'yarn.lock', 'poetry.lock'
    ]

    for pattern in exclude_patterns:
        if pattern.lower() in path.name.lower():
            # 但保留中文的README和项目文档
            if not any(x in path.name for x in ['工作', '笔记', '总结', '汇报', '文档', '说明']):
                return False

    return True


def save_json_report(data: Dict[str, Any], output_path: str) -> bool:
    """
    保存JSON格式的报告

    Args:
        data: 要保存的数据
        output_path: 输出文件路径

    Returns:
        是否保存成功
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"✅ 报告已保存: {output_path}")
        return True
    except Exception as e:
        logger.error(f"❌ 保存报告失败 {output_path}: {e}")
        return False


def generate_timestamp() -> str:
    """
    生成当前时间戳（ISO格式）

    Returns:
        ISO格式时间戳
    """
    return datetime.now().isoformat()


def generate_report_filename(prefix: str, extension: str = 'json') -> str:
    """
    生成报告文件名

    Args:
        prefix: 文件名前缀
        extension: 文件扩展名

    Returns:
        完整的文件名
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{prefix}_{timestamp}.{extension}"


def create_file_metadata(file_path: str, file_id: str = None) -> Dict[str, Any]:
    """
    创建文件元数据

    Args:
        file_path: 文件路径
        file_id: 文件ID（可选）

    Returns:
        文件元数据字典
    """
    path = Path(file_path)

    return {
        "id": file_id or f"note_{hashlib.md5(file_path.encode()).hexdigest()[:8]}",
        "path": str(path.absolute()),
        "filename": path.name,
        "format": path.suffix.lstrip('.'),
        "size_bytes": get_file_size(file_path),
        "size_human": format_bytes(get_file_size(file_path)),
        "checksum": calculate_file_hash(file_path),
        "last_modified": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
        "scan_timestamp": generate_timestamp()
    }


def print_section_header(title: str, width: int = 60):
    """打印章节标题"""
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_subsection(title: str, width: int = 60):
    """打印子章节标题"""
    print(f"\n{title}")
    print("-" * width)


def print_progress(current: int, total: int, prefix: str = "进度"):
    """
    打印进度条

    Args:
        current: 当前进度
        total: 总数
        prefix: 前缀文本
    """
    percentage = (current / total * 100) if total > 0 else 0
    bar_length = 40
    filled_length = int(bar_length * current // total) if total > 0 else 0
    bar = '█' * filled_length + '-' * (bar_length - filled_length)

    print(f'\r{prefix}: |{bar}| {current}/{total} ({percentage:.1f}%)', end='', flush=True)

    if current == total:
        print()  # 换行


def ensure_directory_exists(directory: str):
    """
    确保目录存在，不存在则创建

    Args:
        directory: 目录路径
    """
    Path(directory).mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    # 测试工具函数
    print("🧪 测试工具函数...")

    # 测试时间戳
    print(f"时间戳: {generate_timestamp()}")

    # 测试文件名生成
    print(f"报告文件名: {generate_report_filename('test_report')}")

    # 测试格式化
    print(f"格式化大小: {format_bytes(1234567)}")

    print("✅ 工具函数测试完成")
