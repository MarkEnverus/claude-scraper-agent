# MISO Energy_pricing Data Collector

Automated data collector for MISO energy_pricing data.

## Overview

This scraper collects energy_pricing data from MISO using their HTTP_REST_API interface.

- **Data Source**: MISO
- **API Base URL**: https://api.misoenergy.org
- **Authentication**: API_KEY
- **Data Format**: JSON
- **Update Frequency**: hourly
- **Historical Data**: Supported

## Features

- ✅ Automated data collection with retry logic
- ✅ Content deduplication using Redis hash registry
- ✅ S3 storage with date partitioning (YYYY/MM/DD)
- ✅ Kafka notifications for real-time data pipelines
- ✅ Comprehensive error handling and logging
- ✅ CLI interface with flexible configuration

## Data Endpoints

This scraper collects data from 2 endpoints:

### 1. Day-ahead ex-ante locational marginal pricing data

- **Endpoint ID**: `da_exante_lmp`
- **Path**: `/api/v1/da/{date}/exante/lmp`
- **Method**: `GET`
- **Description**: Day-ahead ex-ante locational marginal pricing data
- **Parameters**: {"date": {"description": "Date for which to retrieve LMP data", "format": "YYYY-MM-DD", "required": true, "type": "string"}}

### 2. Real-time 5-minute locational marginal pricing data

- **Endpoint ID**: `rt_lmp`
- **Path**: `/api/v1/rt/{date}/lmp`
- **Method**: `GET`
- **Description**: Real-time 5-minute locational marginal pricing data
- **Parameters**: {"date": {"format": "YYYY-MM-DD", "required": true, "type": "string"}}


## Installation

### Prerequisites

- Python 3.11+
- Redis (for hash registry)
- AWS credentials (for S3 storage)
- Kafka cluster (optional, for notifications)

### Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `click` - CLI interface
- `redis` - Hash registry
- `boto3` - S3 storage
- `kafka-python` - Kafka notifications
- `requests` - HTTP client

## Configuration

### Environment Variables

Set these environment variables or pass as CLI options:

| Variable | Required | Description |
|----------|----------|-------------|
| `MISO_API_KEY` | Yes | API_KEY authentication key |
| `REDIS_HOST` | No | Redis host (default: localhost) |
| `REDIS_PORT` | No | Redis port (default: 6379) |
| `S3_BUCKET` | Yes | S3 bucket for data storage |
| `KAFKA_BOOTSTRAP_SERVERS` | No | Kafka servers (comma-separated) |
| `KAFKA_TOPIC` | No | Kafka topic (default: miso_energy_pricing) |

### Authentication

This scraper requires authentication via API_KEY.

**API Key Setup:**

1. Register for API access at MISO
2. Obtain your API key
3. Set environment variable:
   ```bash
   export MISO_API_KEY="your-api-key-here"
   ```

The API key is sent in the `Ocp-Apim-Subscription-Key` header.


## Usage

### Command Line

Basic usage:

```bash
python scraper_miso_energy_pricing_http.py \
    --start-date 2025-01-01 \
    --end-date 2025-01-31 \
    --api-key YOUR_API_KEY \
    --s3-bucket your-bucket-name \
    --kafka-bootstrap-servers localhost:9092
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--start-date` | Start date for data collection (YYYY-MM-DD) |
| `--end-date` | End date for data collection (YYYY-MM-DD) |
| `--api-key` | API_KEY authentication key |
| `--redis-host` | Redis host (default: localhost) |
| `--redis-port` | Redis port (default: 6379) |
| `--s3-bucket` | S3 bucket for data storage (required) |
| `--kafka-bootstrap-servers` | Kafka servers (comma-separated) |
| `--kafka-topic` | Kafka topic for notifications |
| `--dgroup` | Data group identifier (default: miso_energy_pricing) |
| `--debug` | Enable debug logging |

### Examples

**Collect data for a single day:**

```bash
python scraper_miso_energy_pricing_http.py \
    --start-date 2025-12-19 \
    --end-date 2025-12-19 \
    --api-key $MISO_API_KEY \
    --s3-bucket production-data
```

**Collect historical data with debug logging:**

```bash
python scraper_miso_energy_pricing_http.py \
    --start-date 2025-01-01 \
    --end-date 2025-12-31 \
    --api-key $MISO_API_KEY \
    --s3-bucket production-data \
    --kafka-bootstrap-servers kafka1:9092,kafka2:9092 \
    --debug
```

**Using environment variables:**

```bash
export MISO_API_KEY="your-api-key"
export S3_BUCKET="production-data"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"

python scraper_miso_energy_pricing_http.py \
    --start-date 2025-01-01 \
    --end-date 2025-01-31
```

## Data Output

### S3 Storage Structure

Data is stored in S3 with date-based partitioning:

```
s3://your-bucket/
└── miso_energy_pricing/
    └── YYYY/
        └── MM/
            └── DD/
                └── miso_energy_pricing_ENDPOINT_YYYYMMDD_HHMMSS_VERSION.json
```

Example:
```
s3://production-data/miso_energy_pricing/2025/01/15/miso_energy_pricing_da_exante_lmp_20250115_143022_001.json
```

### Data Format

Data is stored in JSON format.

**JSON Structure:**
```json
{
    "data": [
        {
            "timestamp": "2025-01-15T14:30:00Z",
            "value": 123.45
        }
    ],
    "meta": {
        "source": "MISO",
        "endpoint": "da_exante_lmp",
        "collected_at": "2025-01-15T14:30:22Z"
    }
}
```

### Kafka Notifications

When Kafka is configured, the scraper sends notifications for each new file:

```json
{
    "event": "new_file",
    "dgroup": "miso_energy_pricing",
    "source": "miso",
    "data_type": "energy_pricing",
    "endpoint": "da_exante_lmp",
    "date": "2025-01-15",
    "s3_path": "s3://bucket/miso_energy_pricing/2025/01/15/file.json",
    "file_hash": "abc123...",
    "timestamp": "2025-01-15T14:30:22Z"
}
```

## Testing

### Run Unit Tests

```bash
pytest tests/miso/test_scraper_miso_energy_pricing_http.py -v
```

### Run Integration Tests

Integration tests require valid credentials:

```bash
export MISO_API_KEY="your-api-key"
pytest tests/miso/test_scraper_miso_energy_pricing_http.py -v -m integration
```

### Test Coverage

```bash
pytest tests/miso/ --cov=miso --cov-report=html
```

## Infrastructure

This scraper uses the collection framework infrastructure:

- **BaseCollector**: Abstract base class for all collectors
- **HashRegistry**: Redis-based SHA256 content deduplication
- **S3Manager**: S3 upload with versioning and date partitioning
- **KafkaProducer**: Real-time notifications for data pipelines

See `infrastructure/` directory for implementation details.

## Monitoring

### Logging

The scraper uses structured JSON logging:

```python
{
    "timestamp": "2025-01-15T14:30:22Z",
    "level": "INFO",
    "message": "Collection complete",
    "extra": {
        "total_candidates": 31,
        "new_files": 28,
        "duplicates": 3,
        "errors": 0
    }
}
```

### Metrics

Key metrics tracked:
- Total candidates generated
- New files collected
- Duplicate files skipped
- Errors encountered
- Collection duration

## Troubleshooting

### Common Issues

**Authentication Errors:**
- Verify MISO_API_KEY is set correctly
- Check API key is valid and not expired
- Ensure API key has required permissions

**Connection Errors:**
- Verify network connectivity to https://api.misoenergy.org
- Check firewall rules allow outbound HTTPS
- Retry with `--debug` flag for detailed logs

**Redis Errors:**
- Verify Redis is running: `redis-cli ping`
- Check Redis host/port configuration
- Ensure Redis has sufficient memory

**S3 Errors:**
- Verify AWS credentials are configured
- Check S3 bucket exists and is accessible
- Ensure IAM permissions for PutObject

## Maintenance

### Infrastructure Version

- **Version**: 1.13.0
- **Generated**: 2025-12-19
- **Generator**: hybrid-template-baml

### Updating

To update to a new infrastructure version:

```bash
python -m claude_scraper.updater \
    --scraper scraper_miso_energy_pricing_http.py \
    --target-version X.Y.Z
```

## Support

For issues or questions:
1. Check logs with `--debug` flag
2. Review API documentation at https://api.misoenergy.org
3. Contact data engineering team

## License

Proprietary - Internal use only
