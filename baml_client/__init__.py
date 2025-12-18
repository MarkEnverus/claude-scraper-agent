"""BAML Client package.

This package re-exports the generated BAML client components.
"""

# Re-export from baml_client.baml_client for convenience
from baml_client.baml_client import b, tracing, stream_types, config, reset_baml_env_vars, watchers
# Import types module to make it accessible as baml_client.types
from baml_client.baml_client import types as _types_module
import sys

# Make types module accessible as baml_client.types
# This must happen at import time, before any code tries to import from baml_client.types
sys.modules['baml_client.types'] = _types_module

# Also expose types as an attribute
types = _types_module

__all__ = [
    "b",
    "types",
    "tracing",
    "stream_types",
    "config",
    "reset_baml_env_vars",
    "watchers",
]
