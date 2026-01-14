"""Unit tests for vision_utils module.

Tests:
- Screenshot saving
- SPA detection
- Image encoding
- Screenshot validation
"""

import tempfile
from pathlib import Path
import pytest

from agentic_scraper.business_analyst.utils.vision_utils import (
    save_screenshot,
    is_spa_likely,
    encode_image_to_base64,
    validate_screenshot_quality,
)


class TestSaveScreenshot:
    """Tests for save_screenshot function."""

    def test_save_screenshot_success(self):
        """Test successful screenshot save."""
        # Create fake PNG data
        png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            screenshot_path = save_screenshot(png_data, output_dir, page_num=1)

            # Verify file exists
            assert Path(screenshot_path).exists()

            # Verify content
            with open(screenshot_path, 'rb') as f:
                saved_data = f.read()
            assert saved_data == png_data

    def test_save_screenshot_creates_directory(self):
        """Test that save_screenshot creates output directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "screenshots"
            assert not output_dir.exists()

            png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
            screenshot_path = save_screenshot(png_data, output_dir, page_num=1)

            # Verify directory was created
            assert output_dir.exists()
            assert Path(screenshot_path).exists()

    def test_save_screenshot_custom_prefix(self):
        """Test screenshot save with custom filename prefix."""
        png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            screenshot_path = save_screenshot(
                png_data,
                output_dir,
                page_num=2,
                filename_prefix="api_docs"
            )

            assert "api_docs_page_2.png" in screenshot_path


class TestIsSpaLikely:
    """Tests for is_spa_likely function."""

    def test_spa_detection_hash_routing(self):
        """Test SPA detection via hash routing in URL."""
        headers = {"content-type": "text/html"}
        url = "https://example.com/#/api-docs"

        assert is_spa_likely(headers, url) is True

    def test_spa_detection_hash_bang(self):
        """Test SPA detection via hashbang routing."""
        headers = {"content-type": "text/html"}
        url = "https://example.com/#!/app"

        assert is_spa_likely(headers, url) is True

    def test_spa_detection_react_header(self):
        """Test SPA detection via React in X-Powered-By header."""
        headers = {"x-powered-by": "React"}
        url = "https://example.com/docs"

        assert is_spa_likely(headers, url) is True

    def test_spa_detection_vue_header(self):
        """Test SPA detection via Vue in X-Powered-By header."""
        headers = {"X-Powered-By": "Vue.js"}
        url = "https://example.com/docs"

        assert is_spa_likely(headers, url) is True

    def test_spa_detection_javascript_content_type(self):
        """Test SPA detection via JavaScript content-type."""
        headers = {"content-type": "application/javascript"}
        url = "https://example.com/app"

        assert is_spa_likely(headers, url) is True

    def test_spa_detection_app_url_pattern(self):
        """Test SPA detection via /app/ URL pattern."""
        headers = {"content-type": "text/html"}
        url = "https://example.com/app/dashboard"

        assert is_spa_likely(headers, url) is True

    def test_not_spa_static_page(self):
        """Test that static pages are not detected as SPA."""
        headers = {"content-type": "text/html"}
        url = "https://example.com/docs/api.html"

        assert is_spa_likely(headers, url) is False

    def test_not_spa_no_indicators(self):
        """Test that pages without SPA indicators return False."""
        headers = {"content-type": "text/html", "server": "nginx"}
        url = "https://example.com/about"

        assert is_spa_likely(headers, url) is False


class TestEncodeImageToBase64:
    """Tests for encode_image_to_base64 function."""

    def test_encode_image_success(self):
        """Test successful image encoding."""
        # Create fake PNG file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
            tmp.write(png_data)
            tmp_path = tmp.name

        try:
            encoded = encode_image_to_base64(tmp_path)

            # Verify encoding
            assert isinstance(encoded, str)
            assert len(encoded) > 0

            # Verify it's valid base64
            import base64
            decoded = base64.b64decode(encoded)
            assert decoded == png_data

        finally:
            Path(tmp_path).unlink()

    def test_encode_image_not_found(self):
        """Test encoding non-existent image raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            encode_image_to_base64("/nonexistent/image.png")


class TestValidateScreenshotQuality:
    """Tests for validate_screenshot_quality function."""

    def test_validate_valid_screenshot(self):
        """Test validation of valid screenshot."""
        # Create fake PNG file with reasonable size
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 5000  # 5KB
            tmp.write(png_data)
            tmp_path = tmp.name

        try:
            is_valid = validate_screenshot_quality(tmp_path)
            assert is_valid is True
        finally:
            Path(tmp_path).unlink()

    def test_validate_file_not_found(self):
        """Test validation fails for non-existent file."""
        is_valid = validate_screenshot_quality("/nonexistent/screenshot.png")
        assert is_valid is False

    def test_validate_file_too_small(self):
        """Test validation fails for file that's too small."""
        # Create tiny file (likely corrupted)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(b'x' * 100)  # 100 bytes
            tmp_path = tmp.name

        try:
            is_valid = validate_screenshot_quality(tmp_path, min_size_bytes=1024)
            assert is_valid is False
        finally:
            Path(tmp_path).unlink()

    def test_validate_file_too_large(self):
        """Test validation fails for file that's too large."""
        # Create large file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            large_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * (11 * 1024 * 1024)  # 11MB
            tmp.write(large_data)
            tmp_path = tmp.name

        try:
            is_valid = validate_screenshot_quality(
                tmp_path,
                max_size_bytes=10 * 1024 * 1024
            )
            assert is_valid is False
        finally:
            Path(tmp_path).unlink()

    def test_validate_custom_size_limits(self):
        """Test validation with custom size limits."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 2000)  # 2KB
            tmp_path = tmp.name

        try:
            # Should pass with min=1KB, max=10KB
            is_valid = validate_screenshot_quality(
                tmp_path,
                min_size_bytes=1024,
                max_size_bytes=10 * 1024
            )
            assert is_valid is True

            # Should fail with min=5KB
            is_valid = validate_screenshot_quality(
                tmp_path,
                min_size_bytes=5 * 1024
            )
            assert is_valid is False

        finally:
            Path(tmp_path).unlink()
