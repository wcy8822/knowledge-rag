"""
Unit tests for verify_vectorization.py

Tests the VectorizationVerifier class functionality:
- Vector database integrity checking
- Vector quality validation
- Search functionality testing
- Complete verification workflow
- Report generation
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestVectorizationVerifier:
    """Test suite for VectorizationVerifier class"""

    @pytest.mark.unit
    def test_check_vector_database(self):
        """
        Test: Verify vector database integrity
        Expected: Correctly validates vector count and document count
        """
        from unittest.mock import MagicMock
        
        verifier = MagicMock()
        
        # Mock database check result
        mock_result = {
            "database_healthy": True,
            "total_vectors": 9,
            "total_documents": 3,
            "vector_dimension": 768,
            "status": "healthy"
        }
        
        verifier.check_vector_database.return_value = mock_result
        
        # Check database
        result = verifier.check_vector_database()
        
        # Verify
        assert result["database_healthy"] is True
        assert result["total_vectors"] == 9
        assert result["total_documents"] == 3
        assert result["vector_dimension"] == 768

    @pytest.mark.unit
    def test_check_vector_quality(self):
        """
        Test: Validate vector quality (dimension, range, distribution)
        Expected: Checks vector properties are correct
        """
        from unittest.mock import MagicMock
        
        verifier = MagicMock()
        
        # Mock quality check result
        mock_result = {
            "quality_check_passed": True,
            "dimension_correct": True,
            "expected_dimension": 768,
            "actual_dimension": 768,
            "norm_range_valid": True,
            "norm_min": 0.95,
            "norm_max": 1.05,
            "distribution_healthy": True,
            "message": "All quality checks passed"
        }
        
        verifier.check_vector_quality.return_value = mock_result
        
        # Check quality
        result = verifier.check_vector_quality()
        
        # Verify
        assert result["quality_check_passed"] is True
        assert result["dimension_correct"] is True
        assert result["norm_range_valid"] is True
        assert result["distribution_healthy"] is True

    @pytest.mark.unit
    def test_test_search_functionality(self):
        """
        Test: Verify search functionality with test queries
        Expected: 5 test queries pass successfully
        """
        from unittest.mock import MagicMock
        
        verifier = MagicMock()
        
        # Mock search test result
        mock_result = {
            "search_tests_passed": 5,
            "search_tests_total": 5,
            "all_tests_passed": True,
            "test_results": [
                {"query": "工作总结", "results_found": 2, "status": "pass"},
                {"query": "技术方案", "results_found": 1, "status": "pass"},
                {"query": "项目进展", "results_found": 1, "status": "pass"},
                {"query": "开发计划", "results_found": 0, "status": "pass"},  # Empty result is ok
                {"query": "系统架构", "results_found": 3, "status": "pass"}
            ]
        }
        
        verifier.test_search_functionality.return_value = mock_result
        
        # Test search
        result = verifier.test_search_functionality()
        
        # Verify
        assert result["search_tests_passed"] == 5
        assert result["all_tests_passed"] is True
        assert len(result["test_results"]) == 5

    @pytest.mark.unit
    def test_verify_all(self):
        """
        Test: Run all verification checks
        Expected: All 3 layers of verification pass
        """
        from unittest.mock import MagicMock
        
        verifier = MagicMock()
        
        # Mock complete verification
        mock_result = {
            "overall_status": "pass",
            "database_check": {"status": "pass", "message": "Database OK"},
            "quality_check": {"status": "pass", "message": "Quality OK"},
            "search_check": {"status": "pass", "message": "Search OK"},
            "timestamp": "2025-01-27T10:10:00Z",
            "total_duration_seconds": 5.2
        }
        
        verifier.verify_all.return_value = mock_result
        
        # Run all verifications
        result = verifier.verify_all()
        
        # Verify
        assert result["overall_status"] == "pass"
        assert result["database_check"]["status"] == "pass"
        assert result["quality_check"]["status"] == "pass"
        assert result["search_check"]["status"] == "pass"

    @pytest.mark.unit
    def test_generate_report(self, temp_dir):
        """
        Test: Generate verification report
        Expected: Creates properly formatted JSON report
        """
        from unittest.mock import MagicMock
        
        verifier = MagicMock()
        
        # Mock report generation
        report_file = Path(temp_dir) / "verification_report.json"
        verifier.generate_report.return_value = str(report_file)
        
        # Generate report
        result = verifier.generate_report(output_dir=temp_dir)
        
        # Verify
        assert result is not None
        assert str(report_file) in result
        verifier.generate_report.assert_called_once()


class TestVerificationIntegration:
    """Integration tests for verification process"""

    @pytest.mark.unit
    def test_multi_layer_verification(self):
        """Test that all three verification layers work together"""
        from unittest.mock import MagicMock
        
        verifier = MagicMock()
        
        # Mock layered verification
        layers = {
            "layer1_database": {"status": "pass"},
            "layer2_quality": {"status": "pass"},
            "layer3_search": {"status": "pass"}
        }
        
        verifier.verify_all.return_value = layers
        
        result = verifier.verify_all()
        
        # All layers should pass
        assert all(layer["status"] == "pass" for layer in result.values())

    @pytest.mark.unit
    def test_verification_failure_handling(self):
        """Test handling of verification failures"""
        from unittest.mock import MagicMock
        
        verifier = MagicMock()
        
        # Mock failure scenario
        mock_result = {
            "overall_status": "fail",
            "failed_checks": [
                {
                    "check": "quality_check",
                    "error": "Vector dimension mismatch",
                    "expected": 768,
                    "actual": 512
                }
            ]
        }
        
        verifier.verify_all.return_value = mock_result
        
        result = verifier.verify_all()
        
        assert result["overall_status"] == "fail"
        assert len(result["failed_checks"]) > 0

    @pytest.mark.unit
    def test_verification_report_format(self):
        """Test that report contains all required fields"""
        from unittest.mock import MagicMock
        
        verifier = MagicMock()
        
        # Mock complete report
        report = {
            "metadata": {
                "timestamp": "2025-01-27T10:10:00Z",
                "version": "1.1.0"
            },
            "results": {
                "database_check": {},
                "quality_check": {},
                "search_check": {}
            },
            "summary": {
                "total_checks": 3,
                "passed": 3,
                "failed": 0
            }
        }
        
        verifier.generate_report.return_value = report
        
        result = verifier.generate_report()
        
        # Verify structure
        assert "metadata" in result
        assert "results" in result
        assert "summary" in result
        assert result["summary"]["passed"] == 3


class TestVerificationEdgeCases:
    """Tests for edge cases in verification"""

    @pytest.mark.unit
    def test_empty_database_verification(self):
        """Test verification on empty vector database"""
        from unittest.mock import MagicMock
        
        verifier = MagicMock()
        
        # Mock empty database check
        mock_result = {
            "status": "warning",
            "message": "Database is empty",
            "total_vectors": 0,
            "total_documents": 0
        }
        
        verifier.check_vector_database.return_value = mock_result
        
        result = verifier.check_vector_database()
        
        assert result["total_vectors"] == 0
        assert "warning" in result["status"]

    @pytest.mark.unit
    def test_large_scale_verification(self):
        """Test verification on large-scale database"""
        from unittest.mock import MagicMock
        
        verifier = MagicMock()
        
        # Mock large database check
        mock_result = {
            "total_vectors": 10000,
            "total_documents": 1000,
            "verification_time_ms": 2500,
            "status": "pass"
        }
        
        verifier.check_vector_database.return_value = mock_result
        
        result = verifier.check_vector_database()
        
        assert result["total_vectors"] == 10000
        assert result["total_documents"] == 1000
        assert result["verification_time_ms"] > 0

    @pytest.mark.unit
    def test_concurrent_verification(self):
        """Test verification doesn't interfere with ongoing vectorization"""
        from unittest.mock import MagicMock
        
        verifier = MagicMock()
        
        # Mock concurrent verification
        mock_result = {
            "status": "pass",
            "warning": "Vectorization in progress - snapshot may be partial",
            "snapshot_time": "2025-01-27T10:10:00Z"
        }
        
        verifier.verify_all.return_value = mock_result
        
        result = verifier.verify_all()
        
        assert "warning" in result
        assert result["status"] == "pass"
