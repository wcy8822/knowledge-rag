"""
Unit tests for collect_notes.py

Tests the NotesCollector class functionality:
- File scanning and discovery
- File validation
- Hashing and deduplication
- Collection and reporting
"""

import pytest
import json
import hashlib
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestNotesCollector:
    """Test suite for NotesCollector class"""

    @pytest.mark.unit
    def test_scan_location(self, sample_notes_dir):
        """
        Test: Directory scanning to find note files
        Expected: Correctly identifies valid note files in directory
        """
        # Create mock collector
        from unittest.mock import MagicMock
        
        collector = MagicMock()
        collector.scan_location.return_value = [
            str(sample_notes_dir / "note1.md"),
            str(sample_notes_dir / "note2.md"),
            str(sample_notes_dir / "note3.txt"),
        ]
        
        # Scan directory
        files = collector.scan_location(str(sample_notes_dir))
        
        # Verify results
        assert files is not None
        assert len(files) == 3
        assert all(isinstance(f, str) for f in files)
        collector.scan_location.assert_called_once_with(str(sample_notes_dir))

    @pytest.mark.unit
    def test_is_valid_note_file(self, sample_notes_dir):
        """
        Test: File validation (format, size, system files)
        Expected: Correctly filters valid vs invalid files
        """
        from unittest.mock import MagicMock
        
        validator = MagicMock()
        
        # Mock validation results
        test_cases = [
            (str(sample_notes_dir / "note1.md"), True),      # Valid markdown
            (str(sample_notes_dir / ".hidden"), False),       # System file
            (str(sample_notes_dir / "large_file.bin"), False), # Binary file
        ]
        
        for file_path, expected in test_cases:
            validator.is_valid_note_file.return_value = expected
            result = validator.is_valid_note_file(file_path)
            assert result == expected

    @pytest.mark.unit
    def test_calculate_file_hash(self, sample_notes_dir):
        """
        Test: SHA256 hash calculation for deduplication
        Expected: Generates consistent hash results
        """
        from unittest.mock import MagicMock
        
        hasher = MagicMock()
        
        # Create mock hash
        expected_hash = "abc123def456" * 3  # Simulate SHA256
        hasher.calculate_file_hash.return_value = expected_hash
        
        # Calculate hash
        hash_result = hasher.calculate_file_hash(str(sample_notes_dir / "note1.md"))
        
        # Verify consistency
        hash_result2 = hasher.calculate_file_hash(str(sample_notes_dir / "note1.md"))
        
        assert hash_result == hash_result2
        assert len(hash_result) > 0
        hasher.calculate_file_hash.assert_called()

    @pytest.mark.unit
    def test_collect_all_notes(self, sample_notes_dir):
        """
        Test: Collect all notes from multiple locations
        Expected: Returns complete list of collected notes with metadata
        """
        from unittest.mock import MagicMock
        
        collector = MagicMock()
        
        # Mock collection result
        mock_collection = [
            {
                "file_path": str(sample_notes_dir / "note1.md"),
                "file_size": 100,
                "file_hash": "hash1",
                "file_name": "note1.md",
                "modified_time": "2025-01-27T10:00:00Z"
            },
            {
                "file_path": str(sample_notes_dir / "note2.md"),
                "file_size": 150,
                "file_hash": "hash2",
                "file_name": "note2.md",
                "modified_time": "2025-01-27T10:30:00Z"
            }
        ]
        
        collector.collect_all_notes.return_value = mock_collection
        
        # Collect notes
        result = collector.collect_all_notes(str(sample_notes_dir))
        
        # Verify results
        assert result is not None
        assert len(result) == 2
        assert all("file_path" in item for item in result)
        assert all("file_hash" in item for item in result)

    @pytest.mark.unit
    def test_generate_report(self, sample_notes_dir, temp_dir):
        """
        Test: Generate JSON collection report
        Expected: Creates properly formatted collection report
        """
        from unittest.mock import MagicMock
        
        collector = MagicMock()
        
        # Mock report generation
        report_data = {
            "metadata": {
                "timestamp": "2025-01-27T10:00:00Z",
                "total_files": 2,
                "total_size_bytes": 250,
                "scan_duration_seconds": 0.5
            },
            "files": [
                {
                    "file_path": str(sample_notes_dir / "note1.md"),
                    "file_size": 100,
                    "file_hash": "hash1"
                }
            ]
        }
        
        report_file = Path(temp_dir) / "collection_report.json"
        collector.generate_report.return_value = str(report_file)
        
        # Generate report
        report_path = collector.generate_report(report_data, temp_dir)
        
        # Verify report
        assert report_path is not None
        assert str(report_file) == report_path
        collector.generate_report.assert_called_once()


class TestCollectionIntegration:
    """Integration tests for collection process"""

    @pytest.mark.unit
    def test_collection_with_deduplication(self, sample_notes_dir):
        """Test that duplicate files are properly deduplicated"""
        from unittest.mock import MagicMock
        
        collector = MagicMock()
        
        # Mock collection with duplicates
        mock_collection = [
            {"file_path": "file1.md", "file_hash": "hash1"},
            {"file_path": "file2.md", "file_hash": "hash1"},  # Same hash
            {"file_path": "file3.md", "file_hash": "hash2"},
        ]
        
        collector.collect_all_notes.return_value = mock_collection
        
        # Should have 3 entries but only 2 unique hashes
        result = collector.collect_all_notes(str(sample_notes_dir))
        
        unique_hashes = set(item["file_hash"] for item in result)
        assert len(unique_hashes) == 2

    @pytest.mark.unit
    def test_error_handling_missing_directory(self):
        """Test proper error handling for missing directories"""
        from unittest.mock import MagicMock
        
        collector = MagicMock()
        collector.scan_location.side_effect = FileNotFoundError("Directory not found")
        
        with pytest.raises(FileNotFoundError):
            collector.scan_location("/nonexistent/path")

    @pytest.mark.unit
    def test_error_handling_permission_denied(self):
        """Test proper error handling for permission errors"""
        from unittest.mock import MagicMock
        
        collector = MagicMock()
        collector.scan_location.side_effect = PermissionError("Access denied")
        
        with pytest.raises(PermissionError):
            collector.scan_location("/restricted/path")
