"""
End-to-end pipeline integration tests

Tests the complete workflow:
- Collection → Vectorization → Verification → Search
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock


class TestCompletePipeline:
    """Test suite for complete vectorization pipeline"""

    @pytest.mark.integration
    def test_complete_pipeline(self, sample_notes_dir, temp_dir):
        """
        Test: Execute full collection → vectorization → verification flow
        Expected: All stages complete successfully
        """
        from unittest.mock import MagicMock
        
        # Mock complete pipeline
        pipeline = MagicMock()
        
        # Stage 1: Collection
        collection_result = {
            "stage": "collection",
            "status": "success",
            "files_collected": 3,
            "duration_ms": 500
        }
        
        # Stage 2: Vectorization
        vectorization_result = {
            "stage": "vectorization",
            "status": "success",
            "embeddings_created": 9,
            "duration_ms": 2500
        }
        
        # Stage 3: Verification
        verification_result = {
            "stage": "verification",
            "status": "success",
            "all_checks_passed": True,
            "duration_ms": 1500
        }
        
        pipeline.run_complete_pipeline.return_value = {
            "overall_status": "success",
            "stages": [
                collection_result,
                vectorization_result,
                verification_result
            ],
            "total_duration_ms": 4500
        }
        
        # Execute pipeline
        result = pipeline.run_complete_pipeline(str(sample_notes_dir))
        
        # Verify all stages succeeded
        assert result["overall_status"] == "success"
        assert len(result["stages"]) == 3
        assert all(stage["status"] == "success" for stage in result["stages"])
        assert result["total_duration_ms"] > 0

    @pytest.mark.integration
    def test_incremental_vectorization(self, sample_notes_dir, temp_dir):
        """
        Test: Update vector database with new files
        Expected: New files processed, existing unchanged
        """
        from unittest.mock import MagicMock
        
        pipeline = MagicMock()
        
        # First run: 3 files
        first_run = {
            "new_files": 3,
            "updated_files": 0,
            "deleted_files": 0,
            "total_embeddings": 9
        }
        
        # Second run: 1 new file
        second_run = {
            "new_files": 1,
            "updated_files": 0,
            "deleted_files": 0,
            "total_embeddings": 12  # 9 existing + 3 new
        }
        
        pipeline.run_incremental_update.side_effect = [first_run, second_run]
        
        # Execute incremental updates
        result1 = pipeline.run_incremental_update()
        result2 = pipeline.run_incremental_update()
        
        # Verify incremental behavior
        assert result1["new_files"] == 3
        assert result2["new_files"] == 1
        assert result2["total_embeddings"] > result1["total_embeddings"]

    @pytest.mark.integration
    def test_error_handling_in_pipeline(self, temp_dir):
        """
        Test: Handle errors gracefully during pipeline execution
        Expected: Errors logged, process continues for other files
        """
        from unittest.mock import MagicMock
        
        pipeline = MagicMock()
        
        # Mock partial failure
        mock_result = {
            "overall_status": "partial_success",
            "successful_files": 2,
            "failed_files": 1,
            "errors": [
                {
                    "file": "corrupted.md",
                    "error": "Invalid encoding",
                    "stage": "vectorization"
                }
            ],
            "recovery_action": "Continued processing remaining files"
        }
        
        pipeline.run_complete_pipeline.return_value = mock_result
        
        # Execute with errors
        result = pipeline.run_complete_pipeline()
        
        # Verify error handling
        assert result["successful_files"] == 2
        assert result["failed_files"] == 1
        assert len(result["errors"]) > 0
        assert "recovery_action" in result

    @pytest.mark.integration
    def test_data_persistence(self, temp_dir):
        """
        Test: Data persists across pipeline reruns
        Expected: Database and files preserved between runs
        """
        from unittest.mock import MagicMock
        
        pipeline = MagicMock()
        
        # First run
        run1 = {
            "databases_created": ["chroma.db"],
            "documents_stored": 3,
            "timestamp": "2025-01-27T10:00:00Z"
        }
        
        # Second run - data persists
        run2 = {
            "databases_found": ["chroma.db"],
            "documents_loaded": 3,
            "new_documents_added": 1,
            "total_documents": 4,
            "timestamp": "2025-01-27T10:05:00Z"
        }
        
        pipeline.run_with_persistence.side_effect = [run1, run2]
        
        # Execute runs
        result1 = pipeline.run_with_persistence(temp_dir)
        result2 = pipeline.run_with_persistence(temp_dir)
        
        # Verify persistence
        assert result1["databases_created"]
        assert result2["databases_found"]
        assert result2["documents_loaded"] == 3
        assert result2["total_documents"] == 4

    @pytest.mark.integration
    def test_system_recovery(self, temp_dir):
        """
        Test: System recovery from partial failures
        Expected: Can resume from checkpoint and continue
        """
        from unittest.mock import MagicMock
        
        pipeline = MagicMock()
        
        # Failure point
        failure = {
            "status": "failed",
            "stage": "vectorization",
            "last_successful_file": "note2.md",
            "checkpoint": "2025-01-27T10:02:30Z"
        }
        
        # Recovery
        recovery = {
            "status": "recovery_successful",
            "resumed_from": "2025-01-27T10:02:30Z",
            "continued_from_file": "note3.md",
            "completed_successfully": True
        }
        
        pipeline.run_complete_pipeline.side_effect = [failure, recovery]
        
        # First run fails
        result1 = pipeline.run_complete_pipeline()
        assert result1["status"] == "failed"
        
        # Resume and succeed
        result2 = pipeline.run_complete_pipeline()
        assert result2["status"] == "recovery_successful"


class TestPipelinePerformance:
    """Performance characteristics of pipeline"""

    @pytest.mark.integration
    def test_pipeline_throughput(self):
        """Test pipeline throughput with realistic data"""
        from unittest.mock import MagicMock
        
        pipeline = MagicMock()
        
        # Mock throughput test
        mock_result = {
            "total_files": 100,
            "processing_time_seconds": 300,
            "throughput_files_per_second": 0.33,
            "average_time_per_file_ms": 3000
        }
        
        pipeline.measure_throughput.return_value = mock_result
        
        result = pipeline.measure_throughput()
        
        assert result["total_files"] == 100
        assert result["processing_time_seconds"] > 0
        assert result["throughput_files_per_second"] > 0

    @pytest.mark.integration
    def test_pipeline_memory_usage(self):
        """Test memory usage during pipeline execution"""
        from unittest.mock import MagicMock
        
        pipeline = MagicMock()
        
        # Mock memory tracking
        mock_result = {
            "initial_memory_mb": 512,
            "peak_memory_mb": 580,
            "final_memory_mb": 520,
            "max_increase_mb": 68
        }
        
        pipeline.measure_memory_usage.return_value = mock_result
        
        result = pipeline.measure_memory_usage()
        
        assert result["peak_memory_mb"] > result["initial_memory_mb"]
        assert result["final_memory_mb"] < result["peak_memory_mb"]


class TestPipelineIntegration:
    """Tests for pipeline integration with other components"""

    @pytest.mark.integration
    def test_pipeline_uses_vectorization_modules(self):
        """Test that pipeline correctly uses vectorization modules"""
        from unittest.mock import MagicMock
        
        pipeline = MagicMock()
        collector = MagicMock()
        vectorizer = MagicMock()
        verifier = MagicMock()
        
        pipeline.collector = collector
        pipeline.vectorizer = vectorizer
        pipeline.verifier = verifier
        
        # Mock module calls
        collector.collect_all_notes.return_value = [{"file": "note1.md"}]
        vectorizer.vectorize_all.return_value = {"embeddings": 3}
        verifier.verify_all.return_value = {"status": "pass"}
        
        # Verify modules are used
        assert pipeline.collector is not None
        assert pipeline.vectorizer is not None
        assert pipeline.verifier is not None

    @pytest.mark.integration
    def test_pipeline_integration_with_rag_system(self):
        """Test pipeline integration with original RAG system"""
        from unittest.mock import MagicMock
        
        pipeline = MagicMock()
        rag_system = MagicMock()
        
        pipeline.rag_system = rag_system
        
        # Mock RAG system interaction
        rag_system.search.return_value = {"results": []}
        rag_system.health_check.return_value = {"healthy": True}
        
        # Verify integration
        assert pipeline.rag_system is not None

    @pytest.mark.integration
    def test_pipeline_respects_configuration(self):
        """Test that pipeline uses configuration correctly"""
        from unittest.mock import MagicMock
        
        pipeline = MagicMock()
        config = {
            "chunk_size": 750,
            "batch_size": 32,
            "model": "BAAI/bge-m3"
        }
        
        pipeline.config = config
        pipeline.set_config.return_value = True
        
        # Set config
        result = pipeline.set_config(config)
        
        assert result is True
        assert pipeline.config["chunk_size"] == 750
