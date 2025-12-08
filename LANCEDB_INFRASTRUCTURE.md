# LanceDB Infrastructure Implementation Guide

## Project Overview

Build a standalone LanceDB-based indexing and query service that:
1. Consumes Kafka notifications from scraper systems
2. Indexes scraped data with metadata and vector embeddings
3. Provides query APIs for frontend users and AI agents
4. Exposes capabilities via MCP (Model Context Protocol) for Claude Code agents

**This is an EXTERNAL service** - completely separate from the scraper plugin infrastructure.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ INPUT: Kafka Notifications (from scrapers)                  │
│  Topic: scraper-notifications                                │
│  Message: ScraperNotificationMessage {                       │
│    dataset, urn, location (S3 path), version, etag,         │
│    metadata: {source, data_type, publish_dtm, ...}          │
│  }                                                           │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ INDEXER SERVICE (Kafka Consumer)                            │
│  1. Read notification from Kafka                             │
│  2. Download file from S3                                    │
│  3. Extract metadata + generate embeddings                   │
│  4. Insert into LanceDB (metadata + vector tables)           │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ LANCEDB STORAGE                                              │
│  Table 1: scraper_metadata (SQL-style queries)               │
│    - Hash lookups, time ranges, source filtering            │
│  Table 2: scraper_vectors (semantic search)                  │
│    - Content embeddings, schema embeddings                   │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ QUERY API SERVICE (FastAPI)                                  │
│  Frontend Endpoints:                                         │
│    GET /api/v1/scrapes/search - Unified search               │
│    GET /api/v1/scrapes/{hash} - Hash lookup                  │
│  Agent Context Endpoints:                                    │
│    POST /api/v1/agents/context/similar-apis                  │
│    POST /api/v1/agents/context/fix-patterns                  │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓
┌─────────────────────────────────────────────────────────────┐
│ MCP SERVER (Model Context Protocol)                         │
│  Wraps Query API as MCP tools for Claude Code agents        │
│  Tools: search_scrapes, find_similar_apis, get_fix_patterns │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Schemas

### Kafka Input Message Format

```json
{
  "dataset": "nyiso_load_forecast",
  "environment": "dev",
  "urn": "load_20250120_14.json",
  "location": "s3://bucket/sourcing/nyiso/load_forecast/year=2025/month=01/day=20/load_20250120_14.json",
  "version": "20250120T143000Z",
  "etag": "abc123def456",
  "metadata": {
    "publish_dtm": "2025-01-20T14:30:00Z",
    "s3_guid": "xyz789",
    "url": "https://api.nyiso.com/v1/load",
    "original_file_size": 12345,
    "original_file_md5sum": "hash...",
    "data_type": "load_forecast",
    "source": "nyiso"
  }
}
```

### LanceDB Schema 1: Metadata Table

```python
from lancedb.pydantic import LanceModel
from datetime import datetime
from typing import Optional

class ScraperMetadata(LanceModel):
    # Primary identifiers
    id: str  # From urn
    sha256_hash: str  # Calculate from content

    # Source information
    data_source: str  # e.g., "NYISO", "MISO", "PJM"
    data_type: str  # e.g., "load_forecast", "pricing"
    dataset: str  # e.g., "nyiso_load_forecast"

    # Storage references
    s3_path: str  # Full S3 URI from 'location'
    s3_bucket: str
    s3_key: str
    file_size_bytes: int

    # Temporal data
    collected_at: datetime  # From metadata.publish_dtm
    published_at: Optional[datetime]  # From version if available
    year: int  # Extract from S3 path
    month: int
    day: int

    # File metadata
    file_format: str  # JSON, CSV, XML, etc.
    etag: str
    version_id: Optional[str]
    md5sum: str

    # Collection metadata
    scraper_name: Optional[str]  # Infer from dataset
    environment: str  # dev, staging, prod
    source_url: Optional[str]  # From metadata.url if present

    # Quality metrics
    validation_status: str  # 'indexed', 'error'
    error_count: int  # Default 0
    warning_count: int  # Default 0
```

### LanceDB Schema 2: Vector Table

```python
from typing import List, Dict, Optional

class ScraperVectorData(LanceModel):
    # Link to metadata
    metadata_id: str  # Foreign key to ScraperMetadata.id
    sha256_hash: str  # Duplicate for easier joins

    # Content representation
    content_summary: str  # First 1000 chars or smart extraction
    content_schema: Optional[str]  # JSON schema if detected
    api_endpoint: Optional[str]  # Extract from metadata.url

    # Vector embeddings (1536-dim for OpenAI text-embedding-3-small)
    content_embedding: List[float]  # Embed content summary
    schema_embedding: Optional[List[float]]  # Embed schema structure

    # Agent-specific metadata (for learning)
    scraper_code_snippet: Optional[str]  # Reserved for future
    collection_success: bool  # True (we only index successful collections)
    fix_history: Optional[List[Dict]]  # Reserved for scraper-fixer feedback

    # Similarity features
    auth_method: Optional[str]  # Extract from content if API data
    rate_limit: Optional[str]
    data_freshness: Optional[str]  # hourly, daily, etc.
    pagination_type: Optional[str]  # None, offset, cursor, page
```

---

## Implementation

### Project Structure

```
lancedb-scraper-index/
├── pyproject.toml              # Dependencies
├── README.md
├── .env.example
├── indexer/
│   ├── __init__.py
│   ├── schemas.py              # ScraperMetadata, ScraperVectorData
│   ├── lancedb_client.py       # LanceDB connection manager
│   ├── embedding_service.py    # OpenAI embedding generation
│   ├── indexer_service.py      # Main Kafka consumer
│   └── utils.py                # Helper functions
├── api/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app
│   ├── routes/
│   │   ├── frontend.py         # /api/v1/scrapes/*
│   │   └── agents.py           # /api/v1/agents/context/*
│   └── dependencies.py         # Shared dependencies
├── mcp_server/
│   ├── __init__.py
│   └── lancedb_mcp.py          # MCP server wrapper
├── docker/
│   ├── Dockerfile.indexer
│   ├── Dockerfile.api
│   └── Dockerfile.mcp
├── k8s/
│   ├── indexer-deployment.yaml
│   ├── api-deployment.yaml
│   ├── mcp-deployment.yaml
│   └── configmap.yaml
└── tests/
    ├── test_indexer.py
    ├── test_api.py
    └── test_mcp.py
```

### Dependencies (pyproject.toml)

```toml
[project]
name = "lancedb-scraper-index"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "lancedb>=0.5.0",
    "pydantic>=2.0.0",
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "confluent-kafka>=2.3.0",
    "boto3>=1.34.0",
    "openai>=1.10.0",
    "python-multipart>=0.0.6",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "httpx>=0.26.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
]
```

### Core Implementation Files

#### 1. schemas.py

```python
"""LanceDB table schemas."""
from lancedb.pydantic import LanceModel
from datetime import datetime
from typing import Optional, List, Dict

class ScraperMetadata(LanceModel):
    """Metadata table for SQL-style queries."""
    # Primary identifiers
    id: str
    sha256_hash: str

    # Source information
    data_source: str
    data_type: str
    dataset: str

    # Storage references
    s3_path: str
    s3_bucket: str
    s3_key: str
    file_size_bytes: int

    # Temporal data
    collected_at: datetime
    published_at: Optional[datetime] = None
    year: int
    month: int
    day: int

    # File metadata
    file_format: str
    etag: str
    version_id: Optional[str] = None
    md5sum: str

    # Collection metadata
    scraper_name: Optional[str] = None
    environment: str = "prod"
    source_url: Optional[str] = None

    # Quality metrics
    validation_status: str = "indexed"
    error_count: int = 0
    warning_count: int = 0


class ScraperVectorData(LanceModel):
    """Vector table for semantic search."""
    # Link to metadata
    metadata_id: str
    sha256_hash: str

    # Content representation
    content_summary: str
    content_schema: Optional[str] = None
    api_endpoint: Optional[str] = None

    # Vector embeddings
    content_embedding: List[float]
    schema_embedding: Optional[List[float]] = None

    # Agent-specific metadata
    scraper_code_snippet: Optional[str] = None
    collection_success: bool = True
    fix_history: Optional[List[Dict]] = None

    # Similarity features
    auth_method: Optional[str] = None
    rate_limit: Optional[str] = None
    data_freshness: Optional[str] = None
    pagination_type: Optional[str] = None
```

#### 2. lancedb_client.py

```python
"""LanceDB connection and table management."""
import lancedb
import os
from pathlib import Path
from .schemas import ScraperMetadata, ScraperVectorData

class LanceDBClient:
    def __init__(self, db_path: str = None):
        """Initialize LanceDB connection.

        Args:
            db_path: Path to LanceDB storage. Can be:
                - Local path: "/mnt/lancedb"
                - S3 URI: "s3://bucket/lancedb"
                If None, uses LANCEDB_PATH env var or defaults to "./lancedb"
        """
        if db_path is None:
            db_path = os.getenv("LANCEDB_PATH", "./lancedb")

        self.db = lancedb.connect(db_path)
        self.metadata_table = None
        self.vector_table = None

    def init_tables(self):
        """Create tables if they don't exist."""
        # Check if tables exist
        table_names = self.db.table_names()

        # Create or open metadata table
        if "scraper_metadata" not in table_names:
            self.metadata_table = self.db.create_table(
                "scraper_metadata",
                schema=ScraperMetadata
            )
            # Create indexes
            self.metadata_table.create_index("sha256_hash")
            self.metadata_table.create_index("data_source")
        else:
            self.metadata_table = self.db.open_table("scraper_metadata")

        # Create or open vector table
        if "scraper_vectors" not in table_names:
            self.vector_table = self.db.create_table(
                "scraper_vectors",
                schema=ScraperVectorData
            )
            # Create vector index for ANN search
            self.vector_table.create_index(
                "content_embedding",
                metric="cosine",
                num_partitions=256,
                num_sub_vectors=96
            )
        else:
            self.vector_table = self.db.open_table("scraper_vectors")

        print(f"✓ LanceDB tables initialized: {table_names}")
```

#### 3. embedding_service.py

```python
"""OpenAI embedding generation service."""
from openai import OpenAI
import json
import os
from typing import List

class EmbeddingService:
    def __init__(self, api_key: str = None):
        """Initialize OpenAI client.

        Args:
            api_key: OpenAI API key. If None, uses OPENAI_API_KEY env var.
        """
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")

        self.client = OpenAI(api_key=api_key)
        self.model = "text-embedding-3-small"  # 1536 dimensions, $0.02/1M tokens

    def embed_content(self, content: str, max_length: int = 8000) -> List[float]:
        """Generate embedding for file content.

        Args:
            content: Text content to embed
            max_length: Max characters before truncation

        Returns:
            List of 1536 floats
        """
        # Truncate if too long
        if len(content) > max_length:
            content = content[:max_length] + "..."

        response = self.client.embeddings.create(
            model=self.model,
            input=content
        )
        return response.data[0].embedding

    def embed_schema(self, schema: dict) -> List[float]:
        """Generate embedding for data schema/structure.

        Args:
            schema: Dictionary representing data structure

        Returns:
            List of 1536 floats
        """
        schema_text = json.dumps(schema, indent=2)

        response = self.client.embeddings.create(
            model=self.model,
            input=f"Data schema:\n{schema_text}"
        )
        return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts in a single API call.

        Args:
            texts: List of text strings

        Returns:
            List of embeddings (each 1536 floats)
        """
        response = self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]
```

#### 4. indexer_service.py

```python
"""Kafka consumer that indexes scraped data into LanceDB."""
from confluent_kafka import Consumer, KafkaError
import boto3
import json
import hashlib
from datetime import datetime
from urllib.parse import urlparse
from .lancedb_client import LanceDBClient
from .embedding_service import EmbeddingService
from .schemas import ScraperMetadata, ScraperVectorData

class LanceDBIndexer:
    def __init__(
        self,
        kafka_brokers: str,
        kafka_topic: str = "scraper-notifications",
        consumer_group: str = "lancedb-indexer"
    ):
        """Initialize indexer service.

        Args:
            kafka_brokers: Comma-separated Kafka broker addresses
            kafka_topic: Topic to subscribe to
            consumer_group: Kafka consumer group ID
        """
        self.lance_client = LanceDBClient()
        self.lance_client.init_tables()

        self.embedding_service = EmbeddingService()
        self.s3_client = boto3.client('s3')

        self.kafka_consumer = Consumer({
            'bootstrap.servers': kafka_brokers,
            'group.id': consumer_group,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': True
        })
        self.kafka_consumer.subscribe([kafka_topic])

        print(f"✓ Indexer initialized: topic={kafka_topic}, group={consumer_group}")

    def run(self):
        """Main indexing loop."""
        print("Starting indexing loop...")

        try:
            while True:
                msg = self.kafka_consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        print(f"Kafka error: {msg.error()}")
                        continue

                # Process message
                try:
                    notification = json.loads(msg.value().decode('utf-8'))
                    self.index_scrape(notification)
                except Exception as e:
                    print(f"Error processing message: {e}")
                    # Continue to next message

        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            self.kafka_consumer.close()

    def index_scrape(self, notification: dict):
        """Index a scraped file into LanceDB.

        Args:
            notification: ScraperNotificationMessage dict
        """
        print(f"Indexing: {notification['urn']}")

        # Parse S3 location
        s3_uri = notification['location']
        parsed = urlparse(s3_uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')

        # Download file content
        try:
            obj = self.s3_client.get_object(Bucket=bucket, Key=key)
            content = obj['Body'].read().decode('utf-8')
        except Exception as e:
            print(f"Error downloading {s3_uri}: {e}")
            return

        # Calculate hash
        sha256_hash = hashlib.sha256(content.encode()).hexdigest()

        # Extract year/month/day from S3 key
        # Expected format: .../year=YYYY/month=MM/day=DD/...
        parts = key.split('/')
        year = month = day = None
        for part in parts:
            if part.startswith('year='):
                year = int(part.split('=')[1])
            elif part.startswith('month='):
                month = int(part.split('=')[1])
            elif part.startswith('day='):
                day = int(part.split('=')[1])

        # Detect file format
        if key.endswith('.json'):
            file_format = 'JSON'
        elif key.endswith('.csv'):
            file_format = 'CSV'
        elif key.endswith('.xml'):
            file_format = 'XML'
        else:
            file_format = 'UNKNOWN'

        # Create metadata record
        metadata = ScraperMetadata(
            id=notification['urn'],
            sha256_hash=sha256_hash,
            data_source=notification['metadata']['source'].upper(),
            data_type=notification['metadata']['data_type'],
            dataset=notification['dataset'],
            s3_path=s3_uri,
            s3_bucket=bucket,
            s3_key=key,
            file_size_bytes=notification['metadata']['original_file_size'],
            collected_at=datetime.fromisoformat(
                notification['metadata']['publish_dtm'].replace('Z', '+00:00')
            ),
            year=year or 0,
            month=month or 0,
            day=day or 0,
            file_format=file_format,
            etag=notification['etag'],
            md5sum=notification['metadata']['original_file_md5sum'],
            environment=notification['environment'],
            source_url=notification['metadata'].get('url')
        )

        # Insert metadata
        self.lance_client.metadata_table.add([metadata.dict()])

        # Generate embeddings
        content_summary = content[:1000]  # First 1000 chars
        content_embedding = self.embedding_service.embed_content(content_summary)

        # Try to extract schema
        schema_embedding = None
        try:
            if file_format == 'JSON':
                data = json.loads(content)
                if isinstance(data, dict):
                    schema = {k: type(v).__name__ for k, v in data.items()}
                    schema_embedding = self.embedding_service.embed_schema(schema)
        except:
            pass  # Skip schema if can't parse

        # Create vector record
        vector_data = ScraperVectorData(
            metadata_id=notification['urn'],
            sha256_hash=sha256_hash,
            content_summary=content_summary,
            content_embedding=content_embedding,
            schema_embedding=schema_embedding,
            api_endpoint=notification['metadata'].get('url')
        )

        # Insert vector data
        self.lance_client.vector_table.add([vector_data.dict()])

        print(f"✓ Indexed: {notification['urn']}")


if __name__ == "__main__":
    import os

    indexer = LanceDBIndexer(
        kafka_brokers=os.getenv("KAFKA_BROKERS", "localhost:9092"),
        kafka_topic=os.getenv("KAFKA_TOPIC", "scraper-notifications")
    )
    indexer.run()
```

#### 5. api/main.py (FastAPI Query Service)

```python
"""FastAPI query service for LanceDB."""
from fastapi import FastAPI, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexer.lancedb_client import LanceDBClient
from indexer.embedding_service import EmbeddingService

app = FastAPI(title="LanceDB Scraper Query API", version="0.1.0")

# Initialize clients
lance_client = LanceDBClient()
lance_client.init_tables()
embedding_service = EmbeddingService()


@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "lancedb-query-api"}


@app.get("/api/v1/scrapes/search")
def search_scrapes(
    data_source: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    query: Optional[str] = None,  # Semantic search
    hash: Optional[str] = None,
    limit: int = Query(default=100, le=1000)
) -> Dict[str, Any]:
    """
    Unified search endpoint.

    Query Parameters:
    - data_source: Filter by source (e.g., "MISO", "NYISO")
    - start_date: ISO format date (e.g., "2025-01-01")
    - end_date: ISO format date
    - query: Semantic search text
    - hash: SHA256 hash lookup
    - limit: Max results (default 100, max 1000)

    Returns:
        {
            "results": [...],
            "count": int,
            "query_type": "sql" | "vector"
        }
    """
    # Build filters
    filters = []
    if data_source:
        filters.append(f"data_source = '{data_source.upper()}'")
    if start_date and end_date:
        filters.append(
            f"collected_at >= '{start_date}T00:00:00' AND "
            f"collected_at <= '{end_date}T23:59:59'"
        )
    if hash:
        filters.append(f"sha256_hash = '{hash}'")

    # Execute query
    if query:  # Semantic search
        query_embedding = embedding_service.embed_content(query)

        where_clause = " AND ".join(filters) if filters else None
        results = lance_client.vector_table.search(query_embedding) \
            .where(where_clause) \
            .limit(limit) \
            .to_list()

        return {
            "results": results,
            "count": len(results),
            "query_type": "vector"
        }
    else:  # SQL-style query
        where_clause = " AND ".join(filters) if filters else None
        results = lance_client.metadata_table.search() \
            .where(where_clause) \
            .limit(limit) \
            .to_list()

        return {
            "results": results,
            "count": len(results),
            "query_type": "sql"
        }


@app.get("/api/v1/scrapes/{hash}")
def get_by_hash(hash: str) -> Dict[str, Any]:
    """Fast hash lookup - check if we have this data."""
    results = lance_client.metadata_table.search() \
        .where(f"sha256_hash = '{hash}'") \
        .limit(1) \
        .to_list()

    if results:
        return {"exists": True, "data": results[0]}
    else:
        return {"exists": False}


@app.post("/api/v1/agents/context/similar-apis")
def find_similar_apis(
    api_spec: Dict[str, Any],
    limit: int = Query(default=10, le=50)
) -> Dict[str, List[Dict]]:
    """
    Find similar APIs we've scraped before.

    Body:
        {
            "endpoint": "https://api.example.com/v1/data",
            "method": "GET",
            "auth_required": true,
            ...
        }

    Returns:
        {
            "similar_apis": [
                {
                    "data_source": "MISO",
                    "api_endpoint": "https://...",
                    "similarity_score": 0.95,
                    ...
                }
            ]
        }
    """
    # Embed the API spec
    schema_embedding = embedding_service.embed_schema(api_spec)

    # Search vector table
    results = lance_client.vector_table.search(schema_embedding) \
        .metric("cosine") \
        .limit(limit) \
        .to_list()

    return {
        "similar_apis": [
            {
                "data_source": r.get("data_source"),
                "api_endpoint": r.get("api_endpoint"),
                "auth_method": r.get("auth_method"),
                "rate_limit": r.get("rate_limit"),
                "similarity_score": 1 - r.get("_distance", 0),
                "content_summary": r.get("content_summary")
            }
            for r in results
        ]
    }


@app.post("/api/v1/agents/context/fix-patterns")
def get_fix_patterns(
    scraper_name: str,
    error_type: Optional[str] = None,
    limit: int = Query(default=5, le=20)
) -> Dict[str, List[Dict]]:
    """
    Retrieve past fix patterns for scraper-fixer agent.

    Body:
        {
            "scraper_name": "nyiso_load_forecast",
            "error_type": "api_auth_failure"
        }

    Returns:
        {
            "fix_patterns": [...]
        }
    """
    # Query for scrapers with fix history
    # Note: This requires fix_history to be populated by scraper-fixer
    where_clause = f"scraper_name = '{scraper_name}'"
    if error_type:
        where_clause += f" AND fix_history IS NOT NULL"

    results = lance_client.vector_table.search() \
        .where(where_clause) \
        .limit(limit) \
        .to_list()

    fix_patterns = []
    for r in results:
        if r.get("fix_history"):
            fix_patterns.append({
                "scraper": r.get("scraper_name"),
                "fix_history": r.get("fix_history"),
                "context": r.get("content_summary")
            })

    return {"fix_patterns": fix_patterns}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### 6. mcp_server/lancedb_mcp.py (MCP Wrapper)

```python
"""MCP server that wraps LanceDB Query API."""
import json
import sys
from typing import Any, Dict
import httpx

# MCP server using stdio
def handle_mcp_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP tool call request."""
    tool_name = request.get("tool")
    tool_input = request.get("input", {})

    # API base URL (from environment or default)
    api_base = "http://localhost:8000"

    if tool_name == "search_scrapes":
        # Call /api/v1/scrapes/search
        response = httpx.get(
            f"{api_base}/api/v1/scrapes/search",
            params=tool_input
        )
        return response.json()

    elif tool_name == "find_similar_apis":
        # Call /api/v1/agents/context/similar-apis
        response = httpx.post(
            f"{api_base}/api/v1/agents/context/similar-apis",
            json=tool_input
        )
        return response.json()

    elif tool_name == "get_fix_patterns":
        # Call /api/v1/agents/context/fix-patterns
        response = httpx.post(
            f"{api_base}/api/v1/agents/context/fix-patterns",
            json=tool_input
        )
        return response.json()

    else:
        return {"error": f"Unknown tool: {tool_name}"}


def main():
    """MCP server main loop (stdio protocol)."""
    print("MCP server started", file=sys.stderr)

    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_mcp_request(request)
            print(json.dumps(response))
            sys.stdout.flush()
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
```

---

## Deployment

### Docker Images

**Dockerfile.indexer:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install .

COPY indexer/ ./indexer/

CMD ["python", "-m", "indexer.indexer_service"]
```

**Dockerfile.api:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install .

COPY indexer/ ./indexer/
COPY api/ ./api/

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes Deployments

**k8s/indexer-deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lancedb-indexer
spec:
  replicas: 2
  selector:
    matchLabels:
      app: lancedb-indexer
  template:
    metadata:
      labels:
        app: lancedb-indexer
    spec:
      containers:
      - name: indexer
        image: your-registry/lancedb-indexer:latest
        env:
        - name: KAFKA_BROKERS
          value: "kafka:9092"
        - name: KAFKA_TOPIC
          value: "scraper-notifications"
        - name: LANCEDB_PATH
          value: "/data/lancedb"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-secret
              key: api-key
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: aws-credentials
              key: access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: aws-credentials
              key: secret-access-key
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        volumeMounts:
        - name: lancedb-storage
          mountPath: /data/lancedb
      volumes:
      - name: lancedb-storage
        persistentVolumeClaim:
          claimName: lancedb-pvc
```

**k8s/api-deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: lancedb-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: lancedb-api
  template:
    metadata:
      labels:
        app: lancedb-api
    spec:
      containers:
      - name: api
        image: your-registry/lancedb-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: LANCEDB_PATH
          value: "/data/lancedb"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-secret
              key: api-key
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1"
        volumeMounts:
        - name: lancedb-storage
          mountPath: /data/lancedb
          readOnly: true
      volumes:
      - name: lancedb-storage
        persistentVolumeClaim:
          claimName: lancedb-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: lancedb-api
spec:
  selector:
    app: lancedb-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## Testing

### Manual Testing

```bash
# 1. Start indexer locally
export KAFKA_BROKERS="localhost:9092"
export LANCEDB_PATH="./test_lancedb"
export OPENAI_API_KEY="sk-..."
python -m indexer.indexer_service

# 2. Start API locally
python -m api.main

# 3. Test API
curl http://localhost:8000/api/v1/scrapes/search?data_source=NYISO&limit=10

# 4. Test semantic search
curl -X GET "http://localhost:8000/api/v1/scrapes/search?query=load%20forecast&limit=5"

# 5. Test hash lookup
curl http://localhost:8000/api/v1/scrapes/abc123...

# 6. Test agent context API
curl -X POST http://localhost:8000/api/v1/agents/context/similar-apis \
  -H "Content-Type: application/json" \
  -d '{"endpoint": "https://api.nyiso.com/v1/load", "method": "GET"}'
```

---

## Success Criteria

### Phase 1: Indexer Working (Week 1-2)
- ✅ Consumes Kafka notifications
- ✅ Downloads files from S3
- ✅ Generates embeddings (OpenAI)
- ✅ Inserts into LanceDB
- ✅ Throughput: 100+ files/minute

### Phase 2: API Working (Week 3-4)
- ✅ All query endpoints functional
- ✅ Frontend search works (4 types)
- ✅ Agent context APIs working
- ✅ Query latency p95 < 500ms

### Phase 3: Production Ready (Week 5-6)
- ✅ K8s deployments stable
- ✅ Auto-scaling configured
- ✅ Monitoring dashboards operational
- ✅ Cost tracking within budget

---

## Next Steps

1. **Set up development environment**
   - Clone repo, install dependencies
   - Connect to test Kafka broker
   - Test with sample notifications

2. **Build and test locally**
   - Run indexer against test data
   - Verify LanceDB tables created
   - Test API endpoints

3. **Deploy to K8s**
   - Build Docker images
   - Deploy indexer and API
   - Configure auto-scaling

4. **Create MCP server**
   - Package as MCP-compatible tool
   - Test with Claude Code locally
   - Deploy MCP server

5. **Integration with plugin**
   - Provide MCP server URL to plugin team
   - Plugin team adds MCP tool calls to agents
   - Test end-to-end workflow
