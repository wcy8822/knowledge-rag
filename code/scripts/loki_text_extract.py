#!/usr/bin/env python3
"""文本入库前的智能提取：根据扩展名选择截断策略

现状：73% 代码文件被 MAX_CHARS=2000 粗暴尾截，imports / class def / main 等
关键信息丢失。修复策略（最小侵入，不动 chunk pipeline）：

  - 文档 (.md/.pdf/.txt 等)：保持原 head 截断（首部即摘要语义）
  - 代码 (.py/.sh/.yaml/.yml/.sql)：智能 head + tail 提取
       short  (≤max_chars)   → 原文
       long   (>max_chars)   → 70% head + 30% tail，中间 [truncated] 占位
       这样保留了顶部 imports/docstring/前几个 def，以及末尾 main 块。

后续 chunk pipeline 升级（.py 进 chunks 集合）作为独立任务。
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

DEFAULT_MAX_CHARS_DOC = 2000
DEFAULT_MAX_CHARS_CODE = 8000

CODE_EXTS = frozenset({".py", ".sh", ".yaml", ".yml", ".sql"})


def is_code_path(path: Union[str, Path]) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in CODE_EXTS


def smart_code_extract(text: str, max_chars: int = DEFAULT_MAX_CHARS_CODE) -> str:
    """长代码 → head 70% + tail 30%；短代码原样。"""
    if len(text) <= max_chars:
        return text

    head_budget = max_chars * 7 // 10
    tail_budget = max_chars - head_budget - 80  # 留 80 字给占位行
    if tail_budget < 0:
        tail_budget = 0

    lines = text.split("\n")
    head_lines = []
    head_chars = 0
    for ln in lines:
        if head_chars + len(ln) + 1 > head_budget:
            break
        head_lines.append(ln)
        head_chars += len(ln) + 1

    tail_lines = []
    tail_chars = 0
    for ln in reversed(lines):
        if tail_chars + len(ln) + 1 > tail_budget:
            break
        tail_lines.append(ln)
        tail_chars += len(ln) + 1
    tail_lines.reverse()

    # head + tail 重叠保护：当文件较小但分布不均匀时，重叠则直接 head 截断
    if len(head_lines) + len(tail_lines) >= len(lines):
        return text[:max_chars]

    omitted_lines = len(lines) - len(head_lines) - len(tail_lines)
    omitted_chars = len(text) - head_chars - tail_chars
    placeholder = f"\n\n... [truncated {omitted_lines} lines / {omitted_chars} chars] ...\n\n"
    return "\n".join(head_lines) + placeholder + "\n".join(tail_lines)


def extract_for_embed(
    path: Union[str, Path],
    text: str,
    max_chars_doc: int = DEFAULT_MAX_CHARS_DOC,
    max_chars_code: int = DEFAULT_MAX_CHARS_CODE,
) -> str:
    """统一入口：根据 path 扩展名选 doc / code 策略。"""
    if is_code_path(path):
        return smart_code_extract(text, max_chars=max_chars_code)
    return text[:max_chars_doc]
