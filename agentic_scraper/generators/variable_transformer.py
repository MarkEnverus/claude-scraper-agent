"""Transform BA Analyzer spec to template variables.

This module transforms validated data source specifications from the BA Analyzer
into template variables for Jinja2 rendering and inputs for BAML code generation.
"""

import re
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse


class VariableTransformer:
    """Transform BA Analyzer ValidatedSpec to template variables."""

    def transform(self, ba_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Transform validated spec into template variables and BAML inputs.

        Args:
            ba_spec: Validated data source spec from BA analyzer

        Returns:
            Dictionary with:
                - template_vars: Variables for Jinja2 template rendering
                - baml_inputs: Inputs for BAML function calls
        """
        template_vars = self._extract_template_vars(ba_spec)
        baml_inputs = self._extract_baml_inputs(ba_spec)

        return {
            "template_vars": template_vars,
            "baml_inputs": baml_inputs,
        }

    def _extract_template_vars(self, ba_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Extract variables for Jinja2 templates.

        Args:
            ba_spec: BA Analyzer validated spec

        Returns:
            Dictionary of template variables
        """
        source = ba_spec.get("source", "Unknown")
        source_clean = self._clean_source_name(source)
        data_type = self._infer_data_type(ba_spec)

        # Datasource and Dataset extraction
        # PREFERRED: BA Analyst should provide 'datasource' and 'dataset' fields explicitly
        # FALLBACK: Derive from source name and endpoint info
        # FUTURE: Add AI-based extraction using BAML when fields are missing

        datasource = ba_spec.get("datasource")
        if not datasource:
            # Fallback: Extract short identifier from source name
            # Example: "Example Weather API" -> "example"
            datasource = source_clean.split()[0].lower() if source_clean else "unknown"
            import logging
            logging.warning(
                f"BA spec missing 'datasource' field, derived '{datasource}' from source name. "
                "BA Analyst should provide explicit 'datasource' field."
            )

        dataset = ba_spec.get("dataset")
        if not dataset:
            # Fallback: Use "data" as default
            # Example: For multi-endpoint specs, orchestrator should set this per-endpoint
            dataset = "data"
            import logging
            logging.warning(
                f"BA spec missing 'dataset' field, using fallback '{dataset}'. "
                "BA Analyst should provide explicit 'dataset' field or orchestrator should set per-endpoint."
            )

        return {
            # Basic identification
            "source": source,
            "source_lower": source_clean.lower(),
            "source_upper": source_clean.upper(),
            "source_snake": self._to_snake_case(source_clean),
            "datasource": datasource,
            "datasource_snake": self._to_snake_case(datasource),
            "data_type": data_type,
            "data_type_lower": data_type.lower(),
            "data_type_snake": self._to_snake_case(data_type),
            "dataset": dataset,
            "dataset_snake": self._to_snake_case(dataset),

            # Class and file naming
            "class_name": self._generate_class_name(source_clean, data_type),
            "dgroup": self._generate_dgroup(source_clean, data_type),
            "filename": self._generate_filename(source_clean, data_type),

            # Metadata
            "scraper_version": "2.0.0",
            "infrastructure_version": "1.13.0",
            "generated_date": datetime.now(UTC).strftime("%Y-%m-%d"),
            "generator_agent": "hybrid-template-baml",

            # Collection method
            "collection_method": self._determine_collection_method(ba_spec),
            "scraper_type": self._determine_scraper_type(ba_spec),

            # API details (if applicable)
            "api_base_url": self._extract_base_url(ba_spec),
            "endpoints": self._transform_endpoints(ba_spec.get("endpoints", [])),

            # Authentication
            "auth_required": self._is_auth_required(ba_spec),
            "auth_method": self._extract_auth_method(ba_spec),
            "auth_header_name": self._extract_auth_header_name(ba_spec),
            "auth_env_var": self._generate_auth_env_var(source_clean),

            # Data format
            "data_format": self._extract_data_format(ba_spec),
            "output_format": self._extract_data_format(ba_spec),  # Same as input for now

            # Collection configuration
            "update_frequency": self._extract_update_frequency(ba_spec),
            "historical_support": self._extract_historical_support(ba_spec),
            "timeout_seconds": 30,  # Default
            "retry_attempts": 3,  # Default

            # Imports (will be enriched by BAML)
            "base_imports": self._determine_base_imports(ba_spec),

            # Placeholders for BAML-generated code (filled later)
            "init_code": "",
            "generate_candidates_code": "",
            "collect_content_code": "",
            "validate_content_code": "",
        }

    def _extract_baml_inputs(self, ba_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Extract inputs for BAML function calls.

        Args:
            ba_spec: BA Analyzer validated spec

        Returns:
            Dictionary of BAML function inputs
        """
        auth_info = ba_spec.get("authentication", {})

        return {
            # Authentication details
            "auth_method": auth_info.get("method", "NONE"),
            "auth_header_name": auth_info.get("header_name", ""),
            "auth_details": auth_info.get("notes", ""),
            "registration_url": auth_info.get("registration_url"),

            # Endpoints
            "endpoints": ba_spec.get("endpoints", []),

            # Collection configuration
            "collection_method": self._determine_collection_method(ba_spec),
            "update_frequency": self._extract_update_frequency(ba_spec),
            "historical_support": self._extract_historical_support(ba_spec),

            # Pagination
            "pagination": ba_spec.get("pagination"),

            # Rate limiting
            "rate_limiting": ba_spec.get("rate_limiting", {}),

            # Error handling
            "error_handling": "standard",  # Can be enhanced based on spec
        }

    # Helper methods for name generation

    def _clean_source_name(self, source: str) -> str:
        """Clean source name by removing special characters."""
        # Remove common suffixes and clean
        cleaned = re.sub(r'\s+(API|Energy|Data|Exchange|Portal)$', '', source, flags=re.IGNORECASE)
        cleaned = re.sub(r'[^\w\s]', '', cleaned)
        return cleaned.strip()

    def _to_snake_case(self, text: str) -> str:
        """Convert text to snake_case."""
        # Replace spaces and hyphens with underscores
        text = re.sub(r'[\s\-]+', '_', text)
        # Insert underscore before capitals
        text = re.sub(r'([a-z])([A-Z])', r'\1_\2', text)
        return text.lower()

    def _to_camel_case(self, text: str) -> str:
        """Convert text to CamelCase."""
        words = re.split(r'[\s\-_]+', text)
        return ''.join(word.capitalize() for word in words if word)

    def _generate_class_name(self, source: str, data_type: str) -> str:
        """Generate CamelCase class name.

        Example: "Example", "weather_data" -> "ExampleWeatherDataCollector"
        """
        source_camel = self._to_camel_case(source)
        data_type_camel = self._to_camel_case(data_type)
        return f"{source_camel}{data_type_camel}Collector"

    def _generate_dgroup(self, source: str, data_type: str) -> str:
        """Generate dgroup identifier.

        Example: "Example", "weather_data" -> "example_weather_data"
        """
        source_snake = self._to_snake_case(source)
        data_type_snake = self._to_snake_case(data_type)
        return f"{source_snake}_{data_type_snake}"

    def _generate_filename(self, source: str, data_type: str) -> str:
        """Generate filename for scraper.

        Always returns 'main.py' as per sourcing module conventions.
        """
        return "main.py"

    def _generate_auth_env_var(self, source: str) -> str:
        """Generate environment variable name for authentication.

        Example: "Example" -> "EXAMPLE_API_KEY"
        """
        source_upper = self._to_snake_case(source).upper()
        return f"{source_upper}_API_KEY"

    # Helper methods for data extraction

    def _infer_data_type(self, ba_spec: Dict[str, Any]) -> str:
        """Infer data type from spec."""
        # Try executive summary first
        exec_summary = ba_spec.get("executive_summary", {})
        data_type = exec_summary.get("data_type")

        if data_type:
            return data_type

        # Fall back to parsing source name
        source = ba_spec.get("source", "")
        if "pricing" in source.lower():
            return "pricing"
        elif "load" in source.lower():
            return "load"
        elif "forecast" in source.lower():
            return "forecast"

        return "data"

    def _determine_collection_method(self, ba_spec: Dict[str, Any]) -> str:
        """Determine collection method from spec."""
        source_type = ba_spec.get("source_type", "").upper()

        method_map = {
            "API": "HTTP_REST_API",
            "FTP": "FTP_SFTP",
            "WEBSITE": "WEBSITE_PARSER",
            "EMAIL": "EMAIL_IMAP",
        }

        return method_map.get(source_type, "HTTP_REST_API")

    def _determine_scraper_type(self, ba_spec: Dict[str, Any]) -> str:
        """Determine scraper type (lowercase version for templates)."""
        method = self._determine_collection_method(ba_spec)
        return method.lower().replace("_", "-")

    def _extract_base_url(self, ba_spec: Dict[str, Any]) -> str:
        """Extract base URL from spec."""
        # Try executive summary first
        exec_summary = ba_spec.get("executive_summary", {})
        base_url = exec_summary.get("base_url")

        if base_url:
            return base_url

        # Try first endpoint's base_url field
        endpoints = ba_spec.get("endpoints", [])
        if endpoints:
            first_endpoint = endpoints[0]
            if isinstance(first_endpoint, dict):
                # Try direct base_url field (BA Analyzer format)
                base_url = first_endpoint.get("base_url")
                if base_url:
                    return base_url

                # Fallback: Try to parse from full_url or url
                full_url = first_endpoint.get("full_url") or first_endpoint.get("url", "")
                if full_url:
                    parsed = urlparse(full_url)
                    return f"{parsed.scheme}://{parsed.netloc}"

        return ""

    def _transform_endpoints(self, endpoints: List[Any]) -> List[Dict[str, Any]]:
        """Transform BA endpoints to template-friendly format."""
        transformed = []

        for ep in endpoints:
            if not isinstance(ep, dict):
                continue

            transformed.append({
                "name": ep.get("endpoint_id", ep.get("name", "unknown")),
                "display_name": ep.get("description", ep.get("name", "Unknown Endpoint")),
                "path": ep.get("path", ep.get("url", "")),
                "method": ep.get("method", "GET"),
                "params": ep.get("parameters", {}),
                "auth_required": ep.get("authentication", {}).get("required", True),
                "description": ep.get("description", ""),
            })

        return transformed

    def _is_auth_required(self, ba_spec: Dict[str, Any]) -> bool:
        """Check if authentication is required."""
        auth = ba_spec.get("authentication", {})
        return auth.get("required", False)

    def _extract_auth_method(self, ba_spec: Dict[str, Any]) -> str:
        """Extract authentication method."""
        auth = ba_spec.get("authentication", {})
        method = auth.get("method", "NONE")

        # Normalize to expected values
        method_upper = method.upper()
        if method_upper in ["API_KEY", "APIKEY"]:
            return "API_KEY"
        elif method_upper in ["BEARER", "BEARER_TOKEN"]:
            return "BEARER_TOKEN"
        elif method_upper in ["BASIC", "BASIC_AUTH"]:
            return "BASIC_AUTH"
        elif method_upper == "OAUTH":
            return "OAUTH"

        return "NONE"

    def _extract_auth_header_name(self, ba_spec: Dict[str, Any]) -> str:
        """Extract authentication header name."""
        auth = ba_spec.get("authentication", {})
        return auth.get("header_name", "Authorization")

    def _extract_data_format(self, ba_spec: Dict[str, Any]) -> str:
        """Extract expected data format."""
        exec_summary = ba_spec.get("executive_summary", {})
        data_format = exec_summary.get("data_format", "json")
        return data_format.lower()

    def _extract_update_frequency(self, ba_spec: Dict[str, Any]) -> str:
        """Extract update frequency."""
        exec_summary = ba_spec.get("executive_summary", {})
        return exec_summary.get("update_frequency", "daily")

    def _extract_historical_support(self, ba_spec: Dict[str, Any]) -> bool:
        """Extract historical support flag."""
        exec_summary = ba_spec.get("executive_summary", {})
        return exec_summary.get("historical_support", True)

    def _determine_base_imports(self, ba_spec: Dict[str, Any]) -> List[str]:
        """Determine required imports based on spec."""
        imports = [
            "import os",
            "import sys",
            "import logging",
            "from datetime import datetime, timedelta, date, UTC",
            "from typing import List, Dict, Any",
            "",
            "import click",
            "import redis",
            "import requests",
        ]

        # Add auth-specific imports
        auth_method = self._extract_auth_method(ba_spec)
        if auth_method == "OAUTH":
            imports.append("from requests_oauthlib import OAuth2Session")

        # Add source-type specific imports
        source_type = ba_spec.get("source_type", "").upper()
        if source_type == "WEBSITE":
            imports.extend([
                "from bs4 import BeautifulSoup",
                "from selenium import webdriver",
            ])
        elif source_type == "FTP":
            imports.append("from ftplib import FTP")

        return imports

    def validate(self, transformed: Dict[str, Any]) -> List[str]:
        """Validate transformed context.

        Args:
            transformed: Transformed context dictionary

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        template_vars = transformed.get("template_vars", {})

        # Check required fields
        required_fields = ["source", "data_type", "class_name", "dgroup"]
        for field in required_fields:
            if not template_vars.get(field):
                errors.append(f"Missing required field: {field}")

        # Validate collection method
        collection_method = template_vars.get("collection_method")
        valid_methods = ["HTTP_REST_API", "FTP_SFTP", "WEBSITE_PARSER", "EMAIL_IMAP"]
        if collection_method not in valid_methods:
            errors.append(f"Invalid collection_method: {collection_method}")

        # Validate auth for API scrapers
        if collection_method == "HTTP_REST_API":
            if template_vars.get("auth_required") and not template_vars.get("auth_header_name"):
                errors.append("auth_header_name required when auth_required=True")

        # Validate endpoints for API scrapers
        if collection_method == "HTTP_REST_API":
            endpoints = template_vars.get("endpoints", [])
            if not endpoints:
                errors.append("At least one endpoint required for HTTP_REST_API scrapers")

        return errors
