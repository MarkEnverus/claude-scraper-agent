"""Vision utilities for BA Analyst - Multimodal LLM calls and screenshot handling.

This module provides utilities for:
- Invoking LLM with vision (screenshots + text)
- Saving screenshots
- Detecting Single Page Applications (SPA)
"""

import base64
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


def invoke_with_vision(
    llm: Any,
    prompt: str,
    images: List[str],
    markdown: Optional[str] = None,
    schema: Optional[Type[T]] = None,
    system: str = ""
) -> T:
    """Invoke LLM with vision capabilities (multimodal).

    Combines screenshots with text/markdown content for AI analysis.
    Uses structured output if schema is provided.

    Args:
        llm: LLM provider with vision support (AnthropicProvider, BedrockProvider)
        prompt: Text prompt describing the analysis task
        images: List of image file paths (screenshots)
        markdown: Optional markdown content to include alongside images
        schema: Optional Pydantic model for structured output
        system: Optional system prompt

    Returns:
        Structured output matching schema (if provided), or raw text

    Raises:
        FileNotFoundError: If image paths don't exist
        ValueError: If LLM doesn't support vision
        Exception: If LLM call fails

    Example:
        >>> from agentic_scraper.types import Phase0Detection
        >>> result = invoke_with_vision(
        ...     llm=provider,
        ...     prompt="Count all operations visible in this screenshot",
        ...     images=["/path/to/screenshot.png"],
        ...     schema=Phase0Detection,
        ...     system="You are analyzing API documentation"
        ... )
        >>> print(result.discovered_endpoint_urls)
    """
    if not images:
        raise ValueError("At least one image path is required for vision analysis")

    # Validate image paths exist
    for image_path in images:
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

    # Build full prompt with optional markdown
    full_prompt = prompt
    if markdown:
        full_prompt = f"{prompt}\n\n**Markdown Content:**\n{markdown[:5000]}"  # Limit markdown to 5k chars

    logger.info(
        f"Invoking LLM with vision: {len(images)} images, "
        f"prompt={len(prompt)} chars, markdown={len(markdown) if markdown else 0} chars"
    )

    try:
        # Check if LLM has vision capability
        if not hasattr(llm, 'invoke_structured_with_vision'):
            raise ValueError("LLM provider does not support vision (missing invoke_structured_with_vision)")

        # Call LLM with vision
        if schema:
            result = llm.invoke_structured_with_vision(
                prompt=full_prompt,
                images=images,
                response_model=schema,
                system=system
            )
        else:
            # Fallback to text output (if LLM supports it)
            if not hasattr(llm, 'invoke_with_vision'):
                raise ValueError("LLM provider does not support unstructured vision output")
            result = llm.invoke_with_vision(
                prompt=full_prompt,
                images=images,
                system=system
            )

        logger.info("Successfully completed vision-based LLM analysis")
        return result

    except Exception as e:
        logger.error(f"Vision LLM call failed: {e}", exc_info=True)
        raise


def save_screenshot(
    data: bytes,
    output_dir: Path,
    page_num: int,
    filename_prefix: str = "screenshot"
) -> str:
    """Save screenshot PNG to disk.

    Args:
        data: Raw PNG bytes
        output_dir: Directory to save screenshot
        page_num: Page number for filename
        filename_prefix: Prefix for filename (default: "screenshot")

    Returns:
        Full path to saved screenshot file

    Raises:
        OSError: If file write fails

    Example:
        >>> screenshot_path = save_screenshot(
        ...     data=png_bytes,
        ...     output_dir=Path("./screenshots"),
        ...     page_num=1
        ... )
        >>> print(screenshot_path)
        /path/to/screenshots/screenshot_page_1.png
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    screenshot_path = output_dir / f"{filename_prefix}_page_{page_num}.png"

    try:
        with open(screenshot_path, 'wb') as f:
            f.write(data)

        logger.info(f"Saved screenshot: {screenshot_path} ({len(data)} bytes)")
        return str(screenshot_path)

    except OSError as e:
        logger.error(f"Failed to save screenshot to {screenshot_path}: {e}")
        raise


def is_spa_likely(headers: Dict[str, str], url: str) -> bool:
    """Heuristic to detect if a page is likely a Single Page Application (SPA).

    Checks for common SPA indicators:
    - Hash routing in URL (#/)
    - Content-Type: application/javascript or text/javascript
    - X-Powered-By headers mentioning React, Vue, Angular
    - URL patterns suggesting SPA frameworks

    Args:
        headers: HTTP response headers from page fetch
        url: Page URL

    Returns:
        True if page appears to be SPA, False otherwise

    Example:
        >>> headers = {"content-type": "text/html", "x-powered-by": "React"}
        >>> url = "https://example.com/#/api-docs"
        >>> is_spa = is_spa_likely(headers, url)
        >>> print(is_spa)
        True
    """
    # Check URL for hash routing (common in SPAs)
    if '#/' in url or '#!' in url:
        logger.debug(f"SPA indicator: Hash routing in URL ({url})")
        return True

    # Check headers for SPA framework indicators
    headers_lower = {k.lower(): v.lower() for k, v in headers.items()}

    # Check X-Powered-By header
    powered_by = headers_lower.get('x-powered-by', '')
    spa_frameworks = ['react', 'vue', 'angular', 'ember', 'backbone', 'next.js', 'nuxt', 'gatsby']
    if any(framework in powered_by for framework in spa_frameworks):
        logger.debug(f"SPA indicator: X-Powered-By header mentions framework ({powered_by})")
        return True

    # Check for JavaScript content type (less reliable, but possible)
    content_type = headers_lower.get('content-type', '')
    if 'javascript' in content_type:
        logger.debug(f"SPA indicator: JavaScript content-type ({content_type})")
        return True

    # Check for common SPA URL patterns
    spa_patterns = ['/app/', '/dashboard/', '/portal/']
    if any(pattern in url.lower() for pattern in spa_patterns):
        logger.debug(f"SPA indicator: URL pattern suggests web app ({url})")
        return True

    logger.debug(f"No SPA indicators detected for {url}")
    return False


def encode_image_to_base64(image_path: str) -> str:
    """Encode image file to base64 string.

    Utility for converting image files to base64 for API calls.

    Args:
        image_path: Path to image file

    Returns:
        Base64-encoded string

    Raises:
        FileNotFoundError: If image doesn't exist

    Example:
        >>> base64_str = encode_image_to_base64("/path/to/image.png")
        >>> print(base64_str[:50])
        iVBORw0KGgoAAAANSUhEUgAAA...
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with open(path, 'rb') as f:
        image_bytes = f.read()

    encoded = base64.b64encode(image_bytes).decode('utf-8')
    logger.debug(f"Encoded image {image_path} to base64 ({len(encoded)} chars)")
    return encoded


def validate_screenshot_quality(
    screenshot_path: str,
    min_size_bytes: int = 1024,
    max_size_bytes: int = 10 * 1024 * 1024
) -> bool:
    """Validate screenshot quality and size.

    Checks if screenshot meets minimum quality requirements:
    - File exists
    - File size within acceptable range
    - File is readable

    Args:
        screenshot_path: Path to screenshot file
        min_size_bytes: Minimum file size (default: 1KB)
        max_size_bytes: Maximum file size (default: 10MB)

    Returns:
        True if screenshot is valid, False otherwise

    Example:
        >>> is_valid = validate_screenshot_quality("/path/to/screenshot.png")
        >>> if not is_valid:
        ...     print("Screenshot quality check failed")
    """
    path = Path(screenshot_path)

    # Check existence
    if not path.exists():
        logger.warning(f"Screenshot validation failed: File not found ({screenshot_path})")
        return False

    # Check file size
    try:
        size = path.stat().st_size

        if size < min_size_bytes:
            logger.warning(
                f"Screenshot validation failed: File too small "
                f"({size} bytes < {min_size_bytes} bytes) - likely empty or corrupted"
            )
            return False

        if size > max_size_bytes:
            logger.warning(
                f"Screenshot validation failed: File too large "
                f"({size} bytes > {max_size_bytes} bytes) - may cause memory issues"
            )
            return False

        logger.debug(f"Screenshot validation passed: {screenshot_path} ({size} bytes)")
        return True

    except OSError as e:
        logger.error(f"Screenshot validation failed: Could not read file ({e})")
        return False
