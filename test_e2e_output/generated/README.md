# OpenWeather Data Data Collector

Automated data collector for OpenWeather data data.

## Overview

This scraper collects data data from OpenWeather using their HTTP_REST_API interface.

- **Data Source**: OpenWeather
- **API Base URL**: 
- **Authentication**: NONE
- **Data Format**: JSON
- **Update Frequency**: daily
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

### 1. Get current weather data for a location

- **Endpoint ID**: `current_weather`
- **Path**: `/weather`
- **Method**: `GET`
- **Description**: Get current weather data for a location
- **Parameters**: {"appid": "API key", "q": "city name"}

### 2. Get 5-day weather forecast

- **Endpoint ID**: `forecast`
- **Path**: `/forecast`
- **Method**: `GET`
- **Description**: Get 5-day weather forecast
- **Parameters**: {"appid": "API key", "cnt": "number of timestamps", "q": "city name"}


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
| `REDIS_HOST` | No | Redis host (default: localhost) |
| `REDIS_PORT` | No | Redis port (default: 6379) |
| `S3_BUCKET` | Yes | S3 bucket for data storage |
| `KAFKA_BOOTSTRAP_SERVERS` | No | Kafka servers (comma-separated) |
| `KAFKA_TOPIC` | No | Kafka topic (default: open_weather_data) |

### Authentication

This scraper does not require authentication.

## Usage

### Command Line

Basic usage:

```bash
python scraper_open_weather_data_http.py \
    --start-date 2025-01-01 \
    --end-date 2025-01-31 \
    --s3-bucket your-bucket-name \
    --kafka-bootstrap-servers localhost:9092
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--start-date` | Start date for data collection (YYYY-MM-DD) |
| `--end-date` | End date for data collection (YYYY-MM-DD) |
| `--redis-host` | Redis host (default: localhost) |
| `--redis-port` | Redis port (default: 6379) |
| `--s3-bucket` | S3 bucket for data storage (required) |
| `--kafka-bootstrap-servers` | Kafka servers (comma-separated) |
| `--kafka-topic` | Kafka topic for notifications |
| `--dgroup` | Data group identifier (default: open_weather_data) |
| `--debug` | Enable debug logging |

### Examples

**Collect data for a single day:**

```bash
python scraper_open_weather_data_http.py \
    --start-date 2025-12-19 \
    --end-date 2025-12-19 \
    --s3-bucket production-data
```

**Collect historical data with debug logging:**

```bash
python scraper_open_weather_data_http.py \
    --start-date 2025-01-01 \
    --end-date 2025-12-31 \
    --s3-bucket production-data \
    --kafka-bootstrap-servers kafka1:9092,kafka2:9092 \
    --debug
```

**Using environment variables:**

```bash
export OPEN_WEATHER_API_KEY="your-api-key"
export S3_BUCKET="production-data"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"

python scraper_open_weather_data_http.py \
    --start-date 2025-01-01 \
    --end-date 2025-01-31
```

## Data Output

### S3 Storage Structure

Data is stored in S3 with date-based partitioning:

```
s3://your-bucket/
└── open_weather_data/
    └── YYYY/
        └── MM/
            └── DD/
                └── open_weather_data_ENDPOINT_YYYYMMDD_HHMMSS_VERSION.json
```

Example:
```
s3://production-data/open_weather_data/2025/01/15/open_weather_data_current_weather_20250115_143022_001.json
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
        "source": "OpenWeather",
        "endpoint": "current_weather",
        "collected_at": "2025-01-15T14:30:22Z"
    }
}
```

### Kafka Notifications

When Kafka is configured, the scraper sends notifications for each new file:

```json
{
    "event": "new_file",
    "dgroup": "open_weather_data",
    "source": "openweather",
    "data_type": "data",
    "endpoint": "current_weather",
    "date": "2025-01-15",
    "s3_path": "s3://bucket/open_weather_data/2025/01/15/file.json",
    "file_hash": "abc123...",
    "timestamp": "2025-01-15T14:30:22Z"
}
```

## Testing

### Run Unit Tests

```bash
pytest tests/open_weather/test_scraper_open_weather_data_http.py -v
```

### Run Integration Tests

Integration tests require valid credentials:

```bash
export OPEN_WEATHER_API_KEY="your-api-key"
pytest tests/open_weather/test_scraper_open_weather_data_http.py -v -m integration
```

### Test Coverage

```bash
pytest tests/open_weather/ --cov=open_weather --cov-report=html
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
- Verify OPEN_WEATHER_API_KEY is set correctly
- Check API key is valid and not expired
- Ensure API key has required permissions

**Connection Errors:**
- Verify network connectivity to 
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
    --scraper scraper_open_weather_data_http.py \
    --target-version X.Y.Z
```

## Support

For issues or questions:
1. Check logs with `--debug` flag
2. Review API documentation at 
3. Contact data engineering team

## License

Proprietary - Internal use only
