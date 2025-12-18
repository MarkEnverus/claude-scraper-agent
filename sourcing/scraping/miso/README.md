# MISO Energy Pricing API Collector

Production-ready HTTP collector for MISO (Midcontinent Independent System Operator) Energy Pricing data.

## Overview

This scraper collects energy pricing data from the MISO Energy Data Exchange API. It covers all 12 endpoints for Day-Ahead and Real-Time markets across three pricing types: LMP (Locational Marginal Pricing), MCP (Marginal Congestion Pricing), and MCC (Marginal Congestion Component).

**Data Source:** MISO Energy
**API Base URL:** https://data-exchange.misoenergy.org
**Authentication:** API Key via `Ocp-Apim-Subscription-Key` header
**Data Format:** JSON

## Endpoints Collected

### Day-Ahead Markets (6 endpoints)

1. **DA_EXANTE_LMP** - Day-Ahead Ex-Ante LMP
   - Path: `/api/v1/da/{date}/exante/lmp`
   - Forward-looking price forecasts

2. **DA_EXPOST_LMP** - Day-Ahead Ex-Post LMP
   - Path: `/api/v1/da/{date}/expost/lmp`
   - Actual settled prices

3. **DA_EXANTE_MCP** - Day-Ahead Ex-Ante MCP
   - Path: `/api/v1/da/{date}/exante/mcp`
   - Forward-looking congestion prices

4. **DA_EXPOST_MCP** - Day-Ahead Ex-Post MCP
   - Path: `/api/v1/da/{date}/expost/mcp`
   - Actual congestion prices

5. **DA_EXANTE_MCC** - Day-Ahead Ex-Ante MCC
   - Path: `/api/v1/da/{date}/exante/mcc`
   - Forward-looking congestion component

6. **DA_EXPOST_MCC** - Day-Ahead Ex-Post MCC
   - Path: `/api/v1/da/{date}/expost/mcc`
   - Actual congestion component

### Real-Time Markets (6 endpoints)

7. **RT_LMP** - Real-Time 5-Minute LMP
   - Path: `/api/v1/rt/{date}/5min/lmp`
   - 5-minute interval pricing

8. **RT_LMP_Hourly** - Real-Time Hourly LMP
   - Path: `/api/v1/rt/{date}/hourly/lmp`
   - Hourly aggregated pricing

9. **RT_MCP** - Real-Time 5-Minute MCP
   - Path: `/api/v1/rt/{date}/5min/mcp`
   - 5-minute congestion pricing

10. **RT_MCP_Hourly** - Real-Time Hourly MCP
    - Path: `/api/v1/rt/{date}/hourly/mcp`
    - Hourly congestion pricing

11. **RT_MCC** - Real-Time 5-Minute MCC
    - Path: `/api/v1/rt/{date}/5min/mcc`
    - 5-minute congestion component

12. **RT_MCC_Hourly** - Real-Time Hourly MCC
    - Path: `/api/v1/rt/{date}/hourly/mcc`
    - Hourly congestion component

## Data Structure

### Day-Ahead Response Format
```json
{
  "effectiveDate": "2025-01-15",
  "marketType": "DA",
  "dataType": "LMP",
  "timestamp": "2025-01-15T00:00:00Z",
  "locations": [
    {
      "locationId": "ALTW.ALTO1",
      "locationName": "ALTW.ALTO1 - Node",
      "locationType": "Node",
      "zone": "ALTW",
      "hourlyData": [
        {
          "hour": 1,
          "lmp": 25.50,
          "mcc": 5.25,
          "mlc": 20.25
        }
      ]
    }
  ]
}
```

### Real-Time Response Format
```json
{
  "effectiveDate": "2025-01-15",
  "marketType": "RT",
  "dataType": "LMP",
  "timestamp": "2025-01-15T12:00:00Z",
  "locations": [
    {
      "locationId": "ALTW.ALTO1",
      "locationName": "ALTW.ALTO1 - Node",
      "locationType": "Node",
      "zone": "ALTW",
      "intervalData": [
        {
          "timestamp": "2025-01-15T12:00:00Z",
          "intervalEnd": "2025-01-15T12:05:00Z",
          "lmp": 25.75,
          "mcc": 5.30,
          "mlc": 20.45
        }
      ]
    }
  ]
}
```

## Setup

### Prerequisites

1. Python 3.9+
2. Redis server (for hash deduplication)
3. AWS credentials configured (for S3 storage)
4. MISO API key

### Installation

```bash
# Install dependencies (if using uv)
uv sync

# Or with pip
pip install -r requirements.txt
```

### Configuration

Set the required environment variable:

```bash
export MISO_API_KEY=72575d06948f460993e3fca6ee68a4da
```

### Redis Setup

Ensure Redis is running:

```bash
# Start Redis locally
redis-server

# Or via Docker
docker run -d -p 6379:6379 redis:latest
```

## Usage

### Basic Usage

Collect data for a single day:

```bash
python scraper_miso_energy_pricing_http.py \
  --start-date 2025-01-15 \
  --end-date 2025-01-16 \
  --s3-bucket my-bucket \
  --environment dev
```

### Date Range Collection

Collect multiple days:

```bash
python scraper_miso_energy_pricing_http.py \
  --start-date 2025-01-01 \
  --end-date 2025-01-31 \
  --s3-bucket my-bucket \
  --environment dev
```

### Custom Redis Configuration

```bash
python scraper_miso_energy_pricing_http.py \
  --start-date 2025-01-15 \
  --end-date 2025-01-16 \
  --redis-host redis.example.com \
  --redis-port 6380 \
  --redis-db 1 \
  --s3-bucket my-bucket
```

### Force Re-download

Skip hash deduplication and re-download all files:

```bash
python scraper_miso_energy_pricing_http.py \
  --start-date 2025-01-15 \
  --end-date 2025-01-16 \
  --s3-bucket my-bucket \
  --force
```

### Debug Logging

Enable detailed debug logs:

```bash
python scraper_miso_energy_pricing_http.py \
  --start-date 2025-01-15 \
  --end-date 2025-01-16 \
  --s3-bucket my-bucket \
  --log-level DEBUG
```

### With Kafka Notifications

```bash
python scraper_miso_energy_pricing_http.py \
  --start-date 2025-01-15 \
  --end-date 2025-01-16 \
  --s3-bucket my-bucket \
  --kafka-connection "kafka://localhost:9092/miso-pricing"
```

## Command-Line Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--start-date` | Yes | - | Start date (YYYY-MM-DD, inclusive) |
| `--end-date` | Yes | - | End date (YYYY-MM-DD, exclusive) |
| `--s3-bucket` | Yes | - | S3 bucket name for storage |
| `--redis-host` | No | localhost | Redis server hostname |
| `--redis-port` | No | 6379 | Redis server port |
| `--redis-db` | No | 0 | Redis database number |
| `--s3-prefix` | No | sourcing | S3 prefix for file organization |
| `--environment` | No | dev | Environment (dev/staging/prod) |
| `--dgroup` | No | miso_energy_pricing | Data group identifier |
| `--kafka-connection` | No | None | Kafka connection string |
| `--force` | No | False | Force re-download (skip hash check) |
| `--log-level` | No | INFO | Log level (DEBUG/INFO/WARNING/ERROR) |
| `--timeout` | No | 30 | HTTP request timeout in seconds |

## Output

### S3 Storage

Files are stored in S3 with date partitioning:

```
s3://{bucket}/{prefix}/{dgroup}/year={YYYY}/month={MM}/day={DD}/{filename}
```

Example paths:
```
s3://my-bucket/sourcing/miso_energy_pricing/year=2025/month=01/day=15/miso_da_exante_lmp_20250115.json
s3://my-bucket/sourcing/miso_energy_pricing/year=2025/month=01/day=15/miso_rt_lmp_20250115.json
```

### Filename Pattern

```
miso_{endpoint_name}_{date}.json
```

Examples:
- `miso_da_exante_lmp_20250115.json` - Day-Ahead Ex-Ante LMP for 2025-01-15
- `miso_rt_lmp_20250115.json` - Real-Time 5-Minute LMP for 2025-01-15
- `miso_rt_mcp_hourly_20250115.json` - Real-Time Hourly MCP for 2025-01-15

### Collection Summary

After execution, the scraper prints a summary:

```
Collection Summary:
  Total candidates: 36
  Successfully collected: 34
  Skipped (duplicate): 2
  Failed: 0
```

## Features

### Deduplication

The scraper uses Redis-backed hash deduplication to avoid re-downloading identical content:

- Content is hashed using SHA256
- Hashes are stored in Redis with 365-day TTL
- Duplicate content is automatically skipped
- Can be bypassed with `--force` flag

### Error Handling

- HTTP errors (404, 500, etc.) are logged and reported
- Connection timeouts are caught and reported
- Invalid JSON responses trigger validation failures
- Failed candidates don't stop the entire collection

### Logging

Structured JSON logging for integration with log aggregation systems:

```json
{
  "timestamp": "2025-01-15T14:30:05Z",
  "level": "INFO",
  "message": "Successfully collected",
  "candidate": "miso_da_exante_lmp_20250115.json",
  "hash": "abc123...",
  "s3_path": "s3://..."
}
```

### Content Validation

- Validates JSON structure
- Rejects empty responses
- Rejects empty JSON objects/arrays
- Custom validation can be extended

## Testing

### Run All Tests

```bash
pytest sourcing/scraping/miso/tests/ -v
```

### Run Specific Test

```bash
pytest sourcing/scraping/miso/tests/test_scraper_miso_energy_pricing_http.py::TestMISOEnergyPricingCollector::test_generate_candidates_single_day -v
```

### With Coverage

```bash
pytest sourcing/scraping/miso/tests/ --cov=sourcing.scraping.miso --cov-report=html
```

## Architecture

### Class Hierarchy

```
BaseCollector (collection_framework.py)
    ↓
MISOEnergyPricingCollector (scraper_miso_energy_pricing_http.py)
```

### Key Components

1. **Candidate Generation** (`generate_candidates()`)
   - Iterates through date range
   - Generates candidates for all 12 endpoints per date
   - Returns list of `DownloadCandidate` objects

2. **Content Collection** (`collect_content()`)
   - Makes HTTP GET request to API endpoint
   - Handles authentication via header
   - Returns raw JSON response

3. **Content Validation** (`validate_content()`)
   - Validates JSON structure
   - Checks for empty responses
   - Logs validation failures

4. **Collection Orchestration** (`run_collection()`)
   - Provided by `BaseCollector`
   - Manages deduplication, S3 upload, Kafka notifications
   - Returns collection statistics

## Monitoring

### Key Metrics

- **Total Candidates**: Number of API calls planned
- **Successfully Collected**: Files uploaded to S3
- **Skipped (Duplicate)**: Files skipped due to hash match
- **Failed**: API calls that failed

### Log Fields

Monitor these fields in your log aggregation system:

- `dgroup`: Data group identifier
- `endpoint_name`: Which endpoint was called
- `candidate`: File identifier
- `hash`: Content hash (for deduplication tracking)
- `s3_path`: Storage location
- `error`: Error messages for failures

## Troubleshooting

### Authentication Errors

```
HTTP 401: Unauthorized
```

**Solution:** Verify `MISO_API_KEY` environment variable is set correctly.

### Connection Timeouts

```
Request timeout after 30s
```

**Solution:** Increase timeout with `--timeout 60` or check network connectivity.

### Redis Connection Failed

```
Failed to connect to Redis: Connection refused
```

**Solution:** Ensure Redis is running on specified host/port.

### S3 Upload Errors

```
Failed to upload to S3: Access Denied
```

**Solution:** Verify AWS credentials and S3 bucket permissions.

### Empty Responses

```
Empty JSON object received
```

**Explanation:** API returned valid JSON but no data. This may occur for:
- Future dates (no data available yet)
- Historical dates outside API's data retention period
- Temporary API issues

## API Rate Limits

MISO API rate limits are not publicly documented. Best practices:

- Use reasonable date ranges
- Monitor for 429 (Too Many Requests) responses
- Consider adding delays between requests if needed

## Historical Data Support

The API supports querying historical dates. Data availability depends on MISO's retention policy. Typical availability:

- Real-Time data: Recent months
- Day-Ahead data: Extended historical period

## Scheduling

### Cron Example

Daily collection at 2 AM:

```cron
0 2 * * * /path/to/scraper_miso_energy_pricing_http.py --start-date $(date +\%Y-\%m-\%d) --end-date $(date -d "+1 day" +\%Y-\%m-\%d) --s3-bucket prod-bucket --environment prod
```

### Airflow DAG Example

```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

dag = DAG(
    'miso_energy_pricing_collection',
    default_args={'start_date': datetime(2025, 1, 1)},
    schedule_interval='0 2 * * *',  # Daily at 2 AM
    catchup=False
)

collect_task = BashOperator(
    task_id='collect_miso_pricing',
    bash_command=(
        'python /path/to/scraper_miso_energy_pricing_http.py '
        '--start-date {{ ds }} '
        '--end-date {{ tomorrow_ds }} '
        '--s3-bucket prod-bucket '
        '--environment prod'
    ),
    dag=dag
)
```

## License

Proprietary - Internal use only

## Support

For issues or questions, contact the data engineering team.

## Changelog

### Version 1.0.0 (2025-01-15)

- Initial release
- Support for all 12 MISO pricing endpoints
- Day-Ahead and Real-Time markets
- LMP, MCP, MCC data types
- Hash-based deduplication
- S3 storage with date partitioning
- Kafka notifications
- Comprehensive test coverage
