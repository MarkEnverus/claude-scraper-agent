---
description: Core scraper creation logic and templates
---

# Scraper Creation Skill

This skill provides reusable templates and patterns for scraper generation.

## Standard File Structure

```
sourcing/scraping/{source}/
├── __init__.py
├── scraper_{source}_{type}_{method}.py
├── README.md
└── tests/
    ├── __init__.py
    ├── test_scraper_{source}_{type}_{method}.py
    ├── conftest.py
    └── fixtures/
        └── sample_response.{format}
```

## Standard Imports

```python
# Standard library
import os
from datetime import datetime, timedelta, date
from typing import List, Dict, Any

# Third-party
import click
import redis
import requests  # or other collection library

# Internal
from sourcing.scraping.commons.collection_framework import (
    BaseCollector,
    DownloadCandidate
)
from sourcing.common.logging_json import setup_logging
```

## Standard CLI Flags

All scrapers should support:
- `--start-date` (required for historical)
- `--end-date` (required for historical)
- `--environment` (dev/staging/prod, default dev)
- `--force` (bypass hash check)
- `--skip-hash-check` (for testing)
- `--kafka-connection-string` (optional)
- `--log-level` (DEBUG/INFO/WARNING/ERROR, default INFO)

## Standard Environment Variables

- `{SOURCE}_API_KEY` - API authentication
- `REDIS_HOST` - Redis hostname
- `REDIS_PORT` - Redis port
- `REDIS_DB` - Redis database number
- `S3_BUCKET` - S3 bucket name
- `KAFKA_CONNECTION_STRING` - Kafka configuration

## Test Structure

```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date

# Test fixtures
@pytest.fixture
def mock_redis():
    return Mock()

@pytest.fixture
def collector(mock_redis):
    return MyCollector(
        api_key="test_key",
        s3_bucket="test-bucket",
        s3_prefix="sourcing",
        redis_client=mock_redis,
        environment="dev"
    )

# Test cases
def test_generate_candidates(collector):
    \"\"\"Test candidate generation.\"\"\"
    start = datetime(2025, 1, 1)
    end = datetime(2025, 1, 2)
    candidates = collector.generate_candidates(start, end)
    assert len(candidates) > 0
    assert all(isinstance(c, DownloadCandidate) for c in candidates)

@patch('requests.get')
def test_collect_content_success(mock_get, collector):
    \"\"\"Test successful content collection.\"\"\"
    mock_response = Mock()
    mock_response.content = b'{"data": "test"}'
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    candidate = DownloadCandidate(
        identifier='test.json',
        source_location='https://api.test.com',
        metadata={},
        collection_params={'query_params': {}},
        file_date=date(2025, 1, 1)
    )

    content = collector.collect_content(candidate)
    assert content == b'{"data": "test"}'
```

## README Template

````markdown
# {SOURCE} {DATA_TYPE} Scraper

Auto-generated scraper for {SOURCE} {DATA_TYPE} data.

## Overview

- **Source**: {SOURCE}
- **Data Type**: {DATA_TYPE}
- **Collection Method**: {METHOD}
- **Update Frequency**: {FREQUENCY}
- **Data Format**: {FORMAT}

## Installation

```bash
pip install redis boto3 click requests
```

## Configuration

### Environment Variables

```bash
export {SOURCE}_API_KEY=your_api_key_here
export REDIS_HOST=localhost
export REDIS_PORT=6379
export S3_BUCKET=your-bucket-name
```

## Usage

### Collect Data

```bash
python scraper_{source}_{type}_{method}.py \
  --start-date 2025-01-20 \
  --end-date 2025-01-21 \
  --environment dev
```

### Force Re-download

```bash
python scraper_{source}_{type}_{method}.py \
  --start-date 2025-01-20 \
  --end-date 2025-01-21 \
  --force
```

## S3 Storage

Files are stored with date partitioning:

```
s3://{bucket}/sourcing/{source}_{type}/year=YYYY/month=MM/day=DD/{filename}.gz
```

## Redis Keys

Hash deduplication uses:

```
hash:{env}:{source}_{type}:{sha256_hash}
```

## Testing

```bash
pytest tests/ -v --cov
```

## Troubleshooting

### Redis Connection Error
Ensure Redis is running: `redis-cli ping`

### S3 Upload Error
Check AWS credentials: `aws sts get-caller-identity`

### API Authentication Error
Verify API key is set: `echo ${{SOURCE}}_API_KEY`
````
