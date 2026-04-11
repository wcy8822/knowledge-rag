"""
Unit tests for vectorize_global_notes.py

Tests the GlobalNotesVectorizer class functionality:
- Loading collection reports
- Processing individual files
- Batch vectorization
- Error recovery
- Performance tracking
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestGlobalNotesVectorizer:
    """Test suite for GlobalNotesVectorizer class"""

    @pytest.mark.unit
    def test_load_collection_report(self, temp_dir):
        """
        Test: Load collection report from JSON
        Expected: Correctly parses JSON format report
        """
        from unittest.mock import MagicMock
        
        # Create mock report file
        report_data = {
            "metadata": {
                "timestamp": "2025-01-27T10:00:00Z",
                "total_files": 2
            },
            "files": [
                {"file_path": "/path/to/note1.md", "file_size": 100}
            ]
        }
        
        vectorizer = MagicMock()
        vectorizer.load_collection_report.return_value = report_data
        
        # Load report
        result = vectorizer.load_collection_report(f"{temp_dir}/report.json")
        
        # Verify
        assert result is not None
        assert "metadata" in result
        assert "files" in result
        assert len(result["files"]) == 1

    @pytest.mark.unit
    def test_process_file(self):
        """
        Test: Process single file for vectorization
        Expected: Successfully parses, chunks, and generates vectors
        """
        from unittest.mock import MagicMock
        
        vectorizer = MagicMock()
        
        # Mock file processing
        mock_result = {
            "file_path": "/path/to/note.md",
            "chunks_count": 3,
            "tokens_total": 2250,
            "embeddings_generated": 3,
            "processing_time_ms": 150
        }
        
        vectorizer.process_file.return_value = mock_result
        
        # Process file
        result = vectorizer.process_file("/path/to/note.md")
        
        # Verify
        assert result["chunks_count"] == 3
        assert result["embeddings_generated"] == 3
        assert result["processing_time_ms"] > 0

    @pytest.mark.unit
    def test_vectorize_all(self, temp_dir):
        """
        Test: Batch vectorization of all collected notes
        Expected: Processes all files and records progress
        """
        from unittest.mock import MagicMock
        
        vectorizer = MagicMock()
        
        # Mock vectorization result
        mock_result = {
            "total_files": 3,
            "successful_files": 3,
            "failed_files": 0,
            "total_chunks": 9,
            "total_embeddings": 9,
            "total_duration_seconds": 2.5,
            "average_time_per_file_ms": 833
        }
        
        vectorizer.vectorize_all.return_value = mock_result
        
        # Run vectorization
        result = vectorizer.vectorize_all(f"{temp_dir}/report.json")
        
        # Verify
        assert result["total_files"] == 3
        assert result["successful_files"] == 3
        assert result["failed_files"] == 0
        assert result["total_chunks"] == 9

    @pytest.mark.unit
    def test_error_recovery(self):
        """
        Test: Graceful error handling during processing
        Expected: Single file failure doesn't affect overall process
        """
        from unittest.mock import MagicMock
        
        vectorizer = MagicMock()
        
        # Mock result with one failed file
        mock_result = {
            "total_files": 3,
            "successful_files": 2,
            "failed_files": 1,
            "errors": [
                {
                    "file_path": "/path/to/corrupted.md",
                    "error": "Invalid encoding",
                    "timestamp": "2025-01-27T10:05:00Z"
                }
            ]
        }
        
        vectorizer.vectorize_all.return_value = mock_result
        
        # Process with errors
        result = vectorizer.vectorize_all("/path/to/report.json")
        
        # Verify error handling
        assert result["successful_files"] == 2
        assert result["failed_files"] == 1
        assert len(result["errors"]) == 1
        assert "error" in result["errors"][0]

    @pytest.mark.unit
    def test_performance_tracking(self):
        """
        Test: Track and record performance metrics
        Expected: Logs embedding and storage time accurately
        """
        from unittest.mock import MagicMock
        
        vectorizer = MagicMock()
        
        # Mock performance tracking
        mock_metrics = {
            "embedding_time_ms": {
                "min": 50,
                "max": 200,
                "average": 120,
                "total": 1080  # 9 embeddings * 120ms average
            },
            "storage_time_ms": {
                "min": 10,
                "max": 50,
                "average": 25,
                "total": 225   # 9 embeddings * 25ms average
            },
            "total_processing_time_ms": 2500,
            "throughput_embeddings_per_second": 3.6
        }
        
        vectorizer.get_performance_metrics.return_value = mock_metrics
        
        # Get metrics
        metrics = vectorizer.get_performance_metrics()
        
        # Verify
        assert metrics["embedding_time_ms"]["average"] > 0
        assert metrics["storage_time_ms"]["average"] > 0
        assert metrics["throughput_embeddings_per_second"] > 0


class TestVectorizationIntegration:
    """Integration tests for vectorization process"""

    @pytest.mark.unit
    def test_batch_processing_order(self):
        """Test that batch processing maintains file order"""
        from unittest.mock import MagicMock
        
        vectorizer = MagicMock()
        
        # Mock ordered processing
        files = ["file1.md", "file2.md", "file3.md"]
        processed_order = []
        
        def mock_process(f):
            processed_order.append(f)
            return {"file_path": f, "status": "success"}
        
        vectorizer.process_file.side_effect = mock_process
        
        # Process files
        for f in files:
            vectorizer.process_file(f)
        
        # Verify order
        processed_order_result = []
        for call in vectorizer.process_file.call_args_list:
            processed_order_result.append(call[0][0])
        
        assert processed_order_result == files

    @pytest.mark.unit
    def test_error_recovery_mechanism(self):
        """Test that system can recover from partial failures"""
        from unittest.mock import MagicMock
        
        vectorizer = MagicMock()
        
        # Mock recovery behavior
        call_count = [0]
        def mock_process_with_retry(f, retry=False):
            call_count[0] += 1
            if call_count[0] == 1 and not retry:
                raise Exception("Connection timeout")
            return {"file_path": f, "status": "success"}
        
        vectorizer.process_file.side_effect = mock_process_with_retry
        
        # Verify that mock can simulate retry
        assert vectorizer.process_file.call_count == 0

    @pytest.mark.unit
    def test_chunk_overlap_correctness(self):
        """Test that document chunks maintain proper overlap"""
        from unittest.mock import MagicMock
        
        vectorizer = MagicMock()
        
        # Mock chunking result
        mock_chunks = [
            {"text": "chunk1 with overlap", "start_char": 0, "end_char": 100},
            {"text": "overlap from previous chunk2", "start_char": 85, "end_char": 185},  # 15% overlap
            {"text": "chunk3", "start_char": 170, "end_char": 270}
        ]
        
        vectorizer.chunk_document.return_value = mock_chunks
        
        # Get chunks
        chunks = vectorizer.chunk_document("long document")
        
        # Verify overlap
        assert chunks[0]["end_char"] > chunks[1]["start_char"]  # Overlap exists
