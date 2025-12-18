"""Pytest configuration and fixtures.

This module sets up pytest configuration including:
- Ensuring baml_client.types module is accessible
"""

import sys

# Import baml_client to trigger the sys.modules setup for baml_client.types
import baml_client  # noqa: F401
