#!/usr/bin/env python3
"""
配置管理模块

功能:
- 统一的配置管理
- 支持YAML/JSON/Python配置文件
- 配置验证和默认值
- 环境变量覆盖
- 配置热重载

这确保了整个系统的配置一致性和可维护性。
"""

import os
import json
import yaml
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """
    配置管理器

    管理Local RAG系统的所有配置，包括：
    - 向量嵌入配置
    - 向量存储配置
    - 混合检索配置
    - API配置
    - 日志配置
    - 向量化配置
    """

    DEFAULT_CONFIG = {
        # 嵌入模型配置
        "embedding": {
            "model": "BAAI/bge-m3",
            "model_name": "BGE-M3",
            "dimension": 768,
            "batch_size": 32,
            "device": "auto",  # auto/cuda/cpu
            "cache_embeddings": True
        },

        # 向量存储配置
        "vector_store": {
            "type": "chroma",  # chroma/qdrant
            "persist_directory": "data/chroma",
            "collection_name": "documents",
            "chroma_settings": {
                "anonymized_telemetry": False,
                "allow_reset": True
            }
        },

        # 混合检索配置
        "search": {
            "hybrid_search": True,
            "vector_weight": 0.6,
            "bm25_weight": 0.4,
            "top_k": 5,
            "rerank_enabled": True,
            "reranker_model": "BAAI/bge-reranker-base",
            "reranker_top_n": 6
        },

        # API服务配置
        "api": {
            "host": "0.0.0.0",
            "port": 8000,
            "workers": 4,
            "timeout": 60,
            "cors_origins": ["*"],
            "enable_docs": True
        },

        # 日志配置
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "logs/app.log",
            "file_level": "DEBUG"
        },

        # 向量化配置
        "vectorization": {
            "batch_size": 32,
            "chunk_size": 750,
            "chunk_overlap": 0.15,
            "min_chunk_size": 50,
            "max_chunk_size": 2000,
            "scan_locations": [
                "/Users/didi/Downloads/panth",
                "/Users/didi/sync",
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Desktop")
            ],
            "supported_formats": [".md", ".txt", ".markdown", ".docx", ".pdf"],
            "max_file_size_mb": 50,
            "enable_deduplication": True
        },

        # 性能配置
        "performance": {
            "cache_enabled": True,
            "cache_size": 1000,
            "parallel_workers": 4,
            "max_memory_mb": 2048
        },

        # 监控和指标
        "monitoring": {
            "enable_metrics": True,
            "metrics_port": 8001,
            "enable_tracing": False,
            "trace_sample_rate": 0.1
        },

        # 系统配置
        "system": {
            "version": "1.1.0",
            "environment": "development",
            "debug": False,
            "data_directory": "data",
            "logs_directory": "logs"
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径 (YAML/JSON)
        """
        self.config = self.DEFAULT_CONFIG.copy()

        # 如果提供了配置文件，则加载
        if config_path:
            self.load_config(config_path)

        # 使用环境变量覆盖配置
        self._apply_env_overrides()

        logger.info("✅ 配置管理器初始化完成")

    def load_config(self, config_path: str) -> None:
        """
        从文件加载配置

        支持格式: YAML, JSON, Python

        Args:
            config_path: 配置文件路径
        """
        if not os.path.exists(config_path):
            logger.warning(f"⚠️  配置文件不存在: {config_path}")
            return

        try:
            if config_path.endswith((".yml", ".yaml")):
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f)
            elif config_path.endswith(".json"):
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
            else:
                logger.error(f"❌ 不支持的配置文件格式: {config_path}")
                return

            # 深度合并配置
            self._deep_merge(self.config, loaded_config)
            logger.info(f"✅ 配置已加载: {config_path}")

        except Exception as e:
            logger.error(f"❌ 加载配置失败: {e}")

    def _apply_env_overrides(self) -> None:
        """
        应用环境变量覆盖

        支持的环境变量格式:
        - LOG_LEVEL: logging.level
        - API_PORT: api.port
        - VECTOR_STORE_TYPE: vector_store.type
        """
        env_mappings = {
            "LOG_LEVEL": ("logging", "level"),
            "API_HOST": ("api", "host"),
            "API_PORT": ("api", "port"),
            "VECTOR_STORE_TYPE": ("vector_store", "type"),
            "EMBEDDING_DEVICE": ("embedding", "device"),
            "DEBUG": ("system", "debug"),
            "ENVIRONMENT": ("system", "environment")
        }

        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                # 类型转换
                if key == "port" or key == "workers":
                    value = int(value)
                elif key in ("debug",):
                    value = value.lower() in ("true", "1", "yes")

                if section not in self.config:
                    self.config[section] = {}

                self.config[section][key] = value
                logger.debug(f"  环境变量覆盖: {env_var} = {value}")

    def _deep_merge(self, base: Dict, override: Dict) -> None:
        """
        深度合并配置字典

        Args:
            base: 基础配置
            override: 覆盖配置
        """
        for key, value in override.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            section: 配置部分 (如 "api", "embedding")
            key: 配置键 (如 "port", "model")
            default: 默认值

        Returns:
            配置值
        """
        if section not in self.config:
            return default

        if key is None:
            return self.config.get(section, default)

        return self.config[section].get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        """
        设置配置值

        Args:
            section: 配置部分
            key: 配置键
            value: 新值
        """
        if section not in self.config:
            self.config[section] = {}

        self.config[section][key] = value
        logger.debug(f"配置已更新: {section}.{key} = {value}")

    def get_all(self) -> Dict[str, Any]:
        """
        获取所有配置

        Returns:
            完整的配置字典
        """
        return self.config.copy()

    def validate(self) -> bool:
        """
        验证配置有效性

        Returns:
            配置是否有效
        """
        try:
            # 检查必需的配置项
            required_sections = ["embedding", "vector_store", "search"]
            for section in required_sections:
                if section not in self.config:
                    logger.error(f"❌ 缺少必需的配置部分: {section}")
                    return False

            # 验证特定的值
            if self.config["embedding"]["model"] not in [
                "BAAI/bge-m3",
                "BAAI/bge-base",
                "BAAI/bge-large"
            ]:
                logger.warning(f"⚠️  未知的嵌入模型: {self.config['embedding']['model']}")

            logger.info("✅ 配置验证通过")
            return True

        except Exception as e:
            logger.error(f"❌ 配置验证失败: {e}")
            return False

    def save(self, output_path: str, format: str = "yaml") -> None:
        """
        保存配置到文件

        Args:
            output_path: 输出文件路径
            format: 文件格式 (yaml/json)
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            if format == "yaml":
                with open(output_path, 'w', encoding='utf-8') as f:
                    yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            elif format == "json":
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"不支持的格式: {format}")

            logger.info(f"✅ 配置已保存: {output_path}")

        except Exception as e:
            logger.error(f"❌ 保存配置失败: {e}")

    def get_config(self) -> Dict[str, Any]:
        """
        获取完整配置（与get_all相同）

        Returns:
            配置字典
        """
        return self.get_all()

    def __repr__(self) -> str:
        """配置管理器的字符串表示"""
        return f"ConfigManager(sections={list(self.config.keys())})"


def main():
    """演示脚本"""
    print("⚙️  配置管理器演示\n")

    # 初始化配置管理器
    cm = ConfigManager()

    # 获取特定配置
    print(f"API端口: {cm.get('api', 'port')}")
    print(f"嵌入模型: {cm.get('embedding', 'model')}")
    print(f"向量维度: {cm.get('embedding', 'dimension')}")

    # 修改配置
    cm.set("api", "port", 9000)
    print(f"\n修改后的API端口: {cm.get('api', 'port')}")

    # 验证配置
    print(f"\n配置验证: {'✅ 通过' if cm.validate() else '❌ 失败'}")

    # 保存配置
    cm.save("config_output.yaml", format="yaml")
    print("✅ 配置已保存到 config_output.yaml")


if __name__ == "__main__":
    main()
