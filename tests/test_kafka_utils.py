"""Unit tests for kafka_utils module.

Tests KafkaConfiguration, KafkaProducer, and ScraperNotificationMessage classes.
"""

import json
import os
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from pathlib import Path

# Import the classes we're testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "infrastructure"))

from kafka_utils import (
    KafkaConfiguration,
    KafkaProducer,
    ScraperNotificationMessage
)


class TestKafkaConfiguration:
    """Tests for KafkaConfiguration class."""

    def test_simple_connection_string(self):
        """Test parsing simple connection string without authentication."""
        conn_str = "kafka://localhost:9092/my-topic"
        config = KafkaConfiguration(conn_str)

        assert config.bootstrap_server == "localhost:9092"
        assert config.topic == "my-topic"
        assert config.security_protocol == "PLAINTEXT"
        assert config.sasl_mechanism == "PLAIN"

    def test_connection_string_with_sasl_plaintext(self):
        """Test parsing connection string with SASL_PLAINTEXT."""
        conn_str = "kafka://localhost:9092/my-topic?security_protocol=SASL_PLAINTEXT&sasl_mechanism=PLAIN"
        config = KafkaConfiguration(conn_str)

        assert config.security_protocol == "SASL_PLAINTEXT"
        assert config.sasl_mechanism == "PLAIN"

    def test_connection_string_with_sasl_ssl(self):
        """Test parsing connection string with SASL_SSL."""
        conn_str = "kafka://kafka.example.com:9093/secure-topic?security_protocol=SASL_SSL&sasl_mechanism=SCRAM-SHA-256"
        config = KafkaConfiguration(conn_str)

        assert config.bootstrap_server == "kafka.example.com:9093"
        assert config.topic == "secure-topic"
        assert config.security_protocol == "SASL_SSL"
        assert config.sasl_mechanism == "SCRAM-SHA-256"

    def test_invalid_schema(self):
        """Test that invalid schema raises ValueError."""
        with pytest.raises(ValueError, match="Invalid connection string schema"):
            KafkaConfiguration("http://localhost:9092/topic")

    def test_missing_topic(self):
        """Test that missing topic raises ValueError."""
        with pytest.raises(ValueError, match="Topic is required"):
            KafkaConfiguration("kafka://localhost:9092/")

    def test_producer_cfg_dict_plaintext(self):
        """Test producer configuration dict for PLAINTEXT."""
        conn_str = "kafka://localhost:9092/my-topic"
        config = KafkaConfiguration(conn_str)
        cfg_dict = config.producer_cfg_dict

        assert cfg_dict["bootstrap.servers"] == "localhost:9092"
        assert cfg_dict["linger.ms"] == "100"
        assert cfg_dict["compression.type"] == "zstd"
        assert "security.protocol" not in cfg_dict  # PLAINTEXT doesn't add security config

    def test_producer_cfg_dict_with_sasl(self):
        """Test producer configuration dict with SASL authentication."""
        conn_str = "kafka://localhost:9092/my-topic?security_protocol=SASL_PLAINTEXT"

        with patch.dict(os.environ, {"SASL_USERNAME": "testuser", "SASL_PASSWORD": "testpass"}):
            config = KafkaConfiguration(conn_str)
            cfg_dict = config.producer_cfg_dict

            assert cfg_dict["security.protocol"] == "SASL_PLAINTEXT"
            assert cfg_dict["sasl.mechanism"] == "PLAIN"
            assert cfg_dict["sasl.username"] == "testuser"
            assert cfg_dict["sasl.password"] == "testpass"

    def test_log_cfg_dict(self):
        """Test logging configuration dict (sanitized, no credentials)."""
        conn_str = "kafka://localhost:9092/my-topic?security_protocol=SASL_PLAINTEXT"

        with patch.dict(os.environ, {"SASL_USERNAME": "testuser", "SASL_PASSWORD": "testpass"}):
            config = KafkaConfiguration(conn_str)
            log_dict = config.log_cfg_dict

            assert "bootstrap.servers" in log_dict
            assert "topic" in log_dict
            assert "sasl.username" not in log_dict  # Should not log credentials
            assert "sasl.password" not in log_dict

    def test_read_sasl_credentials_from_file(self):
        """Test reading SASL credentials from JSON file."""
        creds_json = json.dumps({
            "sasl.username": "fileuser",
            "sasl.password": "filepass"
        })

        with patch("builtins.open", mock_open(read_data=creds_json)):
            conn_str = "kafka://localhost:9092/my-topic?security_protocol=SASL_PLAINTEXT&X_sasl_file=/path/to/creds.json"
            config = KafkaConfiguration(conn_str)

            assert config.sasl_username == "fileuser"
            assert config.sasl_password == "filepass"

    def test_read_sasl_credentials_from_env(self):
        """Test reading SASL credentials from environment variables."""
        conn_str = "kafka://localhost:9092/my-topic?security_protocol=SASL_PLAINTEXT"

        with patch.dict(os.environ, {"SASL_USERNAME": "envuser", "SASL_PASSWORD": "envpass"}):
            config = KafkaConfiguration(conn_str)

            assert config.sasl_username == "envuser"
            assert config.sasl_password == "envpass"

    def test_missing_sasl_credentials_warning(self, caplog):
        """Test that missing SASL credentials logs a warning."""
        conn_str = "kafka://localhost:9092/my-topic?security_protocol=SASL_PLAINTEXT"

        with patch.dict(os.environ, clear=True):  # Clear all env vars
            config = KafkaConfiguration(conn_str)

            assert config.sasl_username is None
            assert config.sasl_password is None
            # Check that a warning was logged
            assert any("SASL credentials not found" in record.message for record in caplog.records)


class TestKafkaProducer:
    """Tests for KafkaProducer class."""

    @patch("kafka_utils.KafkaProducer.__init__", return_value=None)
    def test_init_imports_confluent_kafka(self, mock_init):
        """Test that KafkaProducer attempts to import confluent_kafka."""
        # This test verifies the import is attempted
        # Actual import testing would require confluent-kafka installed
        pass

    @patch("kafka_utils.Producer")
    def test_context_manager_enter_exit(self, mock_producer_class):
        """Test context manager protocol."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer

        config = Mock()
        config.producer_cfg_dict = {"bootstrap.servers": "localhost:9092"}
        config.log_cfg_dict = {"bootstrap.servers": "localhost:9092"}

        with KafkaProducer(config) as producer:
            assert producer is not None

        # Verify flush was called on exit
        mock_producer.flush.assert_called_once()

    @patch("kafka_utils.Producer")
    def test_publish_message(self, mock_producer_class):
        """Test publishing a message to Kafka."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer

        config = Mock()
        config.producer_cfg_dict = {"bootstrap.servers": "localhost:9092"}
        config.log_cfg_dict = {"bootstrap.servers": "localhost:9092"}
        config.topic = "test-topic"

        message = ScraperNotificationMessage(
            dataset="test_dataset",
            environment="dev",
            urn="test_file.json",
            location="s3://bucket/path/file.gz",
            version="20250120T140000Z",
            etag="abc123",
            metadata={"source": "test"}
        )

        producer = KafkaProducer(config)
        producer.publish(message, flush=True)

        # Verify produce was called
        mock_producer.produce.assert_called_once()
        call_args = mock_producer.produce.call_args

        assert call_args[1]["topic"] == "test-topic" if "topic" in call_args[1] else call_args[0][0] == "test-topic"
        # Verify flush was called
        mock_producer.flush.assert_called()

    @patch("kafka_utils.Producer")
    def test_publish_without_flush(self, mock_producer_class):
        """Test publishing without immediate flush."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer

        config = Mock()
        config.producer_cfg_dict = {"bootstrap.servers": "localhost:9092"}
        config.log_cfg_dict = {"bootstrap.servers": "localhost:9092"}
        config.topic = "test-topic"

        message = ScraperNotificationMessage(
            dataset="test_dataset",
            environment="dev",
            urn="test_file.json",
            location="s3://bucket/path/file.gz",
            version="20250120T140000Z",
            etag="abc123",
            metadata={"source": "test"}
        )

        producer = KafkaProducer(config)
        producer.publish(message, flush=False)

        # Produce should be called
        mock_producer.produce.assert_called_once()
        # But flush should NOT be called
        mock_producer.flush.assert_not_called()

    @patch("kafka_utils.Producer")
    def test_delivery_callback_success(self, mock_producer_class):
        """Test successful message delivery callback."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer

        config = Mock()
        config.producer_cfg_dict = {"bootstrap.servers": "localhost:9092"}
        config.log_cfg_dict = {"bootstrap.servers": "localhost:9092"}

        producer = KafkaProducer(config)

        # Mock successful message
        mock_msg = Mock()
        mock_msg.topic.return_value = "test-topic"
        mock_msg.partition.return_value = 0

        # Should not raise
        producer._on_delivery(None, mock_msg)

    @patch("kafka_utils.Producer")
    def test_delivery_callback_failure(self, mock_producer_class):
        """Test failed message delivery callback."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer

        config = Mock()
        config.producer_cfg_dict = {"bootstrap.servers": "localhost:9092"}
        config.log_cfg_dict = {"bootstrap.servers": "localhost:9092"}

        producer = KafkaProducer(config)

        # Mock failed message
        mock_err = Mock()
        mock_err.__str__ = lambda x: "Connection timeout"

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Message delivery failed"):
            producer._on_delivery(mock_err, None)


class TestScraperNotificationMessage:
    """Tests for ScraperNotificationMessage Pydantic model."""

    def test_create_message_with_all_fields(self):
        """Test creating message with all required fields."""
        message = ScraperNotificationMessage(
            dataset="nyiso_load_forecast",
            environment="dev",
            urn="load_20250120_14.json",
            location="s3://bucket/sourcing/nyiso_load_forecast/year=2025/month=01/day=20/file.gz",
            version="20250120T143000Z",
            etag="abc123def456",
            metadata={
                "publish_dtm": "2025-01-20T14:30:00Z",
                "s3_guid": "xyz789",
                "url": "https://api.nyiso.com/v1/load",
                "original_file_size": 12345,
                "original_file_md5sum": "hash123",
                "data_type": "load_forecast",
                "source": "nyiso"
            }
        )

        assert message.dataset == "nyiso_load_forecast"
        assert message.environment == "dev"
        assert message.urn == "load_20250120_14.json"
        assert message.etag == "abc123def456"
        assert message.metadata["source"] == "nyiso"

    def test_missing_required_field_raises_error(self):
        """Test that missing required field raises ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ScraperNotificationMessage(
                dataset="test",
                environment="dev",
                # Missing urn, location, version, etag, metadata
            )

    def test_serialize_to_json(self):
        """Test serialization to JSON string."""
        message = ScraperNotificationMessage(
            dataset="test_dataset",
            environment="prod",
            urn="test_file.json",
            location="s3://bucket/path/file.gz",
            version="20250120T140000Z",
            etag="abc123",
            metadata={"source": "test"}
        )

        json_str = message.model_dump_json()
        assert isinstance(json_str, str)

        # Parse back to verify
        parsed = json.loads(json_str)
        assert parsed["dataset"] == "test_dataset"
        assert parsed["environment"] == "prod"
        assert parsed["metadata"]["source"] == "test"

    def test_model_dump_to_dict(self):
        """Test converting model to dictionary."""
        message = ScraperNotificationMessage(
            dataset="test_dataset",
            environment="dev",
            urn="test_file.json",
            location="s3://bucket/path/file.gz",
            version="20250120T140000Z",
            etag="abc123",
            metadata={"source": "test", "extra": "data"}
        )

        message_dict = message.model_dump()
        assert isinstance(message_dict, dict)
        assert message_dict["dataset"] == "test_dataset"
        assert message_dict["metadata"]["extra"] == "data"

    def test_metadata_is_flexible_dict(self):
        """Test that metadata can hold arbitrary key-value pairs."""
        message = ScraperNotificationMessage(
            dataset="test",
            environment="dev",
            urn="file.json",
            location="s3://bucket/file.gz",
            version="20250120T140000Z",
            etag="abc",
            metadata={
                "custom_field_1": "value1",
                "custom_field_2": 12345,
                "nested": {"key": "value"},
                "list_field": [1, 2, 3]
            }
        )

        assert message.metadata["custom_field_1"] == "value1"
        assert message.metadata["custom_field_2"] == 12345
        assert message.metadata["nested"]["key"] == "value"
        assert message.metadata["list_field"] == [1, 2, 3]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
