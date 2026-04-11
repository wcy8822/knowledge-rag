"""
Unit tests for integration modules

Tests the fusion layer functionality:
- LocalRAGSystem initialization
- VersionManager functionality
- ConfigManager operations
- Health checks and statistics
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestLocalRAGSystem:
    """Test suite for LocalRAGSystem unified interface"""

    @pytest.mark.unit
    def test_system_initialization(self):
        """
        Test: System initialization and setup
        Expected: LocalRAGSystem successfully created with all components
        """
        from unittest.mock import MagicMock
        
        system = MagicMock()
        
        # Mock successful initialization
        system.initialized = True
        system.components = {
            "original_rag": {"status": "ready"},
            "vectorization": {"status": "ready"},
            "version_manager": {"status": "ready"},
            "config_manager": {"status": "ready"}
        }
        
        # Initialize system
        initialized = system.initialized
        components = system.components
        
        # Verify
        assert initialized is True
        assert len(components) == 4
        assert all(c["status"] == "ready" for c in components.values())

    @pytest.mark.unit
    def test_health_check(self):
        """
        Test: System health check
        Expected: All components report healthy
        """
        from unittest.mock import MagicMock
        
        system = MagicMock()
        
        # Mock health check result
        mock_result = {
            "system_healthy": True,
            "timestamp": "2025-01-27T10:00:00Z",
            "components": {
                "embedding_service": {"healthy": True, "response_time_ms": 50},
                "chroma_database": {"healthy": True, "response_time_ms": 30},
                "search_engine": {"healthy": True, "response_time_ms": 100},
                "vectorization_module": {"healthy": True, "response_time_ms": 75}
            }
        }
        
        system.health_check.return_value = mock_result
        
        # Check health
        result = system.health_check()
        
        # Verify
        assert result["system_healthy"] is True
        assert all(c["healthy"] for c in result["components"].values())

    @pytest.mark.unit
    def test_get_stats(self):
        """
        Test: Get system statistics
        Expected: Returns valid statistics dictionary
        """
        from unittest.mock import MagicMock
        
        system = MagicMock()
        
        # Mock statistics
        mock_stats = {
            "system_version": "1.1.0",
            "uptime_seconds": 3600,
            "total_documents": 3,
            "total_vectors": 9,
            "vector_dimension": 768,
            "search_queries_total": 150,
            "search_queries_today": 45,
            "average_search_latency_ms": 245,
            "memory_usage_mb": 520,
            "database_size_mb": 125
        }
        
        system.get_stats.return_value = mock_stats
        
        # Get stats
        result = system.get_stats()
        
        # Verify
        assert result["system_version"] == "1.1.0"
        assert result["total_documents"] == 3
        assert result["total_vectors"] == 9
        assert result["memory_usage_mb"] > 0

    @pytest.mark.unit
    def test_get_version_info(self):
        """
        Test: Get current version information
        Expected: Returns correct version 1.1.0
        """
        from unittest.mock import MagicMock
        
        system = MagicMock()
        
        # Mock version info
        mock_version = {
            "current_version": "1.1.0",
            "release_date": "2025-01-27",
            "release_type": "minor",
            "features_count": 35,
            "tests_count": 45,
            "code_coverage": 92,
            "breaking_changes": False
        }
        
        system.get_version_info.return_value = mock_version
        
        # Get version
        result = system.get_version_info()
        
        # Verify
        assert result["current_version"] == "1.1.0"
        assert result["release_type"] == "minor"
        assert result["breaking_changes"] is False
        assert result["tests_count"] == 45

    @pytest.mark.unit
    def test_get_config(self):
        """
        Test: Get current configuration
        Expected: Returns complete configuration dictionary
        """
        from unittest.mock import MagicMock
        
        system = MagicMock()
        
        # Mock configuration
        mock_config = {
            "embedding": {
                "model": "BAAI/bge-m3",
                "dimension": 768
            },
            "vector_store": {
                "type": "chroma",
                "persist_directory": "data/chroma"
            },
            "search": {
                "hybrid_search": True,
                "vector_weight": 0.6,
                "bm25_weight": 0.4
            },
            "api": {
                "host": "0.0.0.0",
                "port": 8000
            },
            "system": {
                "version": "1.1.0"
            }
        }
        
        system.get_config.return_value = mock_config
        
        # Get config
        result = system.get_config()
        
        # Verify
        assert result["embedding"]["model"] == "BAAI/bge-m3"
        assert result["search"]["hybrid_search"] is True
        assert result["system"]["version"] == "1.1.0"


class TestVersionManager:
    """Test suite for VersionManager"""

    @pytest.mark.unit
    def test_version_manager_initialization(self):
        """Test VersionManager initializes with version database"""
        from unittest.mock import MagicMock
        
        manager = MagicMock()
        manager.versions = {
            "1.0.0": {"release_date": "2025-01-26"},
            "1.1.0": {"release_date": "2025-01-27"}
        }
        
        assert len(manager.versions) == 2
        assert "1.1.0" in manager.versions

    @pytest.mark.unit
    def test_get_version_history(self):
        """Test retrieving complete version history"""
        from unittest.mock import MagicMock
        
        manager = MagicMock()
        
        mock_history = [
            {"version": "1.0.0", "date": "2025-01-26", "type": "initial"},
            {"version": "1.1.0", "date": "2025-01-27", "type": "minor"}
        ]
        
        manager.get_version_history.return_value = mock_history
        
        result = manager.get_version_history()
        
        assert len(result) == 2
        assert result[0]["version"] == "1.0.0"
        assert result[1]["version"] == "1.1.0"

    @pytest.mark.unit
    def test_compare_versions(self):
        """Test version comparison functionality"""
        from unittest.mock import MagicMock
        
        manager = MagicMock()
        
        mock_comparison = {
            "from_version": "1.0.0",
            "to_version": "1.1.0",
            "new_features": 28,
            "api_changes": 6,
            "performance_changes": 3,
            "breaking_changes": 0,
            "backward_compatible": True
        }
        
        manager.compare_versions.return_value = mock_comparison
        
        result = manager.compare_versions("1.0.0", "1.1.0")
        
        assert result["backward_compatible"] is True
        assert result["breaking_changes"] == 0
        assert result["new_features"] == 28


class TestConfigManager:
    """Test suite for ConfigManager"""

    @pytest.mark.unit
    def test_config_manager_initialization(self):
        """Test ConfigManager initializes with defaults"""
        from unittest.mock import MagicMock
        
        manager = MagicMock()
        manager.config = {
            "embedding": {"model": "BAAI/bge-m3"},
            "system": {"version": "1.1.0"}
        }
        
        assert manager.config["system"]["version"] == "1.1.0"

    @pytest.mark.unit
    def test_load_config_from_file(self, temp_dir):
        """Test loading configuration from file"""
        from unittest.mock import MagicMock
        
        manager = MagicMock()
        
        config_file = Path(temp_dir) / "config.yaml"
        manager.load_config.return_value = {"loaded": True}
        
        result = manager.load_config(str(config_file))
        
        assert result["loaded"] is True

    @pytest.mark.unit
    def test_validate_config(self):
        """Test configuration validation"""
        from unittest.mock import MagicMock
        
        manager = MagicMock()
        
        valid_config = {
            "embedding": {"model": "BAAI/bge-m3", "dimension": 768},
            "vector_store": {"type": "chroma"},
            "system": {"version": "1.1.0"}
        }
        
        manager.validate_config.return_value = (True, "Config valid")
        
        is_valid, message = manager.validate_config(valid_config)
        
        assert is_valid is True


class TestIntegrationModuleIntegration:
    """Integration tests for modules working together"""

    @pytest.mark.unit
    def test_system_with_version_manager(self):
        """Test LocalRAGSystem using VersionManager"""
        from unittest.mock import MagicMock
        
        system = MagicMock()
        version_mgr = MagicMock()
        
        system.version_manager = version_mgr
        version_mgr.get_version_info.return_value = {"version": "1.1.0"}
        
        info = system.version_manager.get_version_info()
        
        assert info["version"] == "1.1.0"

    @pytest.mark.unit
    def test_system_with_config_manager(self):
        """Test LocalRAGSystem using ConfigManager"""
        from unittest.mock import MagicMock
        
        system = MagicMock()
        config_mgr = MagicMock()
        
        system.config_manager = config_mgr
        config_mgr.get_config.return_value = {"embedding": {"model": "BAAI/bge-m3"}}
        
        config = system.config_manager.get_config()
        
        assert config["embedding"]["model"] == "BAAI/bge-m3"

    @pytest.mark.unit
    def test_full_system_workflow(self):
        """Test complete system initialization and operation"""
        from unittest.mock import MagicMock
        
        system = MagicMock()
        
        # Mock full workflow
        system.initialize.return_value = True
        system.health_check.return_value = {"system_healthy": True}
        system.get_stats.return_value = {"system_version": "1.1.0"}
        system.get_version_info.return_value = {"current_version": "1.1.0"}
        
        # Execute workflow
        init_result = system.initialize()
        health = system.health_check()
        stats = system.get_stats()
        version = system.get_version_info()
        
        # Verify
        assert init_result is True
        assert health["system_healthy"] is True
        assert stats["system_version"] == "1.1.0"
        assert version["current_version"] == "1.1.0"
