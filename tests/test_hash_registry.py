"""Tests for Redis hash registry."""

import pytest
from unittest.mock import Mock
import json

# Add parent directory to path for imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sourcing.commons.hash_registry import HashRegistry


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = Mock()
    redis_mock.exists = Mock(return_value=0)
    redis_mock.setex = Mock()
    redis_mock.get = Mock(return_value=None)
    redis_mock.delete = Mock(return_value=0)
    redis_mock.scan = Mock(return_value=(0, []))
    return redis_mock


@pytest.fixture
def registry(mock_redis):
    """HashRegistry instance with mocked Redis."""
    return HashRegistry(mock_redis, environment='dev', ttl_days=365)


def test_init_valid_environment(mock_redis):
    """Test initialization with valid environment."""
    registry = HashRegistry(mock_redis, 'dev')
    assert registry.environment == 'dev'
    assert registry.ttl_seconds == 365 * 86400


def test_init_invalid_environment(mock_redis):
    """Test initialization with invalid environment."""
    with pytest.raises(ValueError, match="Invalid environment"):
        HashRegistry(mock_redis, 'invalid')


def test_calculate_hash(registry):
    """Test SHA256 hash calculation."""
    content = b"test data"
    hash_result = registry.calculate_hash(content)

    assert isinstance(hash_result, str)
    assert len(hash_result) == 64  # SHA256 produces 64 hex characters
    # Hash should be consistent
    assert hash_result == registry.calculate_hash(content)


def test_make_key(registry):
    """Test Redis key generation."""
    key = registry._make_key('nyiso_load', 'abc123')

    assert key == 'hash:dev:nyiso_load:abc123'


def test_exists_true(registry, mock_redis):
    """Test exists when hash is found."""
    mock_redis.exists.return_value = 1

    assert registry.exists('abc123', 'nyiso_load') is True
    mock_redis.exists.assert_called_once_with('hash:dev:nyiso_load:abc123')


def test_exists_false(registry, mock_redis):
    """Test exists when hash is not found."""
    mock_redis.exists.return_value = 0

    assert registry.exists('abc123', 'nyiso_load') is False


def test_register(registry, mock_redis):
    """Test hash registration."""
    content_hash = 'abc123def456'
    dgroup = 'nyiso_load'
    s3_path = 's3://bucket/path/file.json.gz'
    metadata = {'source': 'nyiso', 'data_type': 'load'}

    registry.register(content_hash, dgroup, s3_path, metadata)

    # Verify setex was called
    assert mock_redis.setex.called
    call_args = mock_redis.setex.call_args
    key, ttl, value = call_args[0]

    assert key == 'hash:dev:nyiso_load:abc123def456'
    assert ttl == 365 * 86400

    # Parse stored value
    stored_data = json.loads(value)
    assert stored_data['s3_path'] == s3_path
    assert stored_data['metadata'] == metadata
    assert 'registered_at' in stored_data


def test_get_metadata_found(registry, mock_redis):
    """Test metadata retrieval when hash exists."""
    stored_record = {
        's3_path': 's3://bucket/path/file.json.gz',
        'registered_at': '2025-01-20T14:30:00Z',
        'metadata': {'source': 'nyiso'}
    }
    mock_redis.get.return_value = json.dumps(stored_record).encode()

    metadata = registry.get_metadata('abc123', 'nyiso_load')

    assert metadata == stored_record
    assert metadata['s3_path'] == 's3://bucket/path/file.json.gz'


def test_get_metadata_not_found(registry, mock_redis):
    """Test metadata retrieval when hash doesn't exist."""
    mock_redis.get.return_value = None

    metadata = registry.get_metadata('abc123', 'nyiso_load')

    assert metadata is None


def test_delete_success(registry, mock_redis):
    """Test hash deletion when exists."""
    mock_redis.delete.return_value = 1

    result = registry.delete('abc123', 'nyiso_load')

    assert result is True
    mock_redis.delete.assert_called_once_with('hash:dev:nyiso_load:abc123')


def test_delete_not_found(registry, mock_redis):
    """Test hash deletion when doesn't exist."""
    mock_redis.delete.return_value = 0

    result = registry.delete('abc123', 'nyiso_load')

    assert result is False


def test_count(registry, mock_redis):
    """Test counting hashes for a data group."""
    # Mock SCAN to return some keys
    mock_redis.scan.side_effect = [
        (100, ['key1', 'key2', 'key3']),  # First call
        (0, ['key4', 'key5'])             # Second call (cursor=0 means done)
    ]

    count = registry.count('nyiso_load')

    assert count == 5
    assert mock_redis.scan.call_count == 2


def test_environment_isolation():
    """Test that different environments use different keys."""
    mock_redis = Mock()

    dev_registry = HashRegistry(mock_redis, 'dev')
    prod_registry = HashRegistry(mock_redis, 'prod')

    dev_key = dev_registry._make_key('nyiso_load', 'abc123')
    prod_key = prod_registry._make_key('nyiso_load', 'abc123')

    assert dev_key == 'hash:dev:nyiso_load:abc123'
    assert prod_key == 'hash:prod:nyiso_load:abc123'
    assert dev_key != prod_key


def test_ttl_calculation():
    """Test TTL calculation for different durations."""
    mock_redis = Mock()

    registry_30 = HashRegistry(mock_redis, 'dev', ttl_days=30)
    registry_365 = HashRegistry(mock_redis, 'dev', ttl_days=365)

    assert registry_30.ttl_seconds == 30 * 86400
    assert registry_365.ttl_seconds == 365 * 86400


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
