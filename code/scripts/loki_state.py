#!/usr/bin/env python3
"""Loki pipeline state v2 — dict[path → fp] 结构

历史 v1: List[str]，set of fingerprint(=sha256(path:mtime))
  问题：fingerprint 含 mtime → 同一文件 mtime 变更后旧 fingerprint 残留 → 单调增长
  现场：152K state vs 63K chroma，差额 9 万

v2: {"version": 2, "docs": {path: fp}, "ddl": [md5, ...]}
  优势：同一 path 后写覆盖前写，杜绝 mtime 残留
  迁移：v1 → v2 一次性从 ChromaDB metadata 反向重建（id 即 fp，metadata.path 可读）

API:
    state = StateV2.load(path)              # 自动检测 v1/v2，必要时迁移
    state.is_doc_done(path, fp)             # 增量判定
    state.mark_doc(path, fp)                # 登记
    state.is_ddl_done(md5)                  # DDL 判定
    state.mark_ddl(md5)                     # DDL 登记
    state.save(path)                        # 写 v2 JSON
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StateV2:
    docs: dict = field(default_factory=dict)   # path -> fingerprint
    ddl: set = field(default_factory=set)      # set of DDL md5

    # ---- I/O ----

    @classmethod
    def load(cls, state_path: Path, chroma_loader=None) -> "StateV2":
        """读 state.json；v1 → 触发迁移；空/坏文件 → 返回空 state。

        chroma_loader: 可调用对象，返回 (docs_dict, ddl_set) 用于 v1→v2 迁移；
            None 时迁移失败安全降级（视作空 state，让 pipeline 重跑）。
        """
        if not Path(state_path).exists():
            return cls()
        try:
            raw = json.loads(Path(state_path).read_text(encoding="utf-8"))
        except Exception as e:
            sys.stderr.write(f"[loki_state] 解析失败: {e}\n")
            return cls()

        if isinstance(raw, dict) and raw.get("version") == 2:
            return cls(
                docs=dict(raw.get("docs") or {}),
                ddl=set(raw.get("ddl") or []),
            )
        if isinstance(raw, list):
            sys.stderr.write("[loki_state] 检测到 v1 List 格式，触发迁移...\n")
            return cls._migrate_v1(raw, chroma_loader)
        sys.stderr.write("[loki_state] 未知格式，返回空 state\n")
        return cls()

    @classmethod
    def _migrate_v1(cls, v1_ids: list, chroma_loader=None) -> "StateV2":
        if chroma_loader is None:
            sys.stderr.write("[loki_state] 无 chroma_loader，迁移降级为空（pipeline 将重处理）\n")
            return cls()
        try:
            docs, ddl = chroma_loader()
            sys.stderr.write(
                f"[loki_state] 迁移完成: docs={len(docs)} ddl={len(ddl)}\n"
            )
            return cls(docs=dict(docs), ddl=set(ddl))
        except Exception as e:
            sys.stderr.write(f"[loki_state] 迁移失败: {e}（降级为空）\n")
            return cls()

    def save(self, state_path: Path) -> None:
        Path(state_path).write_text(self.to_json(), encoding="utf-8")

    def to_json(self) -> str:
        return json.dumps(
            {"version": 2, "docs": self.docs, "ddl": sorted(self.ddl)},
            ensure_ascii=False,
        )

    # ---- 业务判定 ----

    def is_doc_done(self, path: str, *fps: str) -> bool:
        """任一 fp 命中即视为已处理。

        v3 兼容：传入多个 fp（如 content_fp, mtime_fp）支持新旧 fingerprint 共存。
        典型用法 is_doc_done(path, content_fp, mtime_fp) — content 没变就跳过，
        即使 mtime 变了也不重处理（v2 的 mtime_fp 仍能命中旧条目）。
        """
        cur = self.docs.get(str(path))
        if cur is None:
            return False
        return any(cur == fp for fp in fps if fp)

    def mark_doc(self, path: str, fp: str) -> None:
        self.docs[str(path)] = fp

    def is_ddl_done(self, md5: str) -> bool:
        return md5 in self.ddl

    def mark_ddl(self, md5: str) -> None:
        self.ddl.add(md5)

    # ---- 统计 ----

    def __len__(self) -> int:
        return len(self.docs) + len(self.ddl)


_HEX32_RE = None


def _is_valid_pipeline_entry(fp: str, path: str) -> bool:
    """过滤迁移时的脏数据：只保留 pipeline.py fingerprint 体系的条目。

    - fp 必须是 32 字符 hex（pipeline.fingerprint 输出格式）
    - path 必须是绝对路径（早期 doc_X 体系把 basename 写进 metadata.path，跳过）
    """
    global _HEX32_RE
    if _HEX32_RE is None:
        import re
        _HEX32_RE = re.compile(r"^[0-9a-f]{32}$")
    return bool(_HEX32_RE.match(fp)) and path.startswith("/")


def build_chroma_loader(
    chroma_path: str,
    summaries_col: str = "doc_knowledge_bge_m3",
    ddl_col: str = "ddl_schema_bge_m3",
):
    """返回 chroma_loader 闭包。延迟导入 chromadb。"""

    def _loader():
        import chromadb
        client = chromadb.PersistentClient(path=str(chroma_path))
        docs = {}
        skipped = 0
        try:
            col = client.get_collection(summaries_col)
            offset = 0
            batch = 5000
            while True:
                got = col.get(include=["metadatas"], limit=batch, offset=offset)
                ids = got.get("ids") or []
                metas = got.get("metadatas") or []
                if not ids:
                    break
                for fp, m in zip(ids, metas):
                    if not m:
                        skipped += 1
                        continue
                    p = m.get("path")
                    if p and _is_valid_pipeline_entry(fp, str(p)):
                        docs[str(p)] = fp
                    else:
                        skipped += 1
                if len(ids) < batch:
                    break
                offset += batch
        except Exception as e:
            sys.stderr.write(f"[loki_state] summaries 拉取失败: {e}\n")
        if skipped:
            sys.stderr.write(f"[loki_state] 迁移过滤掉 {skipped} 条非 pipeline 体系 id（早期 doc_X / oil-algo 等）\n")

        ddl = set()
        try:
            col = client.get_collection(ddl_col)
            got = col.get(include=[], limit=10000)
            ids = got.get("ids") or []
            ddl.update(ids)
        except Exception as e:
            sys.stderr.write(f"[loki_state] ddl 拉取失败: {e}\n")

        return docs, ddl

    return _loader
