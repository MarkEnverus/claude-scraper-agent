"""Pytest fixtures and mocks for testing."""

import pytest
from pathlib import Path
from typing import Type, Any
from pydantic import BaseModel, Field

from agentic_scraper.llm.factory import LLMFactory
from agentic_scraper.types import (
    Phase0Detection,
    Phase1Documentation,
    Phase2Tests,
    ValidatedSpec,
    ValidationResult,
    ValidationReport,
    DataSourceType,
    AuthenticationMethod,
    EndpointSpec,
    HTTPMethod,
    ResponseFormat,
    DocQuality,
    ValidationOverallStatus,
)

# Mock GeneratedCode for testing (matches hybrid_generator.py structure)
class GeneratedCode(BaseModel):
    """Generated code from LLM."""
    code: str = ""
    imports: list[str] = Field(default_factory=list)
    notes: str = ""


class MockLLMProvider:
    """Mock LLM provider for testing that returns realistic mock data."""

    def __init__(self):
        self.call_count = 0
        self.calls = []  # Track all calls for assertions
        self.last_prompt = None
        self.last_response_model = None

    async def invoke(self, prompt: str, system: str = "") -> str:
        """Mock invoke for text responses (e.g., executive summary)."""
        self.call_count += 1
        self.last_prompt = prompt
        self.calls.append(("invoke", prompt, system))

        # Return mock markdown for executive summary
        return """# Data Source Executive Summary

## Overview
Mock data source for testing.

## Endpoints
| Endpoint | Method | Auth |
|----------|--------|------|
| /api/v1/data | GET | API Key |
"""

    async def invoke_structured(
        self,
        prompt: str,
        response_model: Type[BaseModel],
        system: str = ""
    ) -> BaseModel:
        """Mock invoke_structured that returns appropriate mock data."""
        self.call_count += 1
        self.last_prompt = prompt
        self.last_response_model = response_model
        self.calls.append(("invoke_structured", prompt, response_model.__name__, system))

        # Return mock data based on response_model
        if response_model == Phase0Detection:
            return Phase0Detection(
                detected_type=DataSourceType.API,
                confidence=0.95,
                indicators=["REST API detected", "JSON responses", "OpenAPI documentation found"],
                discovered_api_calls=["https://api.example.com/v1/data", "https://api.example.com/v1/users"],
                discovered_endpoint_urls=[],
                auth_method="API_KEY",
                base_url="https://api.example.com",
                url="https://api.example.com"
            )

        elif response_model == Phase1Documentation:
            return Phase1Documentation(
                source="MockSource",
                timestamp="2024-01-15T00:00:00Z",
                url="https://api.example.com",
                endpoints=[
                    EndpointSpec(
                        endpoint_id="test_endpoint",
                        path="/api/v1/data",
                        method=HTTPMethod.GET,
                        description="Test endpoint",
                        parameters=[],
                        response_format=ResponseFormat.JSON,
                        authentication_mentioned=True
                    )
                ],
                doc_quality=DocQuality.HIGH,
                notes="Mock documentation"
            )

        elif response_model == Phase2Tests:
            return Phase2Tests(
                source="MockSource",
                timestamp="2024-01-15T00:00:00Z",
                endpoints_tested=[],
                test_summary="Mock test summary"
            )

        elif response_model == ValidationResult:
            return ValidationResult(
                confidence=0.9,
                identified_gaps=[],
                recommendations=[],
                validation_notes="Mock validation passed"
            )

        elif response_model == ValidationReport:
            return ValidationReport(
                validation_timestamp="2024-01-15T00:00:00Z",
                input_file="mock_file.json",
                overall_status=ValidationOverallStatus.PASS,
                overall_confidence=0.95,
                phase_validations={},
                critical_gaps=[],
                overall_recommendations=[],
                collation_notes="Mock validation report"
            )

        elif response_model == ValidatedSpec:
            return ValidatedSpec(
                source="MockSource",
                source_type=DataSourceType.API,
                executive_summary={
                    "data_type": "test_data",
                    "base_url": "https://api.example.com",
                    "data_format": "json",
                    "update_frequency": "daily",
                    "historical_support": True,
                    "collection_method": "HTTP_REST_API",
                },
                authentication={
                    "required": True,
                    "method": "API_KEY",
                    "header_name": "X-API-Key",
                    "notes": "API key required"
                },
                endpoints=[{
                    "endpoint_id": "test",
                    "name": "Test Endpoint",
                    "path": "/api/v1/data",
                    "method": "GET",
                    "description": "Test endpoint"
                }],
                validation_summary={
                    "confidence_score": 0.95,
                    "validation_date": "2024-01-15",
                    "notes": "Mock validation"
                }
            )

        elif response_model == GeneratedCode or response_model.__name__ == "GeneratedCode":
            # Mock generated code for scraper generation
            # Note: Templates use | dedent | indent(N), so code should have consistent leading indent
            # Check the prompt to determine what code to generate
            if "collect_content" in prompt.lower():
                return GeneratedCode(
                    code="""self.logger.info("Fetching data from endpoint")
headers = {"Authorization": f"Bearer {self.api_key}"}
response = requests.get(self.endpoint_url, headers=headers, timeout=30)
response.raise_for_status()
return response.content""",
                    imports=["requests"],
                    notes="Mock collect_content code"
                )
            elif "validate_content" in prompt.lower():
                return GeneratedCode(
                    code="""self.logger.info("Validating content")
if not content:
    raise ValueError("Empty content received")
data = json.loads(content)
if "data" not in data:
    raise ValueError("Missing required field: data")
self.logger.info("Validation passed")""",
                    imports=["json"],
                    notes="Mock validate_content code"
                )
            elif "auth" in prompt.lower() or "__init__" in prompt.lower():
                return GeneratedCode(
                    code="""self.api_key = os.getenv("API_KEY")
if not self.api_key:
    raise ValueError("API_KEY environment variable not set")""",
                    imports=["os"],
                    notes="Mock auth setup code"
                )
            else:
                return GeneratedCode(
                    code="# Mock generated code",
                    imports=[],
                    notes="Generic mock code"
                )

        # Add more response types as needed...

        else:
            raise ValueError(f"MockLLMProvider: Unsupported response_model {response_model}")


@pytest.fixture
def mock_llm_provider():
    """Fixture providing mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def mock_llm_factory(mock_llm_provider):
    """Fixture providing mock LLMFactory that wraps MockLLMProvider.

    This allows tests to use the new HybridGenerator(factory=...) signature
    while still using the existing MockLLMProvider implementation.
    """
    from unittest.mock import Mock
    from agentic_scraper.llm.factory import LLMFactory

    factory = Mock(spec=LLMFactory)

    # create_reasoning_model() returns the mock provider (has invoke_structured)
    factory.create_reasoning_model.return_value = mock_llm_provider

    # invoke_structured() delegates to mock provider
    async def mock_invoke_structured(llm, prompt, response_model, system=""):
        return await mock_llm_provider.invoke_structured(prompt, response_model, system)

    factory.invoke_structured = mock_invoke_structured

    return factory


@pytest.fixture
def ba_analyzer(mock_llm_provider, tmp_path):
    """Fixture providing BAAnalyzer with mock provider."""
    from agentic_scraper.agents.ba_analyzer import BAAnalyzer
    from agentic_scraper.storage.repository import AnalysisRepository

    repository = AnalysisRepository(tmp_path / "analysis")
    return BAAnalyzer(
        llm_provider=mock_llm_provider,
        repository=repository
    )


# Add more fixtures for other agents (validator, collator, etc.)
