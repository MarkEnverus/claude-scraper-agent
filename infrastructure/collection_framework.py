"""Generic collection framework for all scraper types.

This module provides the base infrastructure for building data collection scrapers.
It implements common patterns for downloading, deduplicating, storing, and notifying
about collected data.

Example:
    >>> class MyCollector(BaseCollector):
    ...     def generate_candidates(self, start_date, end_date):
    ...         # Return list of DownloadCandidate objects
    ...         pass
    ...
    ...     def collect_content(self, candidate):
    ...         # Download content via HTTP/FTP/etc.
    ...         return content_bytes
    ...
    >>> collector = MyCollector(dgroup='my_data', s3_bucket='bucket', ...)
    >>> results = collector.run_collection(start_date=..., end_date=...)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TypedDict, Tuple, cast
from dataclasses import dataclass
from datetime import datetime, date, UTC
# Note: Files are stored in original format (not gzipped) to preserve original file integrity
import hashlib
import logging
import re

from sourcing.scraping.commons.hash_registry import HashRegistry
from sourcing.exceptions import ScrapingError
from sourcing.scraping.commons.s3_utils import S3Configuration, S3Uploader

logger = logging.getLogger("sourcing_app")


@dataclass
class DownloadCandidate:
    """Generic candidate for any collection method.

    Represents a single resource to be collected (file, API endpoint, etc.).

    Attributes:
        identifier: Unique filename for this resource
        source_location: Where to collect from (URL, FTP path, etc.)
        metadata: Source-specific metadata (data_type, timestamps, etc.)
        collection_params: Collection-specific parameters (headers, query params, etc.)
        file_date: Date for S3 partitioning (year/month/day)

    Example:
        >>> candidate = DownloadCandidate(
        ...     identifier='load_20250120_14.json',
        ...     source_location='https://api.nyiso.com/v1/load',
        ...     metadata={'data_type': 'load_forecast', 'source': 'nyiso'},
        ...     collection_params={'query_params': {'date': '2025-01-20', 'hour': 14}},
        ...     file_date=date(2025, 1, 20)
        ... )
    """
    identifier: str
    source_location: str
    metadata: Dict[str, Any]
    collection_params: Dict[str, Any]
    file_date: date


class CollectionResults(TypedDict):
    """Type definition for collection run results.

    Attributes:
        total_candidates: Total number of candidates generated
        collected: Number of candidates successfully collected
        skipped_duplicate: Number of candidates skipped (hash exists)
        failed: Number of candidates that failed collection
        errors: List of error details for failed candidates
    """
    total_candidates: int
    collected: int
    skipped_duplicate: int
    failed: int
    errors: List[Dict[str, str]]


class BaseCollector(ABC):
    """Abstract base for all collection types.

    Provides common infrastructure for Redis hash deduplication, S3 storage
    with date partitioning, Kafka notifications, and error handling.

    Subclasses must implement:
        - generate_candidates(): Create list of resources to collect
        - collect_content(): Download/collect content for a candidate

    Subclasses may override:
        - validate_content(): Custom content validation logic

    Attributes:
        dgroup: Data group identifier (e.g., 'nyiso_load_forecast')
        s3_bucket: S3 bucket name
        s3_prefix: S3 prefix (typically 'sourcing')
        environment: Environment name (dev/staging/prod)
        hash_registry: HashRegistry instance for deduplication
        s3_client: Boto3 S3 client
        kafka_connection_string: Optional Kafka connection string for notifications
    """

    def __init__(
        self,
        dgroup: str,
        s3_bucket: str,
        s3_prefix: str,
        redis_client,
        environment: str,
        kafka_connection_string: Optional[str] = None,
        hash_ttl_days: int = 365
    ):
        """Initialize base collector.

        Args:
            dgroup: Data group identifier (e.g., 'nyiso_load_forecast')
            s3_bucket: S3 bucket name
            s3_prefix: S3 prefix (typically 'sourcing')
            redis_client: Redis client instance
            environment: Environment (dev/staging/prod)
            kafka_connection_string: Optional Kafka connection string
            hash_ttl_days: Hash registry TTL in days (default 365)
        """
        self.dgroup = dgroup

        # Validate dgroup parameter
        if not dgroup:
            raise ValueError("dgroup cannot be empty")

        if not re.match(r'^[a-z0-9_]+$', dgroup):
            raise ValueError(
                f"Invalid dgroup '{dgroup}'. "
                "Only lowercase letters, numbers, and underscores allowed."
            )

        # Initialize S3 configuration and uploader
        try:
            s3_config = S3Configuration(s3_bucket, s3_prefix)
            self.s3_uploader = S3Uploader(s3_config)
        except ValueError as e:
            raise ValueError(f"Invalid S3 configuration: {e}") from e

        # Keep references for backwards compatibility
        self.s3_bucket = s3_config.bucket
        self.s3_prefix = s3_config.prefix

        self.environment = environment
        self.hash_registry = HashRegistry(redis_client, environment, hash_ttl_days)
        self.kafka_connection_string = kafka_connection_string

    @abstractmethod
    def generate_candidates(self, **kwargs) -> List[DownloadCandidate]:
        """Generate list of resources to collect.

        Override this method to implement collection-specific logic for
        determining what files/resources to download.

        Args:
            **kwargs: Collection-specific parameters (e.g., start_date, end_date)

        Returns:
            List of DownloadCandidate objects

        Example:
            >>> def generate_candidates(self, start_date, end_date):
            ...     candidates = []
            ...     current = start_date
            ...     while current < end_date:
            ...         candidates.append(DownloadCandidate(...))
            ...         current += timedelta(hours=1)
            ...     return candidates
        """
        pass

    @abstractmethod
    def collect_content(self, candidate: DownloadCandidate) -> bytes:
        """Collect content from source.

        Override this method to implement collection-type-specific logic
        (HTTP GET, FTP download, website parsing, etc.).

        Args:
            candidate: Candidate to collect

        Returns:
            Raw content as bytes

        Raises:
            ScrapingError: If collection fails

        Example:
            >>> def collect_content(self, candidate):
            ...     response = requests.get(
            ...         candidate.source_location,
            ...         params=candidate.collection_params['query_params'],
            ...         timeout=30
            ...     )
            ...     response.raise_for_status()
            ...     return response.content
        """
        pass

    def validate_content(self, content: bytes, candidate: DownloadCandidate) -> bool:
        """Validate collected content.

        Override this method for custom validation logic (JSON structure,
        CSV format, required fields, etc.).

        Default implementation checks for non-empty content.

        Args:
            content: Collected content
            candidate: Candidate that was collected

        Returns:
            True if valid, False otherwise

        Example:
            >>> def validate_content(self, content, candidate):
            ...     try:
            ...         data = json.loads(content)
            ...         return 'forecast' in data and 'timestamp' in data
            ...     except json.JSONDecodeError:
            ...         return False
        """
        return len(content) > 0

    def _build_s3_path(self, candidate: DownloadCandidate) -> str:
        """Build S3 path with date partitioning.

        DEPRECATED: This method is deprecated and will be removed in v2.0.
        Path building now handled by S3Uploader.upload().

        Format: s3://{bucket}/{prefix}/{dgroup}/year={YYYY}/month={MM}/day={DD}/{filename}

        Args:
            candidate: Candidate with file_date

        Returns:
            Full S3 path (legacy format)

        Example:
            >>> path = self._build_s3_path(candidate)
            >>> # s3://bucket/sourcing/nyiso_load/year=2025/month=01/day=20/load_20250120_14.json
        """
        import warnings
        warnings.warn(
            "_build_s3_path is deprecated and will be removed in v2.0. "
            "Use S3Uploader.upload() instead.",
            DeprecationWarning,
            stacklevel=2
        )

        year = candidate.file_date.year
        month = f"{candidate.file_date.month:02d}"
        day = f"{candidate.file_date.day:02d}"

        # Use original filename (no .gz extension)
        filename = candidate.identifier

        return (
            f"s3://{self.s3_bucket}/{self.s3_prefix}/{self.dgroup}/"
            f"year={year}/month={month}/day={day}/{filename}"
        )

    def _upload_to_s3(
        self,
        content: bytes,
        candidate: DownloadCandidate,
        version: str
    ) -> Tuple[str, str, str]:
        """Upload content to S3 with versioning.

        Args:
            content: Raw content bytes
            candidate: Download candidate with filename and file_date
            version: Version timestamp (format: YYYYMMDDHHMMSSZ)

        Returns:
            Tuple of (s3_path, version, etag)

        Raises:
            ScrapingError: If upload fails
        """
        try:
            result = self.s3_uploader.upload(
                content=content,
                filename=candidate.identifier,
                file_date=candidate.file_date,
                version=version
            )
            return cast(Tuple[str, str, str], result)
        except Exception as e:
            raise ScrapingError(f"Failed to upload to S3: {e}") from e

    def _publish_kafka_notification(
        self,
        candidate: DownloadCandidate,
        s3_path: str,
        content_hash: str,
        original_size: int,
        etag: str,
        version: str
    ):
        """Publish notification to Kafka.

        Follows existing ScraperNotificationMessage pattern from fetching_http.py

        Args:
            candidate: Original candidate
            s3_path: S3 location of stored file
            content_hash: SHA256 hash of content
            original_size: Original file size in bytes
            etag: S3 ETag
            version: Version timestamp (format: YYYYMMDDHHMMSSZ)
        """
        if not self.kafka_connection_string:
            logger.debug("Kafka connection not configured, skipping notification")
            return

        try:
            # Import here to avoid circular dependency
            from sourcing.scraping.commons.kafka_utils import (
                KafkaConfiguration,
                KafkaProducer,
                ScraperNotificationMessage
            )

            kafka_config = KafkaConfiguration(self.kafka_connection_string)

            # Build message following existing pattern
            message = ScraperNotificationMessage(
                dataset=self.dgroup,
                environment=self.environment,
                urn=candidate.identifier,
                location=s3_path,
                version=version,  # Use version from S3 upload
                etag=etag,
                metadata={
                    "publish_dtm": datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
                    "s3_guid": hashlib.sha256(
                        f"{s3_path}{datetime.now(UTC).isoformat().replace('+00:00', 'Z')}".encode()
                    ).hexdigest(),
                    "url": candidate.source_location,
                    "original_file_size": original_size,
                    "original_file_md5sum": content_hash,
                    **candidate.metadata
                }
            )

            with KafkaProducer(kafka_config) as producer:
                producer.publish(message)

            logger.info(
                "Published Kafka notification",
                extra={
                    "topic": kafka_config.topic,
                    "urn": candidate.identifier
                }
            )

        except Exception as e:
            logger.error(
                f"Failed to publish Kafka notification: {e}",
                extra={"candidate": candidate.identifier},
                exc_info=True
            )
            # Don't fail the entire collection on Kafka errors

    def run_collection(
        self,
        version: str,
        force: bool = False,
        skip_hash_check: bool = False,
        **candidate_params
    ) -> CollectionResults:
        """Main collection loop.

        Orchestrates the complete collection process:
        1. Generate candidates
        2. For each candidate:
           - Collect content
           - Validate content
           - Check hash deduplication (unless skip_hash_check)
           - Upload to S3 with version
           - Publish Kafka notification
           - Register hash in Redis

        Args:
            version: Version timestamp (format: YYYYMMDDHHMMSSZ)
            force: Force re-download even if hash exists
            skip_hash_check: Skip hash checking entirely (for testing)
            **candidate_params: Parameters passed to generate_candidates()

        Returns:
            Summary dict with collection statistics:
            {
                "total_candidates": int,
                "collected": int,
                "skipped_duplicate": int,
                "failed": int,
                "errors": [{"candidate": str, "error": str}, ...]
            }

        Example:
            >>> results = collector.run_collection(
            ...     version="20251215113400Z",
            ...     start_date=datetime(2025, 1, 20),
            ...     end_date=datetime(2025, 1, 21),
            ...     force=False
            ... )
            >>> print(f"Collected {results['collected']} files")
            >>> print(f"Skipped {results['skipped_duplicate']} duplicates")
        """

        logger.info(
            "Starting collection",
            extra={
                "dgroup": self.dgroup,
                "environment": self.environment,
                "force": force,
                "skip_hash_check": skip_hash_check
            }
        )

        # Generate candidates
        try:
            candidates = self.generate_candidates(**candidate_params)
            logger.info(f"Generated {len(candidates)} candidates")
        except Exception as e:
            logger.error(f"Failed to generate candidates: {e}", exc_info=True)
            return {
                "total_candidates": 0,
                "collected": 0,
                "skipped_duplicate": 0,
                "failed": 0,
                "errors": [{"candidate": "generation", "error": str(e)}]
            }

        results: CollectionResults = {
            "total_candidates": len(candidates),
            "collected": 0,
            "skipped_duplicate": 0,
            "failed": 0,
            "errors": []
        }

        for candidate in candidates:
            try:
                # Collect content
                content = self.collect_content(candidate)

                # Validate
                if not self.validate_content(content, candidate):
                    results["failed"] += 1
                    results["errors"].append({
                        "candidate": candidate.identifier,
                        "error": "Content validation failed"
                    })
                    logger.warning(
                        "Content validation failed",
                        extra={"candidate": candidate.identifier}
                    )
                    continue

                # Calculate hash
                content_hash = self.hash_registry.calculate_hash(content)

                # Check if exists (unless forced or skipped)
                if not force and not skip_hash_check:
                    if self.hash_registry.exists(content_hash, self.dgroup):
                        logger.debug(
                            "Skipping duplicate",
                            extra={
                                "candidate": candidate.identifier,
                                "hash": content_hash[:16] + "..."
                            }
                        )
                        results["skipped_duplicate"] += 1
                        continue

                # Store in S3 with version
                s3_path, version_returned, etag = self._upload_to_s3(
                    content, candidate, version
                )

                # Publish Kafka notification
                self._publish_kafka_notification(
                    candidate, s3_path, content_hash, len(content), etag, version
                )

                # Register hash
                self.hash_registry.register(
                    content_hash,
                    self.dgroup,
                    s3_path,
                    {
                        **candidate.metadata,
                        "version": version,
                        "etag": etag
                    }
                )

                results["collected"] += 1

                logger.info(
                    "Successfully collected",
                    extra={
                        "candidate": candidate.identifier,
                        "hash": content_hash[:16] + "...",
                        "s3_path": s3_path
                    }
                )

            except Exception as e:
                logger.error(
                    "Collection failed",
                    extra={
                        "candidate": candidate.identifier,
                        "error": str(e)
                    },
                    exc_info=True
                )
                results["failed"] += 1
                results["errors"].append({
                    "candidate": candidate.identifier,
                    "error": str(e)
                })

        logger.info(
            "Collection complete",
            extra=results
        )

        return results
