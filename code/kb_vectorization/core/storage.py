"""
本地知识库全量向量化自动化系统 - 向量存储模块
版本: v1.0
日期: 2026-03-01

本模块实现：
- 向量数据持久化
- 向量检索支持
- 元数据管理
- 存储抽象（Chroma/FAISS）
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict

from .base import VectorStore, VectorChunk, SearchResult
from .config import Config
from .utils import (
    setup_logger,
    cosine_similarity,
    ensure_directory,
    get_file_hash,
    sanitize_text,
)


# 元数据存储类
class MetadataStore:
    """元数据存储"""

    def __init__(self, config: Config):
        """
        初始化元数据存储

        Args:
            config: 配置对象
        """
        self.config = config
        self.logger = setup_logger("metadata", config.log_dir, config.log_level)

        self.metadata_file = config.get("storage.metadata.file", "./data/vector_db/metadata.json")
        self.backup_dir = config.get("storage.metadata.backup_dir", "./data/vector_db/backup")
        self.auto_backup = config.get("storage.metadata.auto_backup", True)
        self.backup_count = config.get("storage.metadata.backup_count", 5)

        # 确保目录存在
        ensure_directory(os.path.dirname(self.metadata_file))
        ensure_directory(self.backup_dir)

        # 元数据
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._file_index: Dict[str, List[str]] = {}  # 文件路径 -> 向量ID列表

        # 加载元数据
        self._load_metadata()

    def _load_metadata(self) -> None:
        """加载元数据"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._metadata = data.get("vectors", {})
                    self._file_index = data.get("file_index", {})
                self.logger.info(f"加载元数据: {len(self._metadata)} 个向量")
            except Exception as e:
                self.logger.warning(f"加载元数据失败: {e}")

    def _save_metadata(self) -> None:
        """保存元数据"""
        try:
            data = {
                "vectors": self._metadata,
                "file_index": self._file_index,
                "updated_at": datetime.now().isoformat()
            }

            # 备份
            if self.auto_backup:
                self._backup_metadata()

            # 保存
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.logger.debug(f"保存元数据: {len(self._metadata)} 个向量")

        except Exception as e:
            self.logger.error(f"保存元数据失败: {e}")

    def _backup_metadata(self) -> None:
        """备份元数据"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(self.backup_dir, f"metadata_{timestamp}.json")

            # 复制当前元数据
            if os.path.exists(self.metadata_file):
                shutil.copy2(self.metadata_file, backup_file)

            # 清理旧备份
            self._cleanup_backups()

        except Exception as e:
            self.logger.warning(f"备份元数据失败: {e}")

    def _cleanup_backups(self) -> None:
        """清理旧备份"""
        try:
            backups = sorted(Path(self.backup_dir).glob("metadata_*.json"),
                           reverse=True)

            for backup in backups[self.backup_count:]:
                backup.unlink()
                self.logger.debug(f"删除旧备份: {backup}")

        except Exception as e:
            self.logger.warning(f"清理备份失败: {e}")

    def add_vector(self, chunk: VectorChunk) -> None:
        """
        添加向量元数据

        Args:
            chunk: 向量块
        """
        self._metadata[chunk.id] = {
            "id": chunk.id,
            "file_path": chunk.file_path,
            "file_name": chunk.file_name,
            "category": chunk.category,
            "chunk_index": chunk.chunk_index,
            "chunk_text": chunk.chunk_text,
            "metadata": chunk.metadata
        }

        # 更新文件索引
        if chunk.file_path not in self._file_index:
            self._file_index[chunk.file_path] = []
        self._file_index[chunk.file_path].append(chunk.id)

        # 保存元数据
        self._save_metadata()

    def add_vectors(self, chunks: List[VectorChunk]) -> None:
        """
        批量添加向量元数据

        Args:
            chunks: 向量块列表
        """
        for chunk in chunks:
            self._metadata[chunk.id] = {
                "id": chunk.id,
                "file_path": chunk.file_path,
                "file_name": chunk.file_name,
                "category": chunk.category,
                "chunk_index": chunk.chunk_index,
                "chunk_text": chunk.chunk_text,
                "metadata": chunk.metadata
            }

            if chunk.file_path not in self._file_index:
                self._file_index[chunk.file_path] = []
            self._file_index[chunk.file_path].append(chunk.id)

        self._save_metadata()

    def get_vector(self, vector_id: str) -> Optional[Dict[str, Any]]:
        """
        获取向量元数据

        Args:
            vector_id: 向量ID

        Returns:
            元数据字典，不存在返回 None
        """
        return self._metadata.get(vector_id)

    def get_vectors_by_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        获取文件的所有向量元数据

        Args:
            file_path: 文件路径

        Returns:
            元数据列表
        """
        vector_ids = self._file_index.get(file_path, [])
        return [self._metadata.get(vid) for vid in vector_ids if vid in self._metadata]

    def delete_vector(self, vector_id: str) -> bool:
        """
        删除向量元数据

        Args:
            vector_id: 向量ID

        Returns:
            是否成功
        """
        if vector_id not in self._metadata:
            return False

        # 从文件索引中移除
        file_path = self._metadata[vector_id]["file_path"]
        if file_path in self._file_index:
            if vector_id in self._file_index[file_path]:
                self._file_index[file_path].remove(vector_id)
            if not self._file_index[file_path]:
                del self._file_index[file_path]

        # 删除元数据
        del self._metadata[vector_id]

        self._save_metadata()
        return True

    def delete_by_file(self, file_path: str) -> int:
        """
        删除文件的所有向量元数据

        Args:
            file_path: 文件路径

        Returns:
            删除的向量数量
        """
        vector_ids = self._file_index.get(file_path, [])
        count = len(vector_ids)

        for vector_id in vector_ids:
            if vector_id in self._metadata:
                del self._metadata[vector_id]

        del self._file_index[file_path]

        self._save_metadata()
        return count

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        file_count = len(self._file_index)
        vector_count = len(self._metadata)

        # 按分类统计
        categories: Dict[str, int] = {}
        for meta in self._metadata.values():
            category = meta.get("category", "其他")
            categories[category] = categories.get(category, 0) + 1

        return {
            "total_files": file_count,
            "total_vectors": vector_count,
            "categories": categories,
            "metadata_file": self.metadata_file
        }

    def clear(self) -> None:
        """清空所有元数据"""
        self._metadata.clear()
        self._file_index.clear()
        self._save_metadata()


# Chroma 向量存储
class ChromaStore(VectorStore):
    """Chroma 向量存储"""

    def __init__(self, config: Config):
        """
        初始化 Chroma 存储

        Args:
            config: 配置对象
        """
        self.config = config
        self.logger = setup_logger("chroma_store", config.log_dir, config.log_level)

        # 元数据存储
        self.metadata_store = MetadataStore(config)

        # Chroma 客户端
        self.collection_name = config.chroma_collection_name
        self.persist_directory = config.chroma_persist_dir
        ensure_directory(self.persist_directory)

        # 初始化集合
        self._collection = None
        self._init_collection()

    def _init_collection(self) -> None:
        """初始化 Chroma 集合"""
        try:
            import chromadb
            from chromadb.config import Settings

            # 创建持久化客户端
            client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            # 获取或创建集合
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "本地知识库向量库"}
            )

            self.logger.info(f"Chroma 集合初始化成功: {self.collection_name}")

        except ImportError:
            self.logger.error("Chroma 未安装，请运行: pip install chromadb")
            raise
        except Exception as e:
            self.logger.error(f"Chroma 初始化失败: {e}")
            raise

    def add_vectors(self, chunks: List[VectorChunk]) -> bool:
        """
        添加向量

        Args:
            chunks: 向量块列表

        Returns:
            是否成功
        """
        if not chunks:
            return False

        try:
            # 准备数据
            ids = [chunk.id for chunk in chunks]
            embeddings = [chunk.vector for chunk in chunks]
            documents = [chunk.chunk_text for chunk in chunks]

            # 构建元数据
            metadatas = []
            for chunk in chunks:
                metadata = {
                    "file_path": chunk.file_path,
                    "file_name": chunk.file_name,
                    "category": chunk.category,
                    "chunk_index": chunk.chunk_index,
                    **chunk.metadata
                }
                metadatas.append(metadata)

            # 批量添加
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )

            # 保存元数据
            self.metadata_store.add_vectors(chunks)

            self.logger.info(f"添加 {len(chunks)} 个向量到 Chroma")
            return True

        except Exception as e:
            self.logger.error(f"添加向量失败: {e}")
            return False

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        搜索向量

        Args:
            query_vector: 查询向量
            top_k: 返回结果数
            filters: 过滤条件

        Returns:
            搜索结果列表
        """
        try:
            # 构建查询条件
            where = None
            if filters:
                where = filters

            # 查询
            results = self._collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=where
            )

            # 解析结果
            search_results = []
            if results and results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    vector_id = results["ids"][0][i]
                    distance = results["distances"][0][i]
                    document = results["documents"][0][i]
                    metadata = results["metadatas"][0][i]

                    # 将距离转换为相似度
                    similarity = 1.0 / (1.0 + distance)

                    # 脱敏处理
                    chunk_text = sanitize_text(document) if self.config.enable_sanitization else document

                    search_results.append(SearchResult(
                        id=vector_id,
                        file_path=metadata.get("file_path", ""),
                        file_name=metadata.get("file_name", ""),
                        category=metadata.get("category", ""),
                        chunk_index=metadata.get("chunk_index", 0),
                        chunk_text=chunk_text,
                        similarity=similarity,
                        metadata=metadata
                    ))

            self.logger.debug(f"Chroma 搜索: 找到 {len(search_results)} 个结果")
            return search_results

        except Exception as e:
            self.logger.error(f"向量搜索失败: {e}")
            return []

    def delete_by_file(self, file_path: str) -> int:
        """
        删除指定文件的所有向量

        Args:
            file_path: 文件路径

        Returns:
            删除的向量数量
        """
        try:
            # 获取文件的所有向量ID
            vector_ids = self.metadata_store.get_vectors_by_file(file_path)
            ids = [v["id"] for v in vector_ids if v]

            if not ids:
                return 0

            # 从 Chroma 删除
            self._collection.delete(ids=ids)

            # 从元数据存储删除
            count = self.metadata_store.delete_by_file(file_path)

            self.logger.info(f"删除文件 {file_path} 的 {count} 个向量")
            return count

        except Exception as e:
            self.logger.error(f"删除向量失败: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        try:
            chroma_count = self._collection.count()
            metadata_stats = self.metadata_store.get_stats()

            return {
                "type": "chroma",
                "collection_name": self.collection_name,
                "total_vectors": chroma_count,
                "persist_directory": self.persist_directory,
                "metadata_stats": metadata_stats
            }

        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {"type": "chroma", "error": str(e)}

    def clear(self) -> bool:
        """
        清空向量库

        Returns:
            是否成功
        """
        try:
            # 删除集合
            self._collection.delete(where={})
            self.metadata_store.clear()

            self.logger.info("Chroma 向量库已清空")
            return True

        except Exception as e:
            self.logger.error(f"清空向量库失败: {e}")
            return False


# FAISS 向量存储
class FaissStore(VectorStore):
    """FAISS 向量存储"""

    def __init__(self, config: Config):
        """
        初始化 FAISS 存储

        Args:
            config: 配置对象
        """
        self.config = config
        self.logger = setup_logger("faiss_store", config.log_dir, config.log_level)

        # 元数据存储
        self.metadata_store = MetadataStore(config)

        # FAISS 配置
        self.vector_dim = config.vector_dim
        self.vector_db_dir = config.vector_db_dir
        ensure_directory(self.vector_db_dir)

        # FAISS 索引
        self._index = None
        self._init_index()

    def _init_index(self) -> None:
        """初始化 FAISS 索引"""
        try:
            import faiss
            import numpy as np

            # 根据配置创建索引
            index_type = self.config.get("storage.faiss.index_type", "flat")

            if index_type == "flat":
                # 精确搜索索引
                self._index = faiss.IndexFlatL2(self.vector_dim)
            elif index_type == "ivf":
                # IVF 索引
                nlist = self.config.get("storage.faiss.nlist", 100)
                quantizer = faiss.IndexFlatL2(self.vector_dim)
                self._index = faiss.IndexIVFFlat(quantizer, self.vector_dim, nlist)
            elif index_type == "hnsw":
                # HNSW 索引
                M = self.config.get("storage.faiss.M", 16)
                self._index = faiss.IndexHNSWFlat(self.vector_dim, M)
            else:
                self._index = faiss.IndexFlatL2(self.vector_dim)

            # 尝试加载已有索引
            self._load_index()

            self.logger.info(f"FAISS 索引初始化成功: {index_type}")

        except ImportError:
            self.logger.error("FAISS 未安装，请运行: pip install faiss-cpu")
            raise
        except Exception as e:
            self.logger.error(f"FAISS 初始化失败: {e}")
            raise

    def _load_index(self) -> None:
        """加载已有索引"""
        index_file = os.path.join(self.vector_db_dir, "faiss.index")
        if os.path.exists(index_file):
            try:
                import faiss
                self._index = faiss.read_index(index_file)
                self.logger.info(f"加载 FAISS 索引: {index_file}")
            except Exception as e:
                self.logger.warning(f"加载索引失败: {e}")

    def _save_index(self) -> None:
        """保存索引"""
        index_file = os.path.join(self.vector_db_dir, "faiss.index")
        try:
            import faiss
            faiss.write_index(self._index, index_file)
            self.logger.debug(f"保存 FAISS 索引: {index_file}")
        except Exception as e:
            self.logger.warning(f"保存索引失败: {e}")

    def add_vectors(self, chunks: List[VectorChunk]) -> bool:
        """
        添加向量

        Args:
            chunks: 向量块列表

        Returns:
            是否成功
        """
        if not chunks:
            return False

        try:
            import numpy as np
            import faiss

            # 准备向量
            vectors = np.array([chunk.vector for chunk in chunks], dtype=np.float32)

            # 添加到索引
            self._index.add(vectors)

            # 保存索引
            self._save_index()

            # 保存元数据
            self.metadata_store.add_vectors(chunks)

            self.logger.info(f"添加 {len(chunks)} 个向量到 FAISS")
            return True

        except Exception as e:
            self.logger.error(f"添加向量失败: {e}")
            return False

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        搜索向量

        Args:
            query_vector: 查询向量
            top_k: 返回结果数
            filters: 过滤条件

        Returns:
            搜索结果列表
        """
        try:
            import numpy as np

            # 准备查询向量
            query = np.array([query_vector], dtype=np.float32)

            # 搜索
            distances, indices = self._index.search(query, top_k)

            # 解析结果
            search_results = []
            all_metadata = self.metadata_store._metadata
            all_ids = list(all_metadata.keys())

            for i, idx in enumerate(indices[0]):
                if idx >= 0 and idx < len(all_ids):
                    vector_id = all_ids[idx]
                    distance = float(distances[0][i])
                    metadata = all_metadata[vector_id]

                    # 将距离转换为相似度
                    similarity = 1.0 / (1.0 + distance)

                    # 脱敏处理
                    chunk_text = sanitize_text(metadata["chunk_text"]) if self.config.enable_sanitization else metadata["chunk_text"]

                    search_results.append(SearchResult(
                        id=vector_id,
                        file_path=metadata["file_path"],
                        file_name=metadata["file_name"],
                        category=metadata["category"],
                        chunk_index=metadata["chunk_index"],
                        chunk_text=chunk_text,
                        similarity=similarity,
                        metadata=metadata.get("metadata", {})
                    ))

            self.logger.debug(f"FAISS 搜索: 找到 {len(search_results)} 个结果")
            return search_results

        except Exception as e:
            self.logger.error(f"向量搜索失败: {e}")
            return []

    def delete_by_file(self, file_path: str) -> int:
        """
        删除指定文件的所有向量

        注意: FAISS 不支持高效删除，建议使用 Chroma

        Args:
            file_path: 文件路径

        Returns:
            删除的向量数量
        """
        # FAISS 不支持高效删除，只能重建索引
        self.logger.warning("FAISS 不支持高效删除，需要重建索引")

        # 获取要删除的向量ID
        vector_ids = self.metadata_store.get_vectors_by_file(file_path)
        count = len([v for v in vector_ids if v])

        # 只从元数据中标记
        self.metadata_store.delete_by_file(file_path)

        self.logger.info(f"标记文件 {file_path} 的 {count} 个向量为已删除")
        return count

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        try:
            total_vectors = self._index.ntotal if self._index else 0
            metadata_stats = self.metadata_store.get_stats()

            return {
                "type": "faiss",
                "vector_dim": self.vector_dim,
                "total_vectors": total_vectors,
                "vector_db_dir": self.vector_db_dir,
                "metadata_stats": metadata_stats
            }

        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {"type": "faiss", "error": str(e)}

    def clear(self) -> bool:
        """
        清空向量库

        Returns:
            是否成功
        """
        try:
            # 重新初始化空索引
            self._init_index()
            self.metadata_store.clear()

            self.logger.info("FAISS 向量库已清空")
            return True

        except Exception as e:
            self.logger.error(f"清空向量库失败: {e}")
            return False


# 存储工厂
def create_vector_store(config: Config) -> VectorStore:
    """
    创建向量存储实例

    Args:
        config: 配置对象

    Returns:
        向量存储实例
    """
    store_type = config.store_type.lower()

    if store_type == "chroma":
        return ChromaStore(config)
    elif store_type == "faiss":
        return FaissStore(config)
    else:
        raise ValueError(f"不支持的存储类型: {store_type}")


__all__ = [
    # 元数据存储
    "MetadataStore",
    # 向量存储
    "ChromaStore",
    "FaissStore",
    # 工厂函数
    "create_vector_store",
]
