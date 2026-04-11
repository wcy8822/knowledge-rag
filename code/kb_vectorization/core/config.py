"""
本地知识库全量向量化自动化系统 - 配置加载模块
版本: v1.0
日期: 2026-03-01
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


class Config:
    """配置管理类"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置

        Args:
            config_path: 配置文件路径，默认为 config/config.yaml
        """
        self._config: Dict[str, Any] = {}
        self._config_path = config_path

        if config_path and os.path.exists(config_path):
            self._load_from_file(config_path)
        else:
            self._load_default()

    def _load_from_file(self, path: str) -> None:
        """从文件加载配置"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"加载配置文件失败: {e}")

    def _load_default(self) -> None:
        """加载默认配置"""
        self._config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "system": {
                "name": "本地知识库向量化系统",
                "version": "1.0.0",
                "debug": False,
                "memory_limit": 12,
                "work_dir": str(Path(__file__).parent.parent)
            },
            "scan": {
                "directories": [],
                "exclude_dirs": [".git", "node_modules", "__pycache__"],
                "file_types": [".md", ".sql", ".py", ".js", ".java"],
                "max_file_size_mb": 50,
                "recursive": True
            },
            "categories": {
                "news": {"name": "资讯", "patterns": ["资讯", "news", "report"]},
                "merchant": {"name": "商户画像", "patterns": ["商户", "customer", "profile"]},
                "config": {"name": "技术配置", "patterns": ["config", "setting", "配置"]},
                "report": {"name": "项目汇报", "patterns": ["汇报", "report", "总结"]},
                "mapping": {"name": "数据表映射", "patterns": ["mapping", "table", "schema"]},
                "sql_debug": {"name": "SQL 调试", "patterns": ["sql", "debug", "query"]},
                "default": "其他"
            },
            "vectorize": {
                "batch_size": 500,
                "mvp_batch_size": 5,
                "vector_dim": 384,
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "min_chunk_size": 100,
                "max_chunks_per_file": 1000,
                "retry_count": 3,
                "retry_delay": 1,
                "md_preprocessing": {
                    "remove_md_syntax": True,
                    "merge_empty_lines": True,
                    "split_by_paragraph": True,
                    "remove_code_block_syntax": True,
                    "remove_html_tags": True,
                    "process_tables": True,
                    "preserve_special_words": ["SKU", "GMV", "DAU", "MAU", "ROI"]
                }
            },
            "storage": {
                "type": "chroma",
                "vector_db_dir": "./data/vector_db",
                "chroma": {
                    "collection_name": "kb_vectors",
                    "persist_directory": "./data/vector_db/chroma",
                    "persist": True
                },
                "faiss": {
                    "index_type": "hnsw",
                    "nlist": 100,
                    "M": 16,
                    "efConstruction": 200
                },
                "metadata": {
                    "file": "./data/vector_db/metadata.json",
                    "auto_backup": True,
                    "backup_dir": "./data/vector_db/backup",
                    "backup_count": 5
                }
            },
            "retrieval": {
                "default_top_k": 5,
                "max_top_k": 50,
                "hybrid_weights": {"keyword": 0.3, "vector": 0.7},
                "preview_length": 200,
                "enable_sanitization": True,
                "sanitization_mode": "moderate"
            },
            "api": {
                "host": "127.0.0.1",
                "port": 8000,
                "prefix": "/api/v1",
                "timeout": 60,
                "max_concurrent": 10,
                "rate_limit": 100,
                "enable_cors": False,
                "log_requests": True
            },
            "monitor": {
                "enable_watchdog": True,
                "poll_interval": 1,
                "enable_schedule": True,
                "schedule": {
                    "full_validation_time": "02:00",
                    "cleanup_time": "02:30",
                    "report_time": "08:00"
                },
                "event_delay": 2
            },
            "logging": {
                "level": "INFO",
                "dir": "./logs",
                "retention_days": 30,
                "max_file_size_mb": 100,
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "date_format": "%Y-%m-%d %H:%M:%S",
                "console_output": True,
                "file_output": True,
                "json_format": False
            },
            "stats": {
                "dir": "./data/stats",
                "file_list": "file_list.csv",
                "processing_stats": "processing_stats.json",
                "daily_reports_dir": "daily_reports",
                "realtime": True
            },
            "security": {
                "localhost_only": True,
                "access_token": "",
                "enable_ip_whitelist": True,
                "ip_whitelist": ["127.0.0.1", "::1"],
                "data_sanitization": {
                    "enabled": True,
                    "patterns": [
                        {"name": "手机号", "pattern": r"\d{11}"},
                        {"name": "银行卡号", "pattern": r"\d{15,19}"},
                        {"name": "身份证号", "pattern": r"\d{17}[\dXx]"}
                    ]
                }
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键，支持点分隔符，如 'system.name'
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def set(self, key: str, value: Any) -> None:
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def save(self, path: Optional[str] = None) -> None:
        """
        保存配置到文件

        Args:
            path: 保存路径，默认使用原路径
        """
        save_path = path or self._config_path
        if not save_path:
            raise RuntimeError("未指定保存路径")

        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        with open(save_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(self._config, f, allow_unicode=True, default_flow_style=False)

    # 系统配置
    @property
    def system_name(self) -> str:
        return self.get("system.name", "本地知识库向量化系统")

    @property
    def system_version(self) -> str:
        return self.get("system.version", "1.0.0")

    @property
    def debug(self) -> bool:
        return self.get("system.debug", False)

    @property
    def memory_limit(self) -> int:
        return self.get("system.memory_limit", 12)

    @property
    def work_dir(self) -> str:
        return self.get("system.work_dir", str(Path(__file__).parent.parent))

    # 扫描配置
    def get_scan_dirs(self) -> List[str]:
        return self.get("scan.directories", [])

    def get_exclude_dirs(self) -> List[str]:
        return self.get("scan.exclude_dirs", [])

    def get_file_types(self) -> List[str]:
        return self.get("scan.file_types", [".md", ".sql"])

    def get_max_file_size(self) -> int:
        return self.get("scan.max_file_size_mb", 50) * 1024 * 1024

    def is_recursive_scan(self) -> bool:
        return self.get("scan.recursive", True)

    # 分类配置
    def get_category_patterns(self) -> Dict[str, Dict[str, Any]]:
        """获取分类规则"""
        patterns = {}
        for key, value in self._config.get("categories", {}).items():
            if isinstance(value, dict) and "patterns" in value:
                patterns[key] = value
        return patterns

    def classify(self, file_path: str) -> str:
        """
        根据文件路径分类

        Args:
            file_path: 文件路径

        Returns:
            分类名称
        """
        path_lower = file_path.lower()

        for key, config in self.get_category_patterns().items():
            patterns = config.get("patterns", [])
            for pattern in patterns:
                if pattern.lower() in path_lower:
                    return config.get("name", "其他")

        return self.get("categories.default", "其他")

    # 向量化配置
    @property
    def batch_size(self) -> int:
        return self.get("vectorize.batch_size", 500)

    @property
    def mvp_batch_size(self) -> int:
        return self.get("vectorize.mvp_batch_size", 5)

    @property
    def vector_dim(self) -> int:
        return self.get("vectorize.vector_dim", 384)

    @property
    def chunk_size(self) -> int:
        return self.get("vectorize.chunk_size", 1000)

    @property
    def chunk_overlap(self) -> int:
        return self.get("vectorize.chunk_overlap", 200)

    @property
    def min_chunk_size(self) -> int:
        return self.get("vectorize.min_chunk_size", 100)

    @property
    def max_chunks_per_file(self) -> int:
        return self.get("vectorize.max_chunks_per_file", 1000)

    @property
    def retry_count(self) -> int:
        return self.get("vectorize.retry_count", 3)

    @property
    def retry_delay(self) -> float:
        return self.get("vectorize.retry_delay", 1)

    # 存储配置
    @property
    def store_type(self) -> str:
        return self.get("storage.type", "chroma")

    @property
    def vector_db_dir(self) -> str:
        return self.get("storage.vector_db_dir", "./data/vector_db")

    @property
    def chroma_collection_name(self) -> str:
        return self.get("storage.chroma.collection_name", "kb_vectors")

    @property
    def chroma_persist_dir(self) -> str:
        return self.get("storage.chroma.persist_directory", "./data/vector_db/chroma")

    # API 配置
    @property
    def api_host(self) -> str:
        return self.get("api.host", "127.0.0.1")

    @property
    def api_port(self) -> int:
        return self.get("api.port", 8000)

    @property
    def api_prefix(self) -> str:
        return self.get("api.prefix", "/api/v1")

    # 日志配置
    @property
    def log_level(self) -> str:
        return self.get("logging.level", "INFO")

    @property
    def log_dir(self) -> str:
        return self.get("logging.dir", "./logs")

    # 检索配置
    @property
    def default_top_k(self) -> int:
        return self.get("retrieval.default_top_k", 5)

    @property
    def max_top_k(self) -> int:
        return self.get("retrieval.max_top_k", 50)

    @property
    def enable_sanitization(self) -> bool:
        return self.get("retrieval.enable_sanitization", True)

    # 安全配置
    @property
    def localhost_only(self) -> bool:
        return self.get("security.localhost_only", True)

    @property
    def ip_whitelist(self) -> List[str]:
        return self.get("security.ip_whitelist", ["127.0.0.1"])

    def __repr__(self) -> str:
        return f"Config(work_dir='{self.work_dir}', store_type='{self.store_type}')"
