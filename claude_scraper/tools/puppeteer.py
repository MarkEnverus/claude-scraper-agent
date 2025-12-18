"""Puppeteer tool wrapper for BA analyzer.

This module provides browser automation using Puppeteer via Node.js subprocess.
"""

import logging
import json
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


class PuppeteerTool:
    """Wrapper for Puppeteer via subprocess.

    Runs Puppeteer scripts via Node.js to provide browser automation:
    - Page navigation with JavaScript execution
    - HTML content extraction after page load
    - Network traffic monitoring
    - Screenshot capture
    """

    def __init__(self) -> None:
        """Initialize Puppeteer tool."""
        logger.info("Initializing PuppeteerTool")
        self._check_puppeteer_available()

    def _check_puppeteer_available(self) -> None:
        """Check if npx and puppeteer are available."""
        try:
            result = subprocess.run(
                ["npx", "--yes", "puppeteer", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logger.info(f"Puppeteer available: {result.stdout.strip()}")
            else:
                logger.warning("Puppeteer check failed, but continuing")
        except Exception as e:
            logger.warning(f"Could not verify Puppeteer availability: {e}")

    def get_page_content(self, url: str, wait_for_selector: Optional[str] = None) -> str:
        """Fetch page content after JavaScript execution.

        Args:
            url: URL to fetch
            wait_for_selector: Optional CSS selector to wait for before extracting content

        Returns:
            HTML content after JavaScript execution

        Raises:
            RuntimeError: If page fetch fails
        """
        logger.info(f"Fetching page content with Puppeteer: {url}")

        script = f"""
const puppeteer = require('puppeteer');

(async () => {{
    const browser = await puppeteer.launch({{
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }});

    try {{
        const page = await browser.newPage();
        await page.goto('{url}', {{ waitUntil: 'networkidle2', timeout: 30000 }});

        {'await page.waitForSelector("' + wait_for_selector + '", { timeout: 10000 });' if wait_for_selector else ''}

        const html = await page.content();
        console.log(JSON.stringify({{ html: html }}));
    }} finally {{
        await browser.close();
    }}
}})().catch(err => {{
    console.error(JSON.stringify({{ error: err.message }}));
    process.exit(1);
}});
"""

        try:
            # Write script to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(script)
                script_path = f.name

            try:
                result = subprocess.run(
                    ["node", script_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env={**os.environ, "PUPPETEER_SKIP_DOWNLOAD": "false"}
                )
            finally:
                # Clean up temp file
                try:
                    os.unlink(script_path)
                except:
                    pass

            if result.returncode != 0:
                logger.error(f"Puppeteer error: {result.stderr}")
                raise RuntimeError(f"Puppeteer failed: {result.stderr}")

            # Parse JSON output
            output = result.stdout.strip().split('\n')[-1]
            data = json.loads(output)

            if 'error' in data:
                raise RuntimeError(f"Puppeteer error: {data['error']}")

            logger.info(f"Successfully fetched page content ({len(data['html'])} bytes)")
            return data['html']

        except subprocess.TimeoutExpired:
            logger.error(f"Puppeteer timeout after 60s for {url}")
            raise RuntimeError(f"Puppeteer timeout for {url}")
        except Exception as e:
            logger.error(f"Puppeteer execution failed: {e}")
            raise RuntimeError(f"Puppeteer failed: {e}")

    def extract_network_calls(self, url: str) -> list[str]:
        """Extract network API calls from page load.

        Args:
            url: URL to navigate to and monitor

        Returns:
            List of API endpoint URLs discovered

        Raises:
            RuntimeError: If extraction fails
        """
        logger.info(f"Extracting network calls from {url}")

        script = f"""
const puppeteer = require('puppeteer');

(async () => {{
    const browser = await puppeteer.launch({{
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }});

    try {{
        const page = await browser.newPage();
        const apiCalls = [];

        // Monitor network requests
        page.on('request', request => {{
            const url = request.url();
            const resourceType = request.resourceType();

            // Filter for API-like requests
            if (
                resourceType === 'fetch' ||
                resourceType === 'xhr' ||
                url.includes('/api/') ||
                url.includes('.json') ||
                (url.includes('http') && !url.includes('.css') && !url.includes('.js') && !url.includes('.png') && !url.includes('.jpg'))
            ) {{
                apiCalls.push(url);
            }}
        }});

        await page.goto('{url}', {{ waitUntil: 'networkidle2', timeout: 30000 }});

        // Wait a bit more for lazy-loaded content
        await page.waitForTimeout(2000);

        console.log(JSON.stringify({{ api_calls: apiCalls }}));
    }} finally {{
        await browser.close();
    }}
}})().catch(err => {{
    console.error(JSON.stringify({{ error: err.message }}));
    process.exit(1);
}});
"""

        try:
            # Write script to temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(script)
                script_path = f.name

            try:
                result = subprocess.run(
                    ["node", script_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env={**os.environ, "PUPPETEER_SKIP_DOWNLOAD": "false"}
                )
            finally:
                # Clean up temp file
                try:
                    os.unlink(script_path)
                except:
                    pass

            if result.returncode != 0:
                logger.error(f"Puppeteer error: {result.stderr}")
                return []

            # Parse JSON output
            output = result.stdout.strip().split('\n')[-1]
            data = json.loads(output)

            if 'error' in data:
                logger.error(f"Puppeteer error: {data['error']}")
                return []

            api_calls = data.get('api_calls', [])
            logger.info(f"Extracted {len(api_calls)} network calls")
            return api_calls

        except subprocess.TimeoutExpired:
            logger.error(f"Puppeteer timeout after 60s for {url}")
            return []
        except Exception as e:
            logger.error(f"Puppeteer execution failed: {e}")
            return []

    def navigate(self, url: str) -> None:
        """Navigate to URL (compatibility method).

        For backward compatibility. Use get_page_content() instead.
        """
        self.get_page_content(url)

    def screenshot(self, path: Optional[str] = None) -> bytes:
        """Take screenshot (not implemented).

        Placeholder for future screenshot functionality.
        """
        raise NotImplementedError("Screenshot functionality not yet implemented")

    def evaluate(self, script: str) -> str:
        """Evaluate JavaScript (not implemented).

        Placeholder for future JavaScript evaluation.
        """
        raise NotImplementedError("JavaScript evaluation not yet implemented")
