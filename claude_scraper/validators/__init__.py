"""Validation module for generated scraper code.

This module provides validation to ensure generated scrapers conform to the
BaseCollector interface contract.
"""

from .config import ValidationConfig
from .interface_extractor import InterfaceExtractor, InterfaceDefinition, MethodSignature
from .code_validator import CodeValidator, ValidationReport, ValidationError, ValidationLevel

__all__ = [
    "ValidationConfig",
    "InterfaceExtractor",
    "InterfaceDefinition",
    "MethodSignature",
    "CodeValidator",
    "ValidationReport",
    "ValidationError",
    "ValidationLevel",
]
