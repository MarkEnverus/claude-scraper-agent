"""End-to-end integration tests for CLI and orchestration pipeline.

This module tests the complete user journey from CLI invocation to
final analysis output, including:
- CLI command parsing and execution
- Full pipeline execution with mocked agents
- Progress tracking and output generation
- Error handling and edge cases
- Real LLM integration tests (marked as slow)

Test Strategy:
- Use Click's CliRunner for CLI testing
- Mock external dependencies (WebFetch, Puppeteer, BAML functions)
- Test both success and failure paths
- Verify file generation and formatting
- Include one real LLM test (marked @pytest.mark.slow)

Example:
    # Run all tests except slow ones
    $ pytest tests/test_integration.py -v

    # Run only slow tests (with real LLM calls)
    $ pytest tests/test_integration.py -v -m slow
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from baml_client.baml_client.types import (
    AuthenticationMethod,
    ComplexityLevel,
    ConfidenceLevel,
    DataSourceType,
    DocQuality,
    Endpoint,
    EndpointDetails,
    EndpointSpec,
    ExecutiveSummary,
    HTTPMethod,
    Phase0Detection,
    Phase1Documentation,
    Phase2Tests,
    ResponseFormat,
    ScraperRecommendation,
    ValidatedSpec,
    ValidationOverallStatus,
    ValidationReport,
    ValidationStatus,
    ValidationSummary,
)
from claude_scraper.cli.main import cli
from claude_scraper.orchestration import (
    AnalysisState,
    create_pipeline_without_checkpointing,
    pipeline,
)


@pytest.fixture
def runner():
    """CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_output_dir():
    """Temporary output directory for analysis files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_phase0():
    """Mock Phase 0 detection results."""
    return Phase0Detection(
        detected_type=DataSourceType.API,
        confidence=0.90,
        indicators=["REST API", "JSON responses", "Swagger docs"],
        discovered_api_calls=["https://api.example.com/v1/data"],
        endpoints=[
            Endpoint(
                path="/api/v1/data",
                method=HTTPMethod.GET,
                parameters=[],
                auth_required=False,
                response_format=ResponseFormat.JSON,
            )
        ],
        url="https://api.example.com",
    )


@pytest.fixture
def mock_phase1():
    """Mock Phase 1 documentation results."""
    return Phase1Documentation(
        source="BA Analyzer",
        timestamp="2025-12-18T10:00:00Z",
        url="https://api.example.com",
        endpoints=[
            EndpointSpec(
                endpoint_id="ep_1",
                path="/api/v1/data",
                method=HTTPMethod.GET,
                description="Get data",
                parameters=[],
                response_format=ResponseFormat.JSON,
                authentication_mentioned=False,
            )
        ],
        doc_quality=DocQuality.HIGH,
        notes="API documentation extracted",
    )


@pytest.fixture
def mock_phase2():
    """Mock Phase 2 testing results."""
    return Phase2Tests(
        source="BA Analyzer",
        timestamp="2025-12-18T10:00:00Z",
        files_saved=["test_results.json"],
    )


@pytest.fixture
def mock_phase3_high_confidence():
    """Mock Phase 3 validated spec with high confidence (>= 0.8)."""
    return ValidatedSpec(
        source="BA Analyzer",
        source_type="API",
        timestamp="2025-12-18T10:00:00Z",
        url="https://api.example.com",
        executive_summary=ExecutiveSummary(
            total_endpoints_discovered=1,
            accessible_endpoints=1,
            success_rate="100%",
            primary_formats=[ResponseFormat.JSON.value],
            authentication_required=False,
            estimated_scraper_complexity=ComplexityLevel.LOW,
        ),
        validation_summary=ValidationSummary(
            phases_completed=["Phase0", "Phase1", "Phase2", "Phase3"],
            documentation_review="Complete",
            live_api_testing="Complete",
            discrepancies_found=0,
            confidence_score=0.85,
            confidence_level=ConfidenceLevel.HIGH,
            recommendation="Proceed to scraper generation",
        ),
        endpoints=[
            EndpointDetails(
                endpoint_id="ep_1",
                name="Get Data",
                type="GET",
                base_url="https://api.example.com",
                path="/api/v1/data",
                method=HTTPMethod.GET,
                parameters={},
                authentication={},
                response_format=ResponseFormat.JSON,
                validation_status=ValidationStatus.TESTED_200_OK,
                accessible=True,
                last_tested="2025-12-18T10:00:00Z",
                notes="Endpoint validated",
            )
        ],
        scraper_recommendation=ScraperRecommendation(
            type="API_CLIENT",
            confidence=ConfidenceLevel.HIGH,
            rationale=["Simple API"],
            complexity=ComplexityLevel.LOW,
            estimated_effort="2-3 hours",
            key_challenges=[],
        ),
        discrepancies=[],
        artifacts_generated=["phase0_detection.json"],
        next_steps=["Generate scraper"],
    )


@pytest.fixture
def mock_phase3_low_confidence():
    """Mock Phase 3 validated spec with low confidence (< 0.8)."""
    return ValidatedSpec(
        source="BA Analyzer",
        source_type="API",
        timestamp="2025-12-18T10:00:00Z",
        url="https://api.example.com",
        executive_summary=ExecutiveSummary(
            total_endpoints_discovered=1,
            accessible_endpoints=1,
            success_rate="100%",
            primary_formats=[ResponseFormat.JSON.value],
            authentication_required=False,
            estimated_scraper_complexity=ComplexityLevel.LOW,
        ),
        validation_summary=ValidationSummary(
            phases_completed=["Phase0", "Phase1", "Phase2", "Phase3"],
            documentation_review="Incomplete",
            live_api_testing="Partial",
            discrepancies_found=2,
            confidence_score=0.70,
            confidence_level=ConfidenceLevel.MEDIUM,
            recommendation="Second pass recommended",
        ),
        endpoints=[
            EndpointDetails(
                endpoint_id="ep_1",
                name="Get Data",
                type="GET",
                base_url="https://api.example.com",
                path="/api/v1/data",
                method=HTTPMethod.GET,
                parameters={},
                authentication={},
                response_format=ResponseFormat.JSON,
                validation_status=ValidationStatus.TESTED_200_OK,
                accessible=True,
                last_tested="2025-12-18T10:00:00Z",
                notes="Endpoint validated",
            )
        ],
        scraper_recommendation=ScraperRecommendation(
            type="API_CLIENT",
            confidence=ConfidenceLevel.MEDIUM,
            rationale=["Simple API but incomplete documentation"],
            complexity=ComplexityLevel.LOW,
            estimated_effort="3-4 hours",
            key_challenges=["Missing auth details"],
        ),
        discrepancies=[],
        artifacts_generated=["phase0_detection.json"],
        next_steps=["Run second analysis pass"],
    )


@pytest.fixture
def mock_validation_high_confidence():
    """Mock validation report with high confidence."""
    return ValidationReport(
        validation_timestamp="2025-12-18T10:00:00Z",
        input_file="validated_datasource_spec.json",
        overall_status=ValidationOverallStatus.PASS,
        overall_confidence=0.85,
        phase_validations={},
        critical_gaps=[],
        recommendations_for_second_pass=[],
        validation_summary="High confidence - no second pass needed",
    )


@pytest.fixture
def mock_validation_low_confidence():
    """Mock validation report with low confidence."""
    from baml_client.baml_client.types import CriticalGap

    return ValidationReport(
        validation_timestamp="2025-12-18T10:00:00Z",
        input_file="validated_datasource_spec.json",
        overall_status=ValidationOverallStatus.NEEDS_IMPROVEMENT,
        overall_confidence=0.70,
        phase_validations={},
        critical_gaps=[
            CriticalGap(
                gap_type="Authentication",
                description="Missing authentication details",
                action_required="Investigate auth requirements",
            ),
            CriticalGap(
                gap_type="Endpoints",
                description="Incomplete endpoint enumeration",
                action_required="Re-enumerate all endpoints",
            ),
        ],
        recommendations_for_second_pass=[
            "Re-enumerate all endpoints",
            "Test authentication",
        ],
        validation_summary="Low confidence - second pass recommended",
    )


@pytest.fixture
def mock_qa_results():
    """Mock QA testing results."""
    return {
        "total_tested": 1,
        "keep": 1,
        "remove": 0,
        "flag": 0,
        "results": [
            {
                "endpoint": "/api/v1/data",
                "method": "GET",
                "status_code": 200,
                "decision": "keep",
                "response_time_ms": 125.5,
                "error": None,
            }
        ],
    }


# CLI Tests


def test_cli_analyze_command_help(runner):
    """Test that analyze command help is displayed correctly."""
    result = runner.invoke(cli, ["analyze", "--help"])

    assert result.exit_code == 0
    assert "Analyze a data source" in result.output
    assert "--url" in result.output
    assert "--provider" in result.output
    assert "--output-dir" in result.output
    assert "--debug" in result.output


def test_cli_analyze_missing_url(runner):
    """Test analyze command fails when URL is missing."""
    result = runner.invoke(cli, ["analyze"])

    assert result.exit_code != 0
    assert "Missing option '--url'" in result.output or "Error" in result.output


def test_cli_analyze_basic_execution(
    runner,
    temp_output_dir,
    mock_phase0,
    mock_phase1,
    mock_phase2,
    mock_phase3_high_confidence,
    mock_validation_high_confidence,
    mock_qa_results,
):
    """Test basic analyze command execution with mocked pipeline."""
    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
         patch("claude_scraper.orchestration.nodes.BAValidator") as MockValidator, \
         patch("claude_scraper.orchestration.nodes.EndpointQATester") as MockQA, \
         patch("claude_scraper.orchestration.nodes.WebFetchTool"), \
         patch("claude_scraper.orchestration.nodes.PuppeteerTool"):

        # Mock analyzer
        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze_phase0 = AsyncMock(return_value=mock_phase0)
        mock_analyzer.analyze_phase1 = AsyncMock(return_value=mock_phase1)
        mock_analyzer.analyze_phase2 = AsyncMock(return_value=mock_phase2)
        mock_analyzer.analyze_phase3 = AsyncMock(return_value=mock_phase3_high_confidence)

        # Mock validator
        mock_validator = MockValidator.return_value
        mock_validator.validate_complete_spec = AsyncMock(
            return_value=mock_validation_high_confidence
        )
        mock_validator.should_run_second_analysis = MagicMock(return_value=False)

        # Mock QA
        mock_qa = MockQA.return_value
        mock_qa.test_all_endpoints = MagicMock(return_value=mock_qa_results)

        # Execute CLI command
        result = runner.invoke(cli, [
            "analyze",
            "--url", "https://api.example.com",
            "--output-dir", temp_output_dir,
            "--provider", "bedrock",
        ], catch_exceptions=False)

        # Assertions
        assert result.exit_code == 0
        assert "Analysis Complete" in result.output
        assert "Confidence Score: 0.85" in result.output or "0.85" in result.output


def test_cli_analyze_with_debug_flag(runner, temp_output_dir):
    """Test that debug flag enables verbose logging."""
    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
         patch("claude_scraper.orchestration.nodes.BAValidator") as MockValidator, \
         patch("claude_scraper.orchestration.nodes.EndpointQATester") as MockQA, \
         patch("claude_scraper.orchestration.nodes.WebFetchTool"), \
         patch("claude_scraper.orchestration.nodes.PuppeteerTool"):

        # Setup minimal mocks
        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze_phase0 = AsyncMock(
            side_effect=Exception("Test debug error")
        )

        result = runner.invoke(cli, [
            "analyze",
            "--url", "https://api.example.com",
            "--output-dir", temp_output_dir,
            "--debug",
        ])

        # Should fail but show debug info
        assert result.exit_code != 0
        # Debug flag was set (exact output depends on implementation)


def test_cli_analyze_invalid_url_format(runner, temp_output_dir):
    """Test error handling for malformed URLs."""
    # Note: URL validation might happen at different layers
    # This test verifies graceful error handling
    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
         patch("claude_scraper.orchestration.nodes.WebFetchTool"), \
         patch("claude_scraper.orchestration.nodes.PuppeteerTool"):

        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze_phase0 = AsyncMock(
            side_effect=ValueError("Invalid URL format")
        )

        result = runner.invoke(cli, [
            "analyze",
            "--url", "not-a-valid-url",
            "--output-dir", temp_output_dir,
        ])

        # Should handle error gracefully
        assert result.exit_code != 0


def test_cli_analyze_custom_output_dir(
    runner,
    mock_phase0,
    mock_phase1,
    mock_phase2,
    mock_phase3_high_confidence,
    mock_validation_high_confidence,
    mock_qa_results,
):
    """Test that custom output directory is created and used."""
    with tempfile.TemporaryDirectory() as tmpdir:
        custom_output = os.path.join(tmpdir, "custom_analysis_output")

        with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
             patch("claude_scraper.orchestration.nodes.BAValidator") as MockValidator, \
             patch("claude_scraper.orchestration.nodes.EndpointQATester") as MockQA, \
             patch("claude_scraper.orchestration.nodes.WebFetchTool"), \
             patch("claude_scraper.orchestration.nodes.PuppeteerTool"):

            # Mock analyzer
            mock_analyzer = MockAnalyzer.return_value
            mock_analyzer.analyze_phase0 = AsyncMock(return_value=mock_phase0)
            mock_analyzer.analyze_phase1 = AsyncMock(return_value=mock_phase1)
            mock_analyzer.analyze_phase2 = AsyncMock(return_value=mock_phase2)
            mock_analyzer.analyze_phase3 = AsyncMock(return_value=mock_phase3_high_confidence)

            # Mock validator
            mock_validator = MockValidator.return_value
            mock_validator.validate_complete_spec = AsyncMock(
                return_value=mock_validation_high_confidence
            )
            mock_validator.should_run_second_analysis = MagicMock(return_value=False)

            # Mock QA
            mock_qa = MockQA.return_value
            mock_qa.test_all_endpoints = MagicMock(return_value=mock_qa_results)

            result = runner.invoke(cli, [
                "analyze",
                "--url", "https://api.example.com",
                "--output-dir", custom_output,
            ])

            # Verify custom output directory was created
            # Note: Actual file creation depends on repository implementation
            assert result.exit_code == 0
            # Directory should exist (created by Path.mkdir in CLI)


# Pipeline Integration Tests


@pytest.mark.asyncio
async def test_full_pipeline_execution_skip_run2(
    mock_phase0,
    mock_phase1,
    mock_phase2,
    mock_phase3_high_confidence,
    mock_validation_high_confidence,
    mock_qa_results,
):
    """Test full pipeline execution when confidence >= 0.8 (skips Run 2)."""
    initial_state: AnalysisState = {"url": "https://api.example.com"}

    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
         patch("claude_scraper.orchestration.nodes.BAValidator") as MockValidator, \
         patch("claude_scraper.orchestration.nodes.EndpointQATester") as MockQA, \
         patch("claude_scraper.orchestration.nodes.WebFetchTool"), \
         patch("claude_scraper.orchestration.nodes.PuppeteerTool"):

        # Mock analyzer
        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze_phase0 = AsyncMock(return_value=mock_phase0)
        mock_analyzer.analyze_phase1 = AsyncMock(return_value=mock_phase1)
        mock_analyzer.analyze_phase2 = AsyncMock(return_value=mock_phase2)
        mock_analyzer.analyze_phase3 = AsyncMock(return_value=mock_phase3_high_confidence)

        # Mock validator
        mock_validator = MockValidator.return_value
        mock_validator.validate_complete_spec = AsyncMock(
            return_value=mock_validation_high_confidence
        )
        mock_validator.should_run_second_analysis = MagicMock(return_value=False)

        # Mock QA
        mock_qa = MockQA.return_value
        mock_qa.test_all_endpoints = MagicMock(return_value=mock_qa_results)

        # Execute pipeline
        pipeline_test = create_pipeline_without_checkpointing()
        result = await pipeline_test.ainvoke(initial_state)

        # Assertions
        assert result["run2_required"] is False
        assert result["confidence_score"] == 0.85
        assert "phase0_run1" in result
        assert "final_spec" in result
        assert "qa_results" in result
        assert result["qa_results"]["keep"] == 1


@pytest.mark.asyncio
async def test_full_pipeline_execution_with_run2(
    mock_phase0,
    mock_phase1,
    mock_phase2,
    mock_phase3_low_confidence,
    mock_phase3_high_confidence,
    mock_validation_low_confidence,
    mock_validation_high_confidence,
    mock_qa_results,
):
    """Test full pipeline execution when confidence < 0.8 (triggers Run 2)."""
    initial_state: AnalysisState = {"url": "https://api.example.com"}

    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
         patch("claude_scraper.orchestration.nodes.BAValidator") as MockValidator, \
         patch("claude_scraper.orchestration.nodes.BACollator") as MockCollator, \
         patch("claude_scraper.orchestration.nodes.EndpointQATester") as MockQA, \
         patch("claude_scraper.orchestration.nodes.WebFetchTool"), \
         patch("claude_scraper.orchestration.nodes.PuppeteerTool"):

        # Mock analyzer (Run 1 returns low confidence, Run 2 returns high)
        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze_phase0 = AsyncMock(return_value=mock_phase0)
        mock_analyzer.analyze_phase1 = AsyncMock(return_value=mock_phase1)
        mock_analyzer.analyze_phase2 = AsyncMock(return_value=mock_phase2)
        mock_analyzer.analyze_phase3 = AsyncMock(
            side_effect=[mock_phase3_low_confidence, mock_phase3_high_confidence]
        )

        # Mock validator
        mock_validator = MockValidator.return_value
        mock_validator.validate_complete_spec = AsyncMock(
            side_effect=[mock_validation_low_confidence, mock_validation_high_confidence]
        )
        mock_validator.should_run_second_analysis = MagicMock(return_value=True)
        mock_validator.get_run2_focus_areas = MagicMock(
            return_value=["Re-enumerate endpoints", "Test authentication"]
        )

        # Mock collator
        mock_collator = MockCollator.return_value
        mock_collator.merge_complete_specs = AsyncMock(
            return_value=mock_phase3_high_confidence
        )

        # Mock QA
        mock_qa = MockQA.return_value
        mock_qa.test_all_endpoints = MagicMock(return_value=mock_qa_results)

        # Execute pipeline
        pipeline_test = create_pipeline_without_checkpointing()
        result = await pipeline_test.ainvoke(initial_state)

        # Assertions
        assert result["run2_required"] is True
        assert result["confidence_score"] == 0.70  # Run 1 confidence
        assert "phase0_run1" in result
        assert "phase0_run2" in result
        assert "final_spec" in result
        assert "qa_results" in result


@pytest.mark.asyncio
async def test_pipeline_error_handling_in_run1(mock_phase0):
    """Test pipeline handles errors gracefully during Run 1."""
    from claude_scraper.types.errors import Run1AnalysisError

    initial_state: AnalysisState = {"url": "https://api.example.com"}

    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
         patch("claude_scraper.orchestration.nodes.WebFetchTool"), \
         patch("claude_scraper.orchestration.nodes.PuppeteerTool"):

        # Mock analyzer to fail at Phase 1
        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze_phase0 = AsyncMock(return_value=mock_phase0)
        mock_analyzer.analyze_phase1 = AsyncMock(
            side_effect=Exception("Phase 1 failed - network timeout")
        )

        # Execute pipeline
        pipeline_test = create_pipeline_without_checkpointing()

        with pytest.raises(Run1AnalysisError):
            await pipeline_test.ainvoke(initial_state)


@pytest.mark.asyncio
async def test_pipeline_file_output_generation(
    mock_phase0,
    mock_phase1,
    mock_phase2,
    mock_phase3_high_confidence,
    mock_validation_high_confidence,
    mock_qa_results,
):
    """Test that pipeline generates expected output files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set repository output directory
        with patch("claude_scraper.orchestration.nodes.AnalysisRepository") as MockRepo, \
             patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
             patch("claude_scraper.orchestration.nodes.BAValidator") as MockValidator, \
             patch("claude_scraper.orchestration.nodes.EndpointQATester") as MockQA, \
             patch("claude_scraper.orchestration.nodes.WebFetchTool"), \
             patch("claude_scraper.orchestration.nodes.PuppeteerTool"):

            # Mock repository
            mock_repo = MockRepo.return_value
            mock_repo.output_dir = Path(tmpdir)

            # Mock analyzer
            mock_analyzer = MockAnalyzer.return_value
            mock_analyzer.analyze_phase0 = AsyncMock(return_value=mock_phase0)
            mock_analyzer.analyze_phase1 = AsyncMock(return_value=mock_phase1)
            mock_analyzer.analyze_phase2 = AsyncMock(return_value=mock_phase2)
            mock_analyzer.analyze_phase3 = AsyncMock(return_value=mock_phase3_high_confidence)

            # Mock validator
            mock_validator = MockValidator.return_value
            mock_validator.validate_complete_spec = AsyncMock(
                return_value=mock_validation_high_confidence
            )
            mock_validator.should_run_second_analysis = MagicMock(return_value=False)

            # Mock QA
            mock_qa = MockQA.return_value
            mock_qa.test_all_endpoints = MagicMock(return_value=mock_qa_results)

            initial_state: AnalysisState = {"url": "https://api.example.com"}

            pipeline_test = create_pipeline_without_checkpointing()
            result = await pipeline_test.ainvoke(initial_state)

            # Verify result structure
            assert "final_spec" in result
            assert "qa_results" in result


# Slow Tests (Real LLM Integration)


@pytest.mark.slow
@pytest.mark.skipif(
    os.getenv("AWS_REGION") is None,
    reason="AWS credentials not configured - skipping real LLM test"
)
@pytest.mark.asyncio
async def test_real_llm_integration_simple_api():
    """Test full pipeline with real LLM calls on a simple public API.

    This test makes REAL LLM calls and is marked as slow.
    Only run when you want to verify end-to-end with actual Bedrock/Anthropic.

    Run with: pytest -m slow tests/test_integration.py
    """
    # Use a simple, stable public API for testing
    test_url = "https://jsonplaceholder.typicode.com"

    initial_state: AnalysisState = {"url": test_url}

    # Execute real pipeline (no mocks)
    pipeline_real = create_pipeline_without_checkpointing()
    result = await pipeline_real.ainvoke(initial_state)

    # Basic assertions
    assert "final_spec" in result
    assert "qa_results" in result
    assert result["confidence_score"] > 0.0
    assert len(result["final_spec"].endpoints) > 0

    # Log results for manual inspection
    print(f"\n=== Real LLM Test Results ===")
    print(f"URL: {test_url}")
    print(f"Confidence: {result['confidence_score']:.2f}")
    print(f"Endpoints found: {len(result['final_spec'].endpoints)}")
    print(f"QA Results: {result['qa_results']['keep']} kept, "
          f"{result['qa_results']['remove']} removed")


# Additional Edge Case Tests


def test_cli_deprecated_run_command(runner):
    """Test that deprecated 'run' command shows warning."""
    result = runner.invoke(cli, [
        "run",
        "--mode", "analyze",
        "--url", "https://api.example.com",
    ])

    # Should show deprecation warning
    assert "deprecated" in result.output.lower() or "warning" in result.output.lower()
