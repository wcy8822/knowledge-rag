import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    """应用配置类"""
    
    # 应用基础配置
    app_name: str = Field(default="Local RAG System", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # 数据目录配置
    data_base_dir: str = Field(default="./data", env="DATA_BASE_DIR")
    chroma_dir: str = Field(default="./data/chroma", env="CHROMA_DIR")
    qdrant_dir: str = Field(default="./data/qdrant", env="QDRANT_DIR")
    metadata_dir: str = Field(default="./data/metadata", env="METADATA_DIR")
    upload_dir: str = Field(default="./data/uploads", env="UPLOAD_DIR")
    
    # 向量数据库配置
    vector_db_provider: str = Field(default="chroma", env="VECTOR_DB_PROVIDER")
    chroma_host: str = Field(default="localhost", env="CHROMA_HOST")
    chroma_port: int = Field(default=8001, env="CHROMA_PORT")
    qdrant_host: str = Field(default="localhost", env="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, env="QDRANT_PORT")
    
    # 嵌入模型配置
    embedding_provider: str = Field(default="local", env="EMBEDDING_PROVIDER")
    embedding_model: str = Field(default="BAAI/bge-m3", env="EMBEDDING_MODEL")
    embedding_device: str = Field(default="cpu", env="EMBEDDING_DEVICE")
    embedding_batch_size: int = Field(default=32, env="EMBEDDING_BATCH_SIZE")
    
    # 安全配置
    allow_cloud_embedding: bool = Field(default=False, env="ALLOW_CLOUD_EMBEDDING")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    
    # Redis配置
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # 日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: Optional[str] = Field(default=None, env="LOG_FILE")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.settings = Settings()
        self.yaml_config: Dict[str, Any] = {}
        
        if config_path:
            self._load_yaml_config(config_path)
        elif os.path.exists("config.yaml"):
            self._load_yaml_config("config.yaml")
    
    def _load_yaml_config(self, config_path: str):
        """加载YAML配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.yaml_config = yaml.safe_load(f)
        except Exception as e:
            print(f"Failed to load config from {config_path}: {e}")
            self.yaml_config = {}
    
    def get(self, key: str, default=None):
        """获取配置值，优先使用环境变量，然后是YAML配置"""
        # 首先检查环境变量
        env_key = key.upper()
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value
        
        # 然后检查YAML配置
        keys = key.split('.')
        value = self.yaml_config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def ensure_directories(self):
        """确保所有必要的目录存在"""
        directories = [
            self.settings.data_base_dir,
            self.settings.chroma_dir,
            self.settings.qdrant_dir,
            self.settings.metadata_dir,
            self.settings.upload_dir,
            os.path.join(self.settings.data_base_dir, "logs")
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

# 全局配置实例
config = ConfigManager()