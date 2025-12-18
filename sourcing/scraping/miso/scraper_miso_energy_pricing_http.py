"""MISO Energy Pricing API HTTP Collector.

This scraper collects energy pricing data from the MISO Energy Data Exchange API.
It handles 12 different endpoints covering Day-Ahead and Real-Time markets for
LMP (Locational Marginal Pricing), MCP (Marginal Congestion Pricing), and
MCC (Marginal Congestion Component) data.

Data Source: MISO Energy
API Base URL: https://data-exchange.misoenergy.org
Authentication: API Key (Ocp-Apim-Subscription-Key header)

Endpoints Collected:
    Day-Ahead Markets:
        - LMP Ex-Ante (DA_EXANTE_LMP)
        - LMP Ex-Post (DA_EXPOST_LMP)
        - MCP Ex-Ante (DA_EXANTE_MCP)
        - MCP Ex-Post (DA_EXPOST_MCP)
        - MCC Ex-Ante (DA_EXANTE_MCC)
        - MCC Ex-Post (DA_EXPOST_MCC)

    Real-Time Markets:
        - LMP 5-Minute (RT_LMP)
        - LMP Hourly (RT_LMP_Hourly)
        - MCP 5-Minute (RT_MCP)
        - MCP Hourly (RT_MCP_Hourly)
        - MCC 5-Minute (RT_MCC)
        - MCC Hourly (RT_MCC_Hourly)

Usage:
    python scraper_miso_energy_pricing_http.py \\
        --start-date 2025-01-01 \\
        --end-date 2025-01-02 \\
        --redis-host localhost \\
        --redis-port 6379 \\
        --s3-bucket my-bucket \\
        --s3-prefix sourcing \\
        --environment dev

Environment Variables:
    MISO_API_KEY: Required. MISO API subscription key.

Example:
    export MISO_API_KEY=72575d06948f460993e3fca6ee68a4da
    python scraper_miso_energy_pricing_http.py \\
        --start-date 2025-01-15 --end-date 2025-01-16
"""

import os
import sys
import logging
from datetime import datetime, timedelta, date, UTC
from typing import List, Dict, Any
import json

import click
import redis
import requests

# Add parent directories to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from sourcing.scraping.commons.collection_framework import (
    BaseCollector,
    DownloadCandidate,
    CollectionResults
)
from sourcing.common.logging_json import setup_logging
from sourcing.exceptions import ScrapingError

logger = logging.getLogger("sourcing_app")


# Endpoint configuration for all 12 MISO pricing endpoints
MISO_ENDPOINTS = [
    # Day-Ahead LMP
    {
        "name": "DA_EXANTE_LMP",
        "display_name": "Day-Ahead Ex-Ante LMP",
        "path": "/api/v1/da/{date}/exante/lmp",
        "market_type": "day-ahead",
        "data_type": "lmp",
        "timing": "ex-ante"
    },
    {
        "name": "DA_EXPOST_LMP",
        "display_name": "Day-Ahead Ex-Post LMP",
        "path": "/api/v1/da/{date}/expost/lmp",
        "market_type": "day-ahead",
        "data_type": "lmp",
        "timing": "ex-post"
    },
    # Day-Ahead MCP
    {
        "name": "DA_EXANTE_MCP",
        "display_name": "Day-Ahead Ex-Ante MCP",
        "path": "/api/v1/da/{date}/exante/mcp",
        "market_type": "day-ahead",
        "data_type": "mcp",
        "timing": "ex-ante"
    },
    {
        "name": "DA_EXPOST_MCP",
        "display_name": "Day-Ahead Ex-Post MCP",
        "path": "/api/v1/da/{date}/expost/mcp",
        "market_type": "day-ahead",
        "data_type": "mcp",
        "timing": "ex-post"
    },
    # Day-Ahead MCC
    {
        "name": "DA_EXANTE_MCC",
        "display_name": "Day-Ahead Ex-Ante MCC",
        "path": "/api/v1/da/{date}/exante/mcc",
        "market_type": "day-ahead",
        "data_type": "mcc",
        "timing": "ex-ante"
    },
    {
        "name": "DA_EXPOST_MCC",
        "display_name": "Day-Ahead Ex-Post MCC",
        "path": "/api/v1/da/{date}/expost/mcc",
        "market_type": "day-ahead",
        "data_type": "mcc",
        "timing": "ex-post"
    },
    # Real-Time LMP
    {
        "name": "RT_LMP",
        "display_name": "Real-Time 5-Minute LMP",
        "path": "/api/v1/rt/{date}/5min/lmp",
        "market_type": "real-time",
        "data_type": "lmp",
        "timing": "5-minute"
    },
    {
        "name": "RT_LMP_Hourly",
        "display_name": "Real-Time Hourly LMP",
        "path": "/api/v1/rt/{date}/hourly/lmp",
        "market_type": "real-time",
        "data_type": "lmp",
        "timing": "hourly"
    },
    # Real-Time MCP
    {
        "name": "RT_MCP",
        "display_name": "Real-Time 5-Minute MCP",
        "path": "/api/v1/rt/{date}/5min/mcp",
        "market_type": "real-time",
        "data_type": "mcp",
        "timing": "5-minute"
    },
    {
        "name": "RT_MCP_Hourly",
        "display_name": "Real-Time Hourly MCP",
        "path": "/api/v1/rt/{date}/hourly/mcp",
        "market_type": "real-time",
        "data_type": "mcp",
        "timing": "hourly"
    },
    # Real-Time MCC
    {
        "name": "RT_MCC",
        "display_name": "Real-Time 5-Minute MCC",
        "path": "/api/v1/rt/{date}/5min/mcc",
        "market_type": "real-time",
        "data_type": "mcc",
        "timing": "5-minute"
    },
    {
        "name": "RT_MCC_Hourly",
        "display_name": "Real-Time Hourly MCC",
        "path": "/api/v1/rt/{date}/hourly/mcc",
        "market_type": "real-time",
        "data_type": "mcc",
        "timing": "hourly"
    }
]


class MISOEnergyPricingCollector(BaseCollector):
    """HTTP collector for MISO Energy Pricing API.

    Collects energy pricing data from all 12 MISO endpoints covering Day-Ahead
    and Real-Time markets for LMP, MCP, and MCC data types.

    Attributes:
        api_key: MISO API subscription key for authentication
        base_url: Base URL for MISO API (https://data-exchange.misoenergy.org)
        session: Requests session with configured headers
        timeout: HTTP request timeout in seconds
    """

    def __init__(
        self,
        dgroup: str,
        s3_bucket: str,
        s3_prefix: str,
        redis_client,
        environment: str,
        api_key: str,
        kafka_connection_string: str | None = None,
        hash_ttl_days: int = 365,
        timeout: int = 30
    ):
        """Initialize MISO Energy Pricing collector.

        Args:
            dgroup: Data group identifier (e.g., 'miso_energy_pricing')
            s3_bucket: S3 bucket name
            s3_prefix: S3 prefix (typically 'sourcing')
            redis_client: Redis client instance
            environment: Environment (dev/staging/prod)
            api_key: MISO API subscription key
            kafka_connection_string: Optional Kafka connection string
            hash_ttl_days: Hash registry TTL in days (default 365)
            timeout: HTTP request timeout in seconds (default 30)

        Raises:
            ValueError: If API key is empty
        """
        super().__init__(
            dgroup=dgroup,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            redis_client=redis_client,
            environment=environment,
            kafka_connection_string=kafka_connection_string,
            hash_ttl_days=hash_ttl_days
        )

        if not api_key:
            raise ValueError("MISO API key is required")

        self.api_key = api_key
        self.base_url = "https://data-exchange.misoenergy.org"
        self.timeout = timeout

        # Setup requests session with authentication
        self.session = requests.Session()
        self.session.headers.update({
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Accept": "application/json",
            "User-Agent": "MISO-Energy-Pricing-Collector/1.0"
        })

    def generate_candidates(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[DownloadCandidate]:
        """Generate download candidates for all endpoints and date range.

        Creates candidates for each combination of endpoint and date in the
        specified range. Each candidate represents one API call for a specific
        endpoint and date.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (exclusive)

        Returns:
            List of DownloadCandidate objects

        Example:
            >>> candidates = collector.generate_candidates(
            ...     start_date=datetime(2025, 1, 15),
            ...     end_date=datetime(2025, 1, 16)
            ... )
            >>> len(candidates)  # 12 endpoints * 1 day = 12 candidates
            12
        """
        candidates = []
        current = start_date.date()
        end = end_date.date()

        logger.info(
            "Generating candidates for MISO Energy Pricing",
            extra={
                "start_date": current.isoformat(),
                "end_date": end.isoformat(),
                "endpoint_count": len(MISO_ENDPOINTS)
            }
        )

        while current < end:
            date_str = current.strftime("%Y-%m-%d")

            # Generate candidate for each endpoint
            for endpoint in MISO_ENDPOINTS:
                # Build endpoint path with date parameter
                endpoint_path = endpoint["path"].format(date=date_str)
                full_url = f"{self.base_url}{endpoint_path}"

                # Build identifier with endpoint name and date
                identifier = f"miso_{endpoint['name'].lower()}_{current.strftime('%Y%m%d')}.json"

                candidate = DownloadCandidate(
                    identifier=identifier,
                    source_location=full_url,
                    metadata={
                        "data_source": "miso",
                        "endpoint_name": endpoint["name"],
                        "endpoint_display": endpoint["display_name"],
                        "market_type": endpoint["market_type"],
                        "data_type": endpoint["data_type"],
                        "timing": endpoint["timing"],
                        "date": date_str,
                        "collection_timestamp": datetime.now(UTC).isoformat().replace('+00:00', 'Z')
                    },
                    collection_params={
                        "method": "GET",
                        "headers": {
                            "Ocp-Apim-Subscription-Key": self.api_key,
                            "Accept": "application/json"
                        }
                    },
                    file_date=current
                )

                candidates.append(candidate)

            current += timedelta(days=1)

        logger.info(
            f"Generated {len(candidates)} candidates",
            extra={
                "total_candidates": len(candidates),
                "date_count": (end - start_date.date()).days,
                "endpoint_count": len(MISO_ENDPOINTS)
            }
        )

        return candidates

    def collect_content(self, candidate: DownloadCandidate) -> bytes:
        """Collect content from MISO API endpoint.

        Makes HTTP GET request to the specified endpoint and returns raw JSON response.

        Args:
            candidate: Candidate with source_location (API URL) and collection_params

        Returns:
            Raw JSON response as bytes

        Raises:
            ScrapingError: If HTTP request fails or returns non-200 status
        """
        try:
            logger.debug(
                "Collecting from MISO API",
                extra={
                    "candidate": candidate.identifier,
                    "url": candidate.source_location
                }
            )

            response = self.session.get(
                candidate.source_location,
                timeout=self.timeout
            )

            # Check for HTTP errors
            if response.status_code != 200:
                raise ScrapingError(
                    f"HTTP {response.status_code}: {response.reason} "
                    f"for {candidate.source_location}"
                )

            content = response.content

            logger.debug(
                "Successfully collected content",
                extra={
                    "candidate": candidate.identifier,
                    "size_bytes": len(content),
                    "status_code": response.status_code
                }
            )

            return content

        except requests.exceptions.Timeout as e:
            raise ScrapingError(
                f"Request timeout after {self.timeout}s: {candidate.source_location}"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise ScrapingError(
                f"Connection error: {candidate.source_location}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise ScrapingError(
                f"Request failed: {candidate.source_location} - {e}"
            ) from e

    def validate_content(self, content: bytes, candidate: DownloadCandidate) -> bool:
        """Validate collected JSON content.

        Checks that content is valid JSON and not empty.

        Args:
            content: Raw content bytes
            candidate: Candidate that was collected

        Returns:
            True if valid JSON with data, False otherwise
        """
        if not content or len(content) == 0:
            logger.warning(
                "Empty content received",
                extra={"candidate": candidate.identifier}
            )
            return False

        try:
            # Validate JSON structure
            data = json.loads(content)

            # Check if data is present (not just empty object/array)
            if isinstance(data, dict) and len(data) == 0:
                logger.warning(
                    "Empty JSON object received",
                    extra={"candidate": candidate.identifier}
                )
                return False

            if isinstance(data, list) and len(data) == 0:
                logger.warning(
                    "Empty JSON array received",
                    extra={"candidate": candidate.identifier}
                )
                return False

            logger.debug(
                "Content validation passed",
                extra={
                    "candidate": candidate.identifier,
                    "data_type": type(data).__name__
                }
            )

            return True

        except json.JSONDecodeError as e:
            logger.error(
                "Invalid JSON content",
                extra={
                    "candidate": candidate.identifier,
                    "error": str(e)
                }
            )
            return False


@click.command()
@click.option(
    "--start-date",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD, inclusive)"
)
@click.option(
    "--end-date",
    required=True,
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD, exclusive)"
)
@click.option(
    "--redis-host",
    default="localhost",
    help="Redis host (default: localhost)"
)
@click.option(
    "--redis-port",
    default=6379,
    type=int,
    help="Redis port (default: 6379)"
)
@click.option(
    "--redis-db",
    default=0,
    type=int,
    help="Redis database number (default: 0)"
)
@click.option(
    "--s3-bucket",
    required=True,
    help="S3 bucket name"
)
@click.option(
    "--s3-prefix",
    default="sourcing",
    help="S3 prefix (default: sourcing)"
)
@click.option(
    "--environment",
    type=click.Choice(["dev", "staging", "prod"]),
    default="dev",
    help="Environment (default: dev)"
)
@click.option(
    "--dgroup",
    default="miso_energy_pricing",
    help="Data group identifier (default: miso_energy_pricing)"
)
@click.option(
    "--kafka-connection",
    default=None,
    help="Kafka connection string (optional)"
)
@click.option(
    "--force",
    is_flag=True,
    help="Force re-download even if hash exists"
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Log level (default: INFO)"
)
@click.option(
    "--timeout",
    default=30,
    type=int,
    help="HTTP request timeout in seconds (default: 30)"
)
def main(
    start_date: datetime,
    end_date: datetime,
    redis_host: str,
    redis_port: int,
    redis_db: int,
    s3_bucket: str,
    s3_prefix: str,
    environment: str,
    dgroup: str,
    kafka_connection: str | None,
    force: bool,
    log_level: str,
    timeout: int
):
    """MISO Energy Pricing API HTTP Collector.

    Collects energy pricing data from all 12 MISO endpoints for the specified
    date range. Data includes Day-Ahead and Real-Time markets for LMP, MCP,
    and MCC pricing data.

    Required Environment Variables:
        MISO_API_KEY: MISO API subscription key

    Example:
        export MISO_API_KEY=72575d06948f460993e3fca6ee68a4da

        python scraper_miso_energy_pricing_http.py \\
            --start-date 2025-01-15 \\
            --end-date 2025-01-16 \\
            --s3-bucket my-bucket \\
            --environment dev
    """
    # Setup logging
    setup_logging(level=log_level, use_json=True)

    logger.info(
        "Starting MISO Energy Pricing collection",
        extra={
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "environment": environment,
            "dgroup": dgroup,
            "s3_bucket": s3_bucket,
            "force": force
        }
    )

    # Get API key from environment
    api_key = os.getenv("MISO_API_KEY")
    if not api_key:
        logger.error("MISO_API_KEY environment variable not set")
        sys.exit(1)

    # Connect to Redis
    try:
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False
        )
        redis_client.ping()
        logger.info(
            "Connected to Redis",
            extra={
                "host": redis_host,
                "port": redis_port,
                "db": redis_db
            }
        )
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        sys.exit(1)

    # Initialize collector
    try:
        collector = MISOEnergyPricingCollector(
            dgroup=dgroup,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            redis_client=redis_client,
            environment=environment,
            api_key=api_key,
            kafka_connection_string=kafka_connection,
            timeout=timeout
        )
    except ValueError as e:
        logger.error(f"Failed to initialize collector: {e}")
        sys.exit(1)

    # Generate version timestamp
    version = datetime.now(UTC).strftime("%Y%m%d%H%M%SZ")

    # Run collection
    try:
        results: CollectionResults = collector.run_collection(
            version=version,
            force=force,
            start_date=start_date,
            end_date=end_date
        )

        logger.info(
            "Collection completed",
            extra={
                "total_candidates": results["total_candidates"],
                "collected": results["collected"],
                "skipped_duplicate": results["skipped_duplicate"],
                "failed": results["failed"],
                "error_count": len(results["errors"])
            }
        )

        # Print summary
        print("\nCollection Summary:")
        print(f"  Total candidates: {results['total_candidates']}")
        print(f"  Successfully collected: {results['collected']}")
        print(f"  Skipped (duplicate): {results['skipped_duplicate']}")
        print(f"  Failed: {results['failed']}")

        if results["errors"]:
            print("\nErrors:")
            for error in results["errors"][:10]:  # Show first 10 errors
                print(f"  - {error['candidate']}: {error['error']}")
            if len(results["errors"]) > 10:
                print(f"  ... and {len(results['errors']) - 10} more errors")

        # Exit with error code if any failures
        if results["failed"] > 0:
            sys.exit(1)

    except Exception as e:
        logger.error(
            "Collection failed with exception",
            extra={"error": str(e)},
            exc_info=True
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
