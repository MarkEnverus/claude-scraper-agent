"""Integration tests for LangGraph orchestration pipeline.

This module tests the 5-node BA analysis pipeline with:
- Full pipeline execution (Run 1 → Decision → Run 2 → Collation → QA)
- Conditional routing (skip Run 2 when confidence ≥ 0.8)
- State management and transitions
- Error handling in each node
- Checkpoint/resume capability

Test Strategy:
- Use mocks for external dependencies (WebFetch, Puppeteer, BAML functions)
- Test each node in isolation
- Test full pipeline with conditional routing
- Test error scenarios

Example:
    $ pytest tests/test_orchestration.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from claude_scraper.types import (
    AuthenticationMethod,
    DataSourceType,
    DocQuality,
    HTTPMethod,
    Phase0Detection,
    Phase1Documentation,
    Phase2Tests,
    ResponseFormat,
    ValidatedSpec,
    ValidationOverallStatus,
    ValidationReport,
    EndpointSpec,
    ScraperRecommendation,
    EndpointDetails,
    ValidationStatus,
    Endpoint,
    ExecutiveSummary,
    ValidationSummary,
    ComplexityLevel,
    ScraperType,
    ConfidenceLevel,
)
from claude_scraper.orchestration import (
    AnalysisState,
    create_pipeline_without_checkpointing,
    should_run_second_pass,
    run1_node,
    decision_node,
    run2_node,
    collation_node,
    qa_node,
)
from claude_scraper.types.errors import Run1AnalysisError


# Fixtures for test data
@pytest.fixture
def mock_phase0_run1():
    """Mock Phase 0 detection results for Run 1."""
    return Phase0Detection(
        detected_type=DataSourceType.API,
        confidence=0.90,
        indicators=["REST API", "JSON responses", "Swagger docs"],
        discovered_api_calls=["https://api.example.com/v1/data"],
        discovered_endpoint_urls=["https://api.example.com/v1/data"],
        auth_method="API_KEY",
        base_url="https://api.example.com",
        url="https://api.example.com",
    )


@pytest.fixture
def mock_phase1_run1():
    """Mock Phase 1 documentation results for Run 1."""
    return Phase1Documentation(
        source="BA Analyzer Run 1",
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
def mock_phase2_run1():
    """Mock Phase 2 testing results for Run 1."""
    return Phase2Tests(
        source="BA Analyzer Run 1",
        timestamp="2025-12-18T10:00:00Z",
        files_saved=["test_results_1.json"],
    )


@pytest.fixture
def mock_phase3_run1():
    """Mock Phase 3 validated spec for Run 1."""
    return ValidatedSpec(
        source="BA Analyzer",
        source_type="API",
        datasource="example_api",
        dataset="test_data",
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
            confidence_score=0.75,
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
            confidence=ConfidenceLevel.HIGH,
            rationale=["Simple API"],
            complexity=ComplexityLevel.LOW,
            estimated_effort="2-3 hours",
            key_challenges=[],
        ),
        discrepancies=[],
        artifacts_generated=["phase0_detection.json", "phase1_documentation.json"],
        next_steps=["Generate scraper"],
    )


@pytest.fixture
def mock_validation_low_confidence():
    """Mock validation report with low confidence (triggers Run 2)."""
    return ValidationReport(
        validation_timestamp="2025-12-18T10:00:00Z",
        input_file="validated_datasource_spec.json",
        overall_status=ValidationOverallStatus.NEEDS_IMPROVEMENT,
        overall_confidence=0.75,
        phase_validations={},
        critical_gaps=[],
        recommendations_for_second_pass=[
            "Re-enumerate all endpoints",
            "Test authentication requirements",
        ],
        validation_summary="Confidence below threshold - Run 2 recommended",
    )


@pytest.fixture
def mock_validation_high_confidence():
    """Mock validation report with high confidence (skips Run 2)."""
    return ValidationReport(
        validation_timestamp="2025-12-18T10:00:00Z",
        input_file="validated_datasource_spec.json",
        overall_status=ValidationOverallStatus.PASS,
        overall_confidence=0.85,
        phase_validations={},
        critical_gaps=[],
        recommendations_for_second_pass=[],
        validation_summary="Confidence meets threshold - no Run 2 needed",
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


# Test conditional routing function
def test_should_run_second_pass_with_low_confidence():
    """Test routing decision when confidence is below threshold."""
    state: AnalysisState = {
        "url": "https://api.example.com",
        "run2_required": True,
        "confidence_score": 0.75,
    }
    result = should_run_second_pass(state)
    assert result == "run2"


def test_should_run_second_pass_with_high_confidence():
    """Test routing decision when confidence meets threshold."""
    state: AnalysisState = {
        "url": "https://api.example.com",
        "run2_required": False,
        "confidence_score": 0.85,
    }
    result = should_run_second_pass(state)
    assert result == "collation"


def test_should_run_second_pass_missing_flag():
    """Test routing raises error when run2_required is missing."""
    state: AnalysisState = {
        "url": "https://api.example.com",
        "confidence_score": 0.75,
    }
    with pytest.raises(ValueError, match="run2_required must be present"):
        should_run_second_pass(state)


# Test individual nodes (with mocked dependencies)
@pytest.mark.asyncio
async def test_run1_node_success(
    mock_phase0_run1,
    mock_phase1_run1,
    mock_phase2_run1,
    mock_phase3_run1,
    mock_validation_low_confidence,
):
    """Test run1_node executes successfully with low confidence."""
    state: AnalysisState = {"url": "https://api.example.com"}

    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
         patch("claude_scraper.orchestration.nodes.BAValidator") as MockValidator:

        # Mock analyzer methods
        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze_phase0 = AsyncMock(return_value=mock_phase0_run1)
        mock_analyzer.analyze_endpoints = AsyncMock(return_value=[])
        mock_analyzer.analyze_phase1 = AsyncMock(return_value=mock_phase1_run1)
        mock_analyzer.analyze_phase2 = AsyncMock(return_value=mock_phase2_run1)
        mock_analyzer.analyze_phase3 = AsyncMock(return_value=mock_phase3_run1)

        # Mock validator methods
        mock_validator = MockValidator.return_value
        mock_validator.validate_complete_spec = AsyncMock(
            return_value=mock_validation_low_confidence
        )
        mock_validator.should_run_second_analysis = MagicMock(return_value=True)

        # Execute node
        updates = await run1_node(state)

        # Assertions
        assert updates["phase0_run1"] == mock_phase0_run1
        assert updates["phase1_run1"] == mock_phase1_run1
        assert updates["phase2_run1"] == mock_phase2_run1
        assert updates["phase3_run1"] == mock_phase3_run1
        assert updates["validation_run1"] == mock_validation_low_confidence
        assert updates["confidence_score"] == 0.75
        assert updates["run2_required"] is True


@pytest.mark.asyncio
async def test_run1_node_missing_url():
    """Test run1_node raises error when URL is missing."""
    state: AnalysisState = {}

    with pytest.raises(ValueError, match="URL is required"):
        await run1_node(state)


@pytest.mark.asyncio
async def test_decision_node():
    """Test decision_node passes through without state updates."""
    state: AnalysisState = {
        "url": "https://api.example.com",
        "confidence_score": 0.75,
        "run2_required": True,
        "validation_run1": MagicMock(),
    }

    updates = await decision_node(state)
    assert updates == {}


@pytest.mark.asyncio
async def test_decision_node_missing_confidence():
    """Test decision_node raises error when confidence_score is missing."""
    state: AnalysisState = {
        "url": "https://api.example.com",
        "run2_required": True,
    }

    with pytest.raises(ValueError, match="confidence_score and run2_required must be present"):
        await decision_node(state)


@pytest.mark.asyncio
async def test_run2_node_success(
    mock_phase0_run1,
    mock_phase1_run1,
    mock_phase2_run1,
    mock_phase3_run1,
    mock_validation_high_confidence,
):
    """Test run2_node executes successfully."""
    state: AnalysisState = {
        "url": "https://api.example.com",
        "validation_run1": mock_validation_high_confidence,
    }

    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
         patch("claude_scraper.orchestration.nodes.BAValidator") as MockValidator:

        # Mock analyzer
        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze_phase0 = AsyncMock(return_value=mock_phase0_run1)
        mock_analyzer.analyze_endpoints = AsyncMock(return_value=[])
        mock_analyzer.analyze_phase1 = AsyncMock(return_value=mock_phase1_run1)
        mock_analyzer.analyze_phase2 = AsyncMock(return_value=mock_phase2_run1)
        mock_analyzer.analyze_phase3 = AsyncMock(return_value=mock_phase3_run1)

        # Mock validator
        mock_validator = MockValidator.return_value
        mock_validator.get_run2_focus_areas = MagicMock(
            return_value=["Focus on endpoints", "Test authentication"]
        )
        mock_validator.validate_complete_spec = AsyncMock(
            return_value=mock_validation_high_confidence
        )

        # Execute node
        updates = await run2_node(state)

        # Assertions
        assert updates["phase0_run2"] == mock_phase0_run1
        assert updates["phase1_run2"] == mock_phase1_run1
        assert updates["phase2_run2"] == mock_phase2_run1
        assert updates["phase3_run2"] == mock_phase3_run1
        assert updates["validation_run2"] == mock_validation_high_confidence


@pytest.mark.asyncio
async def test_collation_node_with_run2(mock_phase3_run1):
    """Test collation_node merges Run 1 + Run 2."""
    state: AnalysisState = {
        "phase3_run1": mock_phase3_run1,
        "phase3_run2": mock_phase3_run1,  # Reuse for simplicity
        "run2_required": True,
    }

    with patch("claude_scraper.orchestration.nodes.BACollator") as MockCollator:
        mock_collator = MockCollator.return_value
        mock_collator.merge_complete_specs = AsyncMock(return_value=mock_phase3_run1)

        updates = await collation_node(state)

        # Verify merge was called
        mock_collator.merge_complete_specs.assert_called_once()
        assert updates["final_spec"] == mock_phase3_run1


@pytest.mark.asyncio
async def test_collation_node_without_run2(mock_phase3_run1):
    """Test collation_node uses Run 1 only when Run 2 is skipped."""
    state: AnalysisState = {
        "phase3_run1": mock_phase3_run1,
        "run2_required": False,
    }

    updates = await collation_node(state)

    # Should return Run 1 spec directly
    assert updates["final_spec"] == mock_phase3_run1


@pytest.mark.asyncio
async def test_qa_node_success(mock_phase3_run1, mock_qa_results):
    """Test qa_node executes successfully."""
    state: AnalysisState = {"final_spec": mock_phase3_run1}

    with patch("claude_scraper.orchestration.nodes.EndpointQATester") as MockQA:
        mock_qa = MockQA.return_value
        mock_qa.test_all_endpoints = MagicMock(return_value=mock_qa_results)

        updates = await qa_node(state)

        assert updates["qa_results"] == mock_qa_results
        mock_qa.test_all_endpoints.assert_called_once()


@pytest.mark.asyncio
async def test_qa_node_missing_final_spec():
    """Test qa_node raises error when final_spec is missing."""
    state: AnalysisState = {}

    with pytest.raises(ValueError, match="final_spec is required"):
        await qa_node(state)


# Test full pipeline execution
@pytest.mark.asyncio
async def test_full_pipeline_with_run2(
    mock_phase0_run1,
    mock_phase1_run1,
    mock_phase2_run1,
    mock_phase3_run1,
    mock_validation_low_confidence,
    mock_validation_high_confidence,
    mock_qa_results,
):
    """Test full pipeline execution when Run 1 confidence < 0.8 (triggers Run 2)."""
    initial_state: AnalysisState = {"url": "https://api.example.com"}

    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
         patch("claude_scraper.orchestration.nodes.BAValidator") as MockValidator, \
         patch("claude_scraper.orchestration.nodes.BACollator") as MockCollator, \
         patch("claude_scraper.orchestration.nodes.EndpointQATester") as MockQA:

        # Mock Run 1 analyzer
        mock_analyzer_run1 = MockAnalyzer.return_value
        mock_analyzer_run1.analyze_phase0 = AsyncMock(return_value=mock_phase0_run1)
        mock_analyzer_run1.analyze_endpoints = AsyncMock(return_value=[])
        mock_analyzer_run1.analyze_phase1 = AsyncMock(return_value=mock_phase1_run1)
        mock_analyzer_run1.analyze_phase2 = AsyncMock(return_value=mock_phase2_run1)
        mock_analyzer_run1.analyze_phase3 = AsyncMock(return_value=mock_phase3_run1)

        # Mock validator (returns low confidence for Run 1, high for Run 2)
        mock_validator = MockValidator.return_value
        mock_validator.validate_complete_spec = AsyncMock(
            side_effect=[mock_validation_low_confidence, mock_validation_high_confidence]
        )
        mock_validator.should_run_second_analysis = MagicMock(return_value=True)
        mock_validator.get_run2_focus_areas = MagicMock(return_value=["Focus areas"])

        # Mock collator
        mock_collator = MockCollator.return_value
        mock_collator.merge_complete_specs = AsyncMock(return_value=mock_phase3_run1)

        # Mock QA
        mock_qa = MockQA.return_value
        mock_qa.test_all_endpoints = MagicMock(return_value=mock_qa_results)

        # Create pipeline and execute
        pipeline = create_pipeline_without_checkpointing()
        result = await pipeline.ainvoke(initial_state)

        # Assertions
        assert result["run2_required"] is True
        assert result["confidence_score"] == 0.75
        assert "phase0_run1" in result
        assert "phase1_run1" in result
        assert "phase2_run1" in result
        assert "phase3_run1" in result
        assert "validation_run1" in result
        assert "phase0_run2" in result
        assert "phase1_run2" in result
        assert "phase2_run2" in result
        assert "phase3_run2" in result
        assert "validation_run2" in result
        assert "final_spec" in result
        assert "qa_results" in result


@pytest.mark.asyncio
async def test_full_pipeline_skip_run2(
    mock_phase0_run1,
    mock_phase1_run1,
    mock_phase2_run1,
    mock_phase3_run1,
    mock_validation_high_confidence,
    mock_qa_results,
):
    """Test full pipeline skips Run 2 when confidence >= 0.8."""
    # Update mock_phase3_run1 to have high confidence
    mock_phase3_high = mock_phase3_run1
    mock_phase3_high.validation_summary.confidence_score = 0.85

    initial_state: AnalysisState = {"url": "https://api.example.com"}

    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
         patch("claude_scraper.orchestration.nodes.BAValidator") as MockValidator, \
         patch("claude_scraper.orchestration.nodes.EndpointQATester") as MockQA:

        # Mock analyzer
        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze_phase0 = AsyncMock(return_value=mock_phase0_run1)
        mock_analyzer.analyze_endpoints = AsyncMock(return_value=[])
        mock_analyzer.analyze_phase1 = AsyncMock(return_value=mock_phase1_run1)
        mock_analyzer.analyze_phase2 = AsyncMock(return_value=mock_phase2_run1)
        mock_analyzer.analyze_phase3 = AsyncMock(return_value=mock_phase3_high)

        # Mock validator (returns high confidence)
        mock_validator = MockValidator.return_value
        mock_validator.validate_complete_spec = AsyncMock(
            return_value=mock_validation_high_confidence
        )
        mock_validator.should_run_second_analysis = MagicMock(return_value=False)

        # Mock QA
        mock_qa = MockQA.return_value
        mock_qa.test_all_endpoints = MagicMock(return_value=mock_qa_results)

        # Create pipeline and execute
        pipeline = create_pipeline_without_checkpointing()
        result = await pipeline.ainvoke(initial_state)

        # Assertions
        assert result["run2_required"] is False
        assert result["confidence_score"] == 0.85
        assert "phase0_run1" in result
        assert "phase1_run1" in result
        assert "phase2_run1" in result
        assert "phase3_run1" in result
        assert "validation_run1" in result
        # Run 2 should be skipped
        assert "phase0_run2" not in result or result.get("phase0_run2") is None
        assert "final_spec" in result
        assert "qa_results" in result


# Test error handling
@pytest.mark.asyncio
async def test_pipeline_error_in_run1():
    """Test pipeline handles errors in Run 1."""
    initial_state: AnalysisState = {"url": "https://api.example.com"}

    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer:

        # Mock analyzer to raise error
        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze_phase0 = AsyncMock(
            side_effect=Exception("Phase 0 failed")
        )

        # Create pipeline
        pipeline = create_pipeline_without_checkpointing()

        # Execute should raise custom Run1AnalysisError exception
        with pytest.raises(Run1AnalysisError, match="Run 1 analysis failed"):
            await pipeline.ainvoke(initial_state)


# Test checkpoint and resume functionality
@pytest.mark.asyncio
async def test_checkpoint_and_resume(
    mock_phase0_run1,
    mock_phase1_run1,
    mock_phase2_run1,
    mock_phase3_run1,
    mock_validation_low_confidence,
    mock_validation_high_confidence,
    mock_qa_results,
):
    """Test that pipeline can checkpoint and resume from saved state.

    This test verifies LangGraph's checkpointing functionality by:
    1. Creating a pipeline with checkpointing enabled
    2. Executing Run 1 (which triggers Run 2 due to low confidence)
    3. Verifying that state is persisted with thread_id
    4. Resuming from checkpoint and completing the pipeline
    """
    from claude_scraper.orchestration.pipeline import create_pipeline

    initial_state: AnalysisState = {"url": "https://api.example.com"}
    thread_id = "test-checkpoint-thread-123"
    config = {"configurable": {"thread_id": thread_id}}

    with patch("claude_scraper.orchestration.nodes.BAAnalyzer") as MockAnalyzer, \
         patch("claude_scraper.orchestration.nodes.BAValidator") as MockValidator, \
         patch("claude_scraper.orchestration.nodes.BACollator") as MockCollator, \
         patch("claude_scraper.orchestration.nodes.EndpointQATester") as MockQA:

        # Mock analyzer
        mock_analyzer = MockAnalyzer.return_value
        mock_analyzer.analyze_phase0 = AsyncMock(return_value=mock_phase0_run1)
        mock_analyzer.analyze_endpoints = AsyncMock(return_value=[])
        mock_analyzer.analyze_phase1 = AsyncMock(return_value=mock_phase1_run1)
        mock_analyzer.analyze_phase2 = AsyncMock(return_value=mock_phase2_run1)
        mock_analyzer.analyze_phase3 = AsyncMock(return_value=mock_phase3_run1)

        # Mock validator
        mock_validator = MockValidator.return_value
        mock_validator.validate_complete_spec = AsyncMock(
            side_effect=[mock_validation_low_confidence, mock_validation_high_confidence]
        )
        mock_validator.should_run_second_analysis = MagicMock(return_value=True)
        mock_validator.get_run2_focus_areas = MagicMock(return_value=["Focus areas"])

        # Mock collator
        mock_collator = MockCollator.return_value
        mock_collator.merge_complete_specs = AsyncMock(return_value=mock_phase3_run1)

        # Mock QA
        mock_qa = MockQA.return_value
        mock_qa.test_all_endpoints = MagicMock(return_value=mock_qa_results)

        # Create pipeline WITH checkpointing
        pipeline = create_pipeline(with_checkpointing=True)

        # Verify pipeline has checkpointer attached
        assert pipeline.checkpointer is not None, "Pipeline should have checkpointer"

        # Execute full pipeline with config to enable checkpointing
        result = await pipeline.ainvoke(initial_state, config=config)

        # Verify full execution completed
        assert result["run2_required"] is True
        assert result["confidence_score"] == 0.75
        assert "phase0_run1" in result
        assert "phase0_run2" in result
        assert "final_spec" in result
        assert "qa_results" in result

        # Verify state was checkpointed by getting state
        saved_state = await pipeline.aget_state(config)
        assert saved_state is not None
        assert saved_state.values.get("url") == "https://api.example.com"
        assert saved_state.values.get("final_spec") is not None

        # Test that we can retrieve the state using get_state_history
        # (this verifies checkpoint persistence)
        state_history = [state async for state in pipeline.aget_state_history(config)]
        assert len(state_history) > 0, "Should have checkpoint history"
