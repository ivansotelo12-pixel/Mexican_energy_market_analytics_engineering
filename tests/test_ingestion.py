# filepath: tests/test_ingestion.py
"""Tests for CENACE PML data ingestion components."""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.cenace_client import CenaceAPIClient, fetch_cenace_pml_data
from src.ingestion.data_validator import (
    ValidationResult,
    filter_valid_records,
    validate_data_quality,
    validate_record,
)
from src.ingestion.s3_manager import S3Manager
from src.utils.config import build_cenace_url, format_cenace_date, get_date_range


# =============================================================================
# Tests for config.py
# =============================================================================
class TestConfig:
    """Tests for configuration utilities."""
    
    def test_format_cenace_date(self):
        """Test date formatting for CENACE API."""
        dt = datetime(2026, 5, 28)
        result = format_cenace_date(dt)
        assert result == "2026/05/28"
    
    def test_get_date_range_default(self):
        """Test default 7-day lookback."""
        start, end = get_date_range(7)
        delta = end - start
        assert delta.days == 7
    
    def test_get_date_range_custom(self):
        """Test custom lookback period."""
        start, end = get_date_range(30)
        delta = end - start
        assert delta.days == 30
    
    def test_build_cenace_url(self):
        """Test CENACE URL construction."""
        start = datetime(2026, 5, 21)
        end = datetime(2026, 5, 28)
        url = build_cenace_url("03CHI-115", start, end)
        
        assert "03CHI-115" in url
        assert "SIN" in url
        assert "MDA" in url
        assert "2026/05/21" in url
        assert "2026/05/28" in url


# =============================================================================
# Tests for data_validator.py
# =============================================================================
class TestDataValidator:
    """Tests for PML data validation."""
    
    def test_validate_record_valid(self):
        """Test validation of a valid PML record."""
        record = {
            "nodo": "03CHI-115",
            "fecha": "2026-05-28",
            "pml": 1500.50,
            "pml_energia": 1400.00,
            "pml_perdidas": 50.25,
            "pml_congestion": 50.25,
        }
        is_valid, error = validate_record(record)
        assert is_valid is True
        assert error is None
    
    def test_validate_record_missing_field(self):
        """Test validation fails for missing required field."""
        record = {
            "nodo": "03CHI-115",
            "fecha": "2026-05-28",
            "pml": 1500.50,
            # Missing pml_energia, pml_perdidas, pml_congestion
        }
        is_valid, error = validate_record(record)
        assert is_valid is False
        assert "Missing required field" in error
    
    def test_validate_record_invalid_pml_range(self):
        """Test validation fails for out-of-range PML value."""
        record = {
            "nodo": "03CHI-115",
            "fecha": "2026-05-28",
            "pml": 60000,  # Above max of 50000
            "pml_energia": 1400.00,
            "pml_perdidas": 50.25,
            "pml_congestion": 50.25,
        }
        is_valid, error = validate_record(record)
        assert is_valid is False
        assert "outside valid range" in error
    
    def test_validate_record_invalid_date_format(self):
        """Test validation fails for invalid date format."""
        record = {
            "nodo": "03CHI-115",
            "fecha": "28-05-2026",  # Wrong format
            "pml": 1500.50,
            "pml_energia": 1400.00,
            "pml_perdidas": 50.25,
            "pml_congestion": 50.25,
        }
        is_valid, error = validate_record(record)
        assert is_valid is False
        assert "Invalid date format" in error
    
    def test_validate_record_invalid_nodo_format(self):
        """Test validation fails for invalid nodo format."""
        record = {
            "nodo": "INVALID",
            "fecha": "2026-05-28",
            "pml": 1500.50,
            "pml_energia": 1400.00,
            "pml_perdidas": 50.25,
            "pml_congestion": 50.25,
        }
        is_valid, error = validate_record(record)
        assert is_valid is False
        assert "Invalid nodo format" in error
    
    def test_validate_data_quality(self):
        """Test batch validation of records."""
        records = [
            {
                "nodo": "03CHI-115",
                "fecha": "2026-05-28",
                "pml": 1500.50,
                "pml_energia": 1400.00,
                "pml_perdidas": 50.25,
                "pml_congestion": 50.25,
            },
            {
                "nodo": "03GJA-115",
                "fecha": "2026-03-28",
                "pml": 1600.00,
                "pml_energia": 1500.00,
                "pml_perdidas": 50.00,
                "pml_congestion": 50.00,
            },
            {
                "nodo": "INVALID",  # Invalid
                "fecha": "2026-03-28",
                "pml": 1500.50,
                "pml_energia": 1400.00,
                "pml_perdidas": 50.25,
                "pml_congestion": 50.25,
            },
        ]
        
        result = validate_data_quality(records)
        assert result.total_valid == 2
        assert result.total_invalid == 1
        assert result.is_valid is False
    
    def test_validate_data_quality_empty(self):
        """Test validation with empty record list."""
        result = validate_data_quality([])
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_filter_valid_records(self):
        """Test filtering records into valid/invalid."""
        records = [
            {
                "nodo": "03CHI-115",
                "fecha": "2026-03-28",
                "pml": 1500.50,
                "pml_energia": 1400.00,
                "pml_perdidas": 50.25,
                "pml_congestion": 50.25,
            },
            {
                "nodo": "INVALID",
                "fecha": "2026-03-28",
                "pml": 1500.50,
                "pml_energia": 1400.00,
                "pml_perdidas": 50.25,
                "pml_congestion": 50.25,
            },
        ]
        
        valid, invalid = filter_valid_records(records)
        assert len(valid) == 1
        assert len(invalid) == 1


# =============================================================================
# Tests for cenace_client.py
# =============================================================================
class TestCenaceClient:
    """Tests for CENACE API client."""
    
    @patch("src.ingestion.cenace_client.requests.get")
    def test_fetch_pml_data_success(self, mock_get):
        """Test successful PML data fetch."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "datos": [
                {
                    "fecha": "2026-03-28",
                    "pml": 1500.50,
                    "pml_energia": 1400.00,
                    "pml_perdidas": 50.25,
                    "pml_congestion": 50.25,
                }
            ],
            "status": "OK",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        client = CenaceAPIClient()
        records = client.fetch_pml_data("03CHI-115", 7)
        
        assert len(records) == 1
        assert records[0]["nodo"] == "03CHI-115"
        assert records[0]["pml"] == 1500.50
    
    @patch("src.ingestion.cenace_client.requests.get")
    def test_parse_response(self, mock_get):
        """Test API response parsing."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "datos": [
                {
                    "fecha": "2026-03-28",
                    "pml": 1500.50,
                    "pml_energia": 1400.00,
                    "pml_perdidas": 50.25,
                    "pml_congestion": 50.25,
                },
                {
                    "fecha": "2026-03-27",
                    "pml": 1450.00,
                    "pml_energia": 1350.00,
                    "pml_perdidas": 50.00,
                    "pml_congestion": 50.00,
                },
            ],
            "status": "OK",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        client = CenaceAPIClient()
        records = client._parse_response(mock_response.json(), "03CHI-115")
        
        assert len(records) == 2
        assert all(r["nodo"] == "03CHI-115" for r in records)
    
    @patch("src.ingestion.cenace_client.requests.get")
    def test_fetch_pml_data_api_error(self, mock_get):
        """Test handling of API errors."""
        import requests
        
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("API Error")
        mock_get.return_value = mock_response
        
        client = CenaceAPIClient()
        
        with pytest.raises(requests.HTTPError):
            client.fetch_pml_data("03CHI-115", 7)


# =============================================================================
# Tests for s3_manager.py
# =============================================================================
class TestS3Manager:
    """Tests for S3 operations."""
    
    @patch("src.ingestion.s3_manager.boto3.client")
    def test_build_s3_key_with_datetime(self, mock_boto):
        """Test S3 key building with datetime object."""
        mock_boto.return_value = MagicMock()
        manager = S3Manager(bucket="test-bucket")
        dt = datetime(2026, 3, 28)
        key = manager._build_s3_key("03CHI-115", dt)

        assert "raw/pml/2026/03/28/03CHI-115/data.parquet" in key

    @patch("src.ingestion.s3_manager.boto3.client")
    def test_build_s3_key_with_string_date(self, mock_boto):
        """Test S3 key building with string date."""
        mock_boto.return_value = MagicMock()
        manager = S3Manager(bucket="test-bucket")
        key = manager._build_s3_key("03CHI-115", "2026-03-28")

        assert "raw/pml/2026/03/28/03CHI-115/data.parquet" in key
    
    @patch("src.ingestion.s3_manager.boto3.client")
    def test_upload_parquet_success(self, mock_boto):
        """Test successful Parquet upload."""
        # Setup mocks
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3
        
        manager = S3Manager(bucket="test-bucket")
        records = [
            {
                "nodo": "03CHI-115",
                "fecha": "2026-03-28",
                "pml": 1500.50,
                "pml_energia": 1400.00,
                "pml_perdidas": 50.25,
                "pml_congestion": 50.25,
            }
        ]
        
        result = manager.upload_parquet(records, "03CHI-115", "2026-03-28")
        
        assert result is True
        mock_s3.put_object.assert_called_once()
    
    @patch("src.ingestion.s3_manager.boto3.client")
    def test_upload_parquet_empty_records(self, mock_boto):
        """Test upload with empty records."""
        mock_boto.return_value = MagicMock()
        
        manager = S3Manager(bucket="test-bucket")
        result = manager.upload_parquet([], "03CHI-115", "2026-03-28")
        
        assert result is False
    
    @patch("src.ingestion.s3_manager.boto3.client")
    def test_list_objects(self, mock_boto):
        """Test listing S3 objects."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "raw/pml/2026/03/28/03CHI-115/data.parquet"},
                {"Key": "raw/pml/2026/03/28/03GJA-115/data.parquet"},
            ]
        }
        mock_boto.return_value = mock_s3
        
        manager = S3Manager(bucket="test-bucket")
        objects = manager.list_objects("raw/pml/2026/03/28/")
        
        assert len(objects) == 2
        assert "03CHI-115" in objects[0]


# =============================================================================
# Integration-style tests
# =============================================================================
class TestIngestionFlow:
    """Integration tests for the complete ingestion flow."""
    
    def test_full_flow_with_mock(self):
        """Test complete ingestion flow with mocked dependencies."""
        # This simulates the full flow without actual API/S3 calls
        from src.ingestion.main import lambda_handler
        
        # Mock both API and S3
        with patch("src.ingestion.main.CenaceAPIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.fetch_pml_data.return_value = [
                {
                    "nodo": "03CHI-115",
                    "fecha": "2026-03-28",
                    "pml": 1500.50,
                    "pml_energia": 1400.00,
                    "pml_perdidas": 50.25,
                    "pml_congestion": 50.25,
                }
            ]
            mock_client_class.return_value = mock_client
            
            with patch("src.ingestion.main.S3Manager") as mock_s3_class:
                mock_s3 = MagicMock()
                mock_s3.upload_parquet.return_value = True
                mock_s3_class.return_value = mock_s3
                
                result = lambda_handler({}, None)
                
                assert result["status"] == "success"
                assert result["nodes_processed"] >= 1
