"""Tests for S3 utility module."""

import pytest
from datetime import date
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from commons.s3_utils import (
    S3Configuration,
    S3PathBuilder,
    S3Uploader,
    validate_version_format
)


class TestValidateVersionFormat:
    """Tests for validate_version_format function."""

    def test_validate_version_format_valid(self) -> None:
        """Test valid version format."""
        assert validate_version_format("20251215113400Z")
        assert validate_version_format("20200101000000Z")
        assert validate_version_format("20991231235959Z")

    def test_validate_version_format_invalid(self) -> None:
        """Test invalid version formats."""
        # Missing Z
        assert not validate_version_format("20251215113400")
        # Too short
        assert not validate_version_format("2025121511340Z")
        # Too long
        assert not validate_version_format("202512151134000Z")
        # Invalid characters
        assert not validate_version_format("2025-12-15T11:34:00Z")
        # Not a timestamp
        assert not validate_version_format("invalid")
        # Empty
        assert not validate_version_format("")


class TestS3Configuration:
    """Tests for S3Configuration class."""

    def test_s3_configuration_valid(self) -> None:
        """Test valid S3 configuration."""
        config = S3Configuration("my-bucket", "raw-data")
        assert config.bucket == "my-bucket"
        assert config.prefix == "raw-data"

    def test_s3_configuration_empty_bucket(self) -> None:
        """Test empty bucket name."""
        with pytest.raises(ValueError, match="S3 bucket cannot be empty"):
            S3Configuration("", "prefix")

    def test_s3_configuration_invalid_bucket(self) -> None:
        """Test invalid bucket names."""
        # Uppercase not allowed
        with pytest.raises(ValueError, match="Invalid S3 bucket name"):
            S3Configuration("MyBucket", "prefix")

        # Underscores not allowed
        with pytest.raises(ValueError, match="Invalid S3 bucket name"):
            S3Configuration("my_bucket", "prefix")

        # Special characters not allowed
        with pytest.raises(ValueError, match="Invalid S3 bucket name"):
            S3Configuration("my@bucket", "prefix")

    def test_s3_configuration_valid_bucket_names(self) -> None:
        """Test valid bucket name patterns."""
        # Lowercase letters, numbers, hyphens, dots
        config1 = S3Configuration("my-bucket", "prefix")
        assert config1.bucket == "my-bucket"

        config2 = S3Configuration("mybucket123", "prefix")
        assert config2.bucket == "mybucket123"

        config3 = S3Configuration("my.bucket.name", "prefix")
        assert config3.bucket == "my.bucket.name"

    def test_s3_configuration_path_traversal_prefix(self) -> None:
        """Test path traversal detection in prefix."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            S3Configuration("bucket", "../malicious")

        with pytest.raises(ValueError, match="Path traversal detected"):
            S3Configuration("bucket", "/absolute/path")

    def test_s3_configuration_invalid_prefix_characters(self) -> None:
        """Test invalid characters in prefix."""
        # Uppercase not allowed
        with pytest.raises(ValueError, match="Invalid characters in prefix"):
            S3Configuration("bucket", "RawData")

        # Special characters not allowed
        with pytest.raises(ValueError, match="Invalid characters in prefix"):
            S3Configuration("bucket", "raw@data")

    def test_s3_configuration_prefix_normalization(self) -> None:
        """Test prefix normalization (strip slashes)."""
        # Test with leading slash - should fail validation
        with pytest.raises(ValueError, match="Path traversal detected"):
            S3Configuration("bucket", "/raw-data/")

        # Test with trailing slash only
        config2 = S3Configuration("bucket", "raw-data/")
        assert config2.prefix == "raw-data"

        # Test with no slashes
        config3 = S3Configuration("bucket", "raw-data")
        assert config3.prefix == "raw-data"

        # Empty prefix
        config4 = S3Configuration("bucket", "")
        assert config4.prefix == ""

    def test_s3_configuration_prefix_with_slashes(self) -> None:
        """Test prefix with internal slashes."""
        config = S3Configuration("bucket", "raw/data/subfolder")
        assert config.prefix == "raw/data/subfolder"


class TestS3PathBuilder:
    """Tests for S3PathBuilder class."""

    def test_build_path_basic(self) -> None:
        """Test basic path building."""
        builder = S3PathBuilder()
        config = S3Configuration("my-bucket", "raw-data")
        path = builder.build_path(
            config=config,
            filename="data.json",
            file_date=date(2025, 12, 15),
            version="20251215113400Z"
        )

        expected = (
            "s3://my-bucket/raw-data/"
            "year=2025/month=12/day=15/20251215113400Z/data.json"
        )
        assert path == expected

    def test_build_path_no_prefix(self) -> None:
        """Test path building without prefix."""
        builder = S3PathBuilder()
        config = S3Configuration("my-bucket", "")
        path = builder.build_path(
            config=config,
            filename="data.json",
            file_date=date(2025, 1, 5),
            version="20250105093000Z"
        )

        expected = (
            "s3://my-bucket/"
            "year=2025/month=01/day=05/20250105093000Z/data.json"
        )
        assert path == expected

    def test_build_path_no_dgroup(self) -> None:
        """Confirm dgroup is not in path."""
        builder = S3PathBuilder()
        config = S3Configuration("bucket", "prefix")
        path = builder.build_path(
            config=config,
            filename="file.json",
            file_date=date(2025, 12, 15),
            version="20251215113400Z"
        )

        # Should not contain any dgroup reference
        assert "dgroup" not in path.lower()
        assert "nyiso" not in path
        assert "miso" not in path

    def test_build_path_version_included(self) -> None:
        """Confirm version is included in path."""
        builder = S3PathBuilder()
        config = S3Configuration("bucket", "prefix")
        version = "20251215113400Z"
        path = builder.build_path(
            config=config,
            filename="file.json",
            file_date=date(2025, 12, 15),
            version=version
        )

        # Version should be in path
        assert version in path
        # Verify it's in the right position (after day, before filename)
        assert f"day=15/{version}/file.json" in path

    def test_build_path_date_formatting(self) -> None:
        """Test date formatting with zero-padding."""
        builder = S3PathBuilder()
        config = S3Configuration("bucket", "prefix")
        path = builder.build_path(
            config=config,
            filename="file.json",
            file_date=date(2025, 1, 5),  # Single digit month and day
            version="20250105000000Z"
        )

        assert "year=2025" in path
        assert "month=01" in path  # Zero-padded
        assert "day=05" in path    # Zero-padded

    def test_build_path_empty_filename(self) -> None:
        """Test empty filename validation."""
        builder = S3PathBuilder()
        config = S3Configuration("bucket", "prefix")

        with pytest.raises(ValueError, match="filename cannot be empty"):
            builder.build_path(
                config=config,
                filename="",
                file_date=date(2025, 12, 15),
                version="20251215113400Z"
            )

    def test_build_path_empty_version(self) -> None:
        """Test empty version validation."""
        builder = S3PathBuilder()
        config = S3Configuration("bucket", "prefix")

        with pytest.raises(ValueError, match="version cannot be empty"):
            builder.build_path(
                config=config,
                filename="file.json",
                file_date=date(2025, 12, 15),
                version=""
            )

    def test_build_path_traversal_filename(self) -> None:
        """Test path traversal detection in filename."""
        builder = S3PathBuilder()
        config = S3Configuration("bucket", "prefix")

        with pytest.raises(ValueError, match="Path traversal detected"):
            builder.build_path(
                config=config,
                filename="../malicious.json",
                file_date=date(2025, 12, 15),
                version="20251215113400Z"
            )

    def test_build_path_invalid_filename_characters(self) -> None:
        """Test invalid characters in filename."""
        builder = S3PathBuilder()
        config = S3Configuration("bucket", "prefix")

        with pytest.raises(ValueError, match="Invalid characters in filename"):
            builder.build_path(
                config=config,
                filename="file@name.json",
                file_date=date(2025, 12, 15),
                version="20251215113400Z"
            )


class TestS3Uploader:
    """Tests for S3Uploader class."""

    @patch("commons.s3_utils.boto3.client")
    def test_upload_success(self, mock_boto3_client: Mock) -> None:
        """Test successful upload."""
        # Mock S3 client
        mock_s3_client = Mock()
        mock_s3_client.put_object.return_value = {
            "ETag": '"abc123def456"',
            "VersionId": "v1"
        }
        mock_boto3_client.return_value = mock_s3_client

        # Create uploader
        config = S3Configuration("my-bucket", "raw-data")
        uploader = S3Uploader(config)

        # Upload
        s3_path, version, etag = uploader.upload(
            content=b"test data",
            filename="test.json",
            file_date=date(2025, 12, 15),
            version="20251215113400Z"
        )

        # Verify
        assert s3_path == (
            "s3://my-bucket/raw-data/"
            "year=2025/month=12/day=15/20251215113400Z/test.json"
        )
        assert version == "20251215113400Z"
        assert etag == "abc123def456"

        # Verify put_object was called
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]["Bucket"] == "my-bucket"
        assert call_args[1]["Key"] == (
            "raw-data/year=2025/month=12/day=15/20251215113400Z/test.json"
        )
        assert call_args[1]["Body"] == b"test data"

    @patch("commons.s3_utils.boto3.client")
    def test_upload_invalid_version_format(self, mock_boto3_client: Mock) -> None:
        """Test upload with invalid version format."""
        config = S3Configuration("bucket", "prefix")
        uploader = S3Uploader(config)

        with pytest.raises(ValueError, match="Invalid version format"):
            uploader.upload(
                content=b"data",
                filename="file.json",
                file_date=date(2025, 12, 15),
                version="invalid"
            )

    @patch("commons.s3_utils.boto3.client")
    def test_upload_version_parameter_used(self, mock_boto3_client: Mock) -> None:
        """Test that version parameter is used (not auto-generated)."""
        mock_s3_client = Mock()
        mock_s3_client.put_object.return_value = {"ETag": '"etag"'}
        mock_boto3_client.return_value = mock_s3_client

        config = S3Configuration("bucket", "prefix")
        uploader = S3Uploader(config)

        version_input = "20251215113400Z"
        s3_path, version_output, etag = uploader.upload(
            content=b"data",
            filename="file.json",
            file_date=date(2025, 12, 15),
            version=version_input
        )

        # Version output should match input (not auto-generated)
        assert version_output == version_input
        # Version should be in S3 path
        assert version_input in s3_path

    @patch("commons.s3_utils.boto3.client")
    def test_upload_s3_error(self, mock_boto3_client: Mock) -> None:
        """Test upload with S3 error."""
        mock_s3_client = Mock()
        mock_s3_client.put_object.side_effect = Exception("S3 error")
        mock_boto3_client.return_value = mock_s3_client

        config = S3Configuration("bucket", "prefix")
        uploader = S3Uploader(config)

        with pytest.raises(Exception, match="Failed to upload to S3"):
            uploader.upload(
                content=b"data",
                filename="file.json",
                file_date=date(2025, 12, 15),
                version="20251215113400Z"
            )

    @patch("commons.s3_utils.boto3.client")
    def test_upload_no_prefix(self, mock_boto3_client: Mock) -> None:
        """Test upload with no prefix."""
        mock_s3_client = Mock()
        mock_s3_client.put_object.return_value = {"ETag": '"etag"'}
        mock_boto3_client.return_value = mock_s3_client

        config = S3Configuration("bucket", "")
        uploader = S3Uploader(config)

        s3_path, version, etag = uploader.upload(
            content=b"data",
            filename="file.json",
            file_date=date(2025, 12, 15),
            version="20251215113400Z"
        )

        # Should not have double slash after bucket
        assert s3_path == (
            "s3://bucket/year=2025/month=12/day=15/20251215113400Z/file.json"
        )

        # Verify key doesn't start with slash
        call_args = mock_s3_client.put_object.call_args
        key = call_args[1]["Key"]
        assert not key.startswith("/")
