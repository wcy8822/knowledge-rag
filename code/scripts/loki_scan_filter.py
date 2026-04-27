#!/usr/bin/env python3
"""Loki 准入过滤：路径黑名单（强）

第一性原理：知识库的源应该是「人写的」内容，不是第三方依赖、虚拟环境、
generated artifact。本模块只做路径维度的强黑名单（最便宜的拦截层）；
项目维度的白名单由 pipeline.SCAN_DIRS 控制。

历史事故（2026-04-27）：早期某次跑把 ~/Work/projects/glm-openclaw-AI基础设施
/code/python-sdk/python3.13.2/lib/python3.13/site-packages/ 整库扫进 chroma，
导致 52,322 条第三方 .py 污染 summaries（83% 噪声），搜索 Recall@5
从 57.5% 跌回 29.2%。本模块根治。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Union

# 路径中含以下任一片段即视为脏数据（substring 检测，与位置无关）
EXCLUDED_PATH_FRAGMENTS = (
    # Python 第三方包
    "/site-packages/",
    "/dist-packages/",
    "/.venv/",
    "/venv/",
    "/.tox/",
    # 内嵌完整 Python SDK
    "/python-sdk/",
    "/Python.framework/",
    # Node / 前端构建产物
    "/node_modules/",
    "/.next/",
    "/.nuxt/",
    "/dist/",
    "/build/",
    # VCS / 缓存 / 编译产物
    "/.git/",
    "/__pycache__/",
    "/.pytest_cache/",
    "/.mypy_cache/",
    "/.ruff_cache/",
    "/.cache/",
    # 模型权重 / 向量库
    "/bge-m3-model/",
    "/chroma/",
    "/chroma-doc-knowledge",
    # 归档 / 临时
    "/archives/",
    ".bak.",        # 文件名后缀（如 server.py.bak.20260426），与 pipeline.py:145 同标准
    "/Trash/",
    "/.Trash/",
    # macOS / IDE
    "/.DS_Store",
    "/.idea/",
    "/.vscode/",
)

# 兜底正则：内嵌的 Python 标准库目录（site-packages 之外的也跳过）
_STDLIB_RE = re.compile(r"/lib/python3\.\d+/")
_PYTHON_VER_DIR_RE = re.compile(r"/python3\.\d+/")


def is_excluded_path(path: Union[str, Path]) -> bool:
    """路径中含黑名单片段则排除。"""
    p = str(path)
    for frag in EXCLUDED_PATH_FRAGMENTS:
        if frag in p:
            return True
    if _STDLIB_RE.search(p) or _PYTHON_VER_DIR_RE.search(p):
        return True
    return False


def filter_paths(paths: Iterable) -> list:
    """从 (path, ...) 序列里剔除被排除的，保持原顺序。

    支持 path 单值列表或 (path, *extra) tuple 列表。
    """
    out = []
    for item in paths:
        p = item[0] if isinstance(item, (tuple, list)) else item
        if not is_excluded_path(p):
            out.append(item)
    return out
