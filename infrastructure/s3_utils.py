"""S3 utility module for data storage with versioning.

This module provides reusable S3 functionality for scrapers, similar to kafka_utils.py.
It implements configuration validation, path building with versioning, and S3 uploads.

Example:
    >>> config = S3Configuration("my-bucket", "raw-data")
    >>> uploader = S3Uploader(config)
    >>> s3_path, version, etag = uploader.upload(
    ...     content=b"data",
    ...     filename="file.json",
    ...     file_date=date(2025, 12, 15),
    ...     version="20251215113400Z"
    ... )
    >>> print(s3_path)
    s3://my-bucket/raw-data/year=2025/month=12/day=15/20251215113400Z/file.json
"""

import re
import logging
from datetime import date
from typing import Tuple

import boto3

logger = logging.getLogger("sourcing_app")


def validate_version_format(version: str) -> bool:
    """Validate version matches YYYYMMDDHHMMSSZ format.

    Args:
        version: Version string to validate

    Returns:
        True if valid, False otherwise

    Example:
        >>> validate_version_format("20251215113400Z")
        True
        >>> validate_version_format("20251215")
        False
        >>> validate_version_format("2025-12-15")
        False
    """
    pattern = r"^\d{14}Z$"
    return bool(re.match(pattern, version))


class S3Configuration:
    """S3 configuration with validation.

    Validates and stores S3 bucket and prefix configuration with security checks
    to prevent path traversal and invalid bucket names.

    Attributes:
        bucket: S3 bucket name (validated)
        prefix: S3 key prefix (validated and normalized)

    Raises:
        ValueError: If bucket or prefix validation fails

    Example:
        >>> config = S3Configuration("my-bucket", "raw-data")
        >>> print(config.bucket)
        my-bucket
        >>> print(config.prefix)
        raw-data
    """

    def __init__(self, bucket: str, prefix: str) -> None:
        """Initialize S3 configuration.

        Args:
            bucket: S3 bucket name
            prefix: S3 key prefix

        Raises:
            ValueError: If validation fails
        """
        self.bucket = self._validate_bucket(bucket)
        self.prefix = self._validate_prefix(prefix)

    def _validate_bucket(self, bucket: str) -> str:
        """Validate S3 bucket name.

        Args:
            bucket: Bucket name to validate

        Returns:
            Validated bucket name

        Raises:
            ValueError: If bucket name is invalid
        """
        if not bucket:
            raise ValueError("S3 bucket cannot be empty")

        if not re.match(r"^[a-z0-9\-\.]+$", bucket):
            raise ValueError(
                f"Invalid S3 bucket name '{bucket}'. "
                "Only lowercase letters, numbers, hyphens, and dots allowed."
            )

        return bucket

    def _validate_prefix(self, prefix: str) -> str:
        """Validate and normalize S3 prefix.

        Args:
            prefix: Prefix to validate

        Returns:
            Validated and normalized prefix (no leading/trailing slashes)

        Raises:
            ValueError: If prefix contains path traversal or invalid characters
        """
        # Check for path traversal
        if ".." in prefix or prefix.startswith("/"):
            raise ValueError(f"Path traversal detected in prefix: {prefix}")

        if prefix and not re.match(r"^[a-z0-9_\-\/]*$", prefix):
            raise ValueError(
                f"Invalid characters in prefix '{prefix}'. "
                "Only lowercase letters, numbers, underscores, hyphens, "
                "and slashes allowed."
            )

        # Normalize: strip leading/trailing slashes
        return prefix.strip("/")


class S3PathBuilder:
    """Builds S3 paths with date partitioning and versioning.

    Constructs S3 paths following the pattern:
    s3://{bucket}/{prefix}/year=YYYY/month=MM/day=DD/{version}/{filename}

    Example:
        >>> builder = S3PathBuilder()
        >>> config = S3Configuration("my-bucket", "raw-data")
        >>> path = builder.build_path(
        ...     config=config,
        ...     filename="data.json",
        ...     file_date=date(2025, 12, 15),
        ...     version="20251215113400Z"
        ... )
        >>> print(path)
        s3://my-bucket/raw-data/year=2025/month=12/day=15/20251215113400Z/data.json
    """

    def build_path(
        self,
        config: S3Configuration,
        filename: str,
        file_date: date,
        version: str
    ) -> str:
        """Build S3 path with date partitioning and version.

        Args:
            config: S3 configuration
            filename: File name
            file_date: Date for partitioning
            version: Version timestamp (format: YYYYMMDDHHMMSSZ)

        Returns:
            Full S3 path

        Raises:
            ValueError: If path components are invalid

        Example:
            >>> builder = S3PathBuilder()
            >>> config = S3Configuration("bucket", "prefix")
            >>> path = builder.build_path(
            ...     config, "file.json", date(2025, 12, 15), "20251215113400Z"
            ... )
        """
        # Validate path components for security
        self._validate_path_component(filename, "filename")
        self._validate_path_component(version, "version")

        # Build date partition
        year = file_date.year
        month = f"{file_date.month:02d}"
        day = f"{file_date.day:02d}"

        # Construct path
        if config.prefix:
            path = (
                f"s3://{config.bucket}/{config.prefix}/"
                f"year={year}/month={month}/day={day}/{version}/{filename}"
            )
        else:
            path = (
                f"s3://{config.bucket}/"
                f"year={year}/month={month}/day={day}/{version}/{filename}"
            )

        return path

    def _validate_path_component(self, component: str, name: str) -> None:
        """Validate S3 path component for safety.

        Args:
            component: Path component to validate
            name: Name of component for error messages

        Raises:
            ValueError: If component contains path traversal or invalid chars
        """
        if not component:
            raise ValueError(f"{name} cannot be empty")

        # Check for path traversal
        if ".." in component or component.startswith("/"):
            raise ValueError(f"Path traversal detected in {name}: {component}")

        # Check for invalid characters (allow alphanumeric, underscore, hyphen, dot)
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", component):
            raise ValueError(f"Invalid characters in {name}: {component}")


class S3Uploader:
    """Handles S3 uploads with versioning.

    Creates boto3 S3 client and uploads content to S3 with automatic path
    construction including version timestamps.

    Attributes:
        config: S3 configuration
        s3_client: Boto3 S3 client
        path_builder: S3PathBuilder instance

    Example:
        >>> config = S3Configuration("my-bucket", "raw-data")
        >>> uploader = S3Uploader(config)
        >>> s3_path, version, etag = uploader.upload(
        ...     content=b"data",
        ...     filename="file.json",
        ...     file_date=date(2025, 12, 15),
        ...     version="20251215113400Z"
        ... )
    """

    def __init__(self, config: S3Configuration) -> None:
        """Initialize S3 uploader.

        Args:
            config: S3 configuration

        Example:
            >>> config = S3Configuration("bucket", "prefix")
            >>> uploader = S3Uploader(config)
        """
        self.config: S3Configuration = config
        self.s3_client = boto3.client("s3")
        self.path_builder = S3PathBuilder()

    def upload(
        self,
        content: bytes,
        filename: str,
        file_date: date,
        version: str
    ) -> Tuple[str, str, str]:
        """Upload content to S3 with versioning.

        Args:
            content: Raw content bytes
            filename: File name
            file_date: Date for partitioning
            version: Version timestamp (format: YYYYMMDDHHMMSSZ)

        Returns:
            Tuple of (s3_path, version, etag)

        Raises:
            ValueError: If version format is invalid
            Exception: If S3 upload fails

        Example:
            >>> uploader = S3Uploader(S3Configuration("bucket", "prefix"))
            >>> s3_path, ver, etag = uploader.upload(
            ...     content=b"data",
            ...     filename="file.json",
            ...     file_date=date(2025, 12, 15),
            ...     version="20251215113400Z"
            ... )
        """
        # Validate version format
        if not validate_version_format(version):
            raise ValueError(
                f"Invalid version format: {version}. "
                "Expected format: YYYYMMDDHHMMSSZ (e.g., 20251215113400Z)"
            )

        # Build S3 path
        s3_path = self.path_builder.build_path(
            config=self.config,
            filename=filename,
            file_date=file_date,
            version=version
        )

        # Parse S3 path
        path_parts = s3_path.replace("s3://", "").split("/", 1)
        bucket = path_parts[0]
        key = path_parts[1]

        logger.debug(
            "Uploading to S3",
            extra={
                "bucket": bucket,
                "key": key,
                "size": len(content),
                "version": version
            }
        )

        try:
            # Upload to S3
            response = self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=content
            )

            etag = response.get("ETag", "").strip('"')

            logger.info(
                "Successfully uploaded to S3",
                extra={
                    "s3_path": s3_path,
                    "etag": etag,
                    "version": version
                }
            )

            return s3_path, version, etag

        except Exception as e:
            logger.error(
                f"Failed to upload to S3: {e}",
                extra={"s3_path": s3_path, "version": version},
                exc_info=True
            )
            raise Exception(f"Failed to upload to S3 {s3_path}: {e}") from e
