#!/usr/bin/env python3
"""BM25 tokens 缓存：增量复用上一轮 jieba 切词结果

背景（详见 OB 笔记 202604262145+Loki-4_25-280min异常追溯）：
rebuild_bm25 每次跑都从 chroma 全量拉 10 万+ 条同步 jieba.cut，
单线程 CPU bound 占 188 分钟。其实大部分文档没变，tokens 可复用。

设计：
  - 上一轮 pickle 已有 doc_ids + corpus_tokens（平行 list），
    新版 pickle 增加 doc_text_sigs（同长度的 sig 列表）
  - cache key = (doc_id, sig)；命中则复用 tokens，否则现切
  - sig = sha1(searchable_text)[:16]，碰撞率 ≈ 1/2^64

API:
  compute_sig(text) -> str
  load_cache(pickle_path) -> dict[(doc_id, sig) -> list[str]]
  lookup(cache, doc_id, sig) -> list[str] | None
"""

from __future__ import annotations

import hashlib
import pickle
import sys
from pathlib import Path
from typing import Optional


def compute_sig(text: str) -> str:
    """对 searchable_text 计算 16 字符 hex sig（sha1 前 16）。"""
    if text is None:
        text = ""
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def load_cache(pickle_path: Path) -> dict:
    """从旧 pickle 构造 (doc_id, sig) → tokens 缓存。

    旧 pickle 没有 doc_text_sigs 字段时返回空 dict（首跑无 cache）。
    任何异常一律降级为空（确保 BM25 重建不被破坏）。
    """
    p = Path(pickle_path)
    if not p.exists():
        return {}
    try:
        with open(p, "rb") as f:
            raw = pickle.load(f)
    except Exception as e:
        sys.stderr.write(f"[bm25_cache] 旧 pickle 读取失败: {e}\n")
        return {}

    doc_ids = raw.get("doc_ids") or []
    sigs = raw.get("doc_text_sigs") or []
    tokens_list = raw.get("corpus_tokens") or []
    if not doc_ids or len(doc_ids) != len(sigs) or len(doc_ids) != len(tokens_list):
        # 旧版本无 sigs 字段 / 长度不一致 → 不可信，弃用
        return {}

    cache = {}
    for did, sig, toks in zip(doc_ids, sigs, tokens_list):
        if did and sig:
            cache[(did, sig)] = toks
    return cache


def lookup(cache: dict, doc_id: str, sig: str) -> Optional[list]:
    """命中返回 tokens；未命中返回 None。"""
    return cache.get((doc_id, sig))
