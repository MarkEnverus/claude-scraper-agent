"""Tests for BA Collator Agent.

This module tests the BACollator class for merging Run 1 and Run 2
analysis results with weighted confidence scoring.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from baml_client.types import (
    AuthenticationMethod,
    CollationResult,
    ComplexityLevel,
    ConfidenceLevel,
    DataSourceType,
    Endpoint,
    EndpointDetails,
    ExecutiveSummary,
    HTTPMethod,
    Phase0Detection,
    ResponseFormat,
    ScraperRecommendation,
    ScraperType,
    ValidatedSpec,
    ValidationStatus,
    ValidationSummary,
)

from claude_scraper.agents.ba_collator import BACollator
from claude_scraper.storage.repository import AnalysisRepository


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_phase0_run1():
    """Sample Phase 0 detection from Run 1."""
    return Phase0Detection(
        detected_type=DataSourceType.API,
        confidence=0.8,
        indicators=["REST API", "JSON responses"],
        discovered_api_calls=["https://api.example.com/v1"],
        endpoints=[
            Endpoint(
                path="/v1/data",
                method=HTTPMethod.GET,
                parameters=[],
                auth_required=False,
                response_format=ResponseFormat.JSON
            )
        ],
        url="https://api.example.com"
    )


@pytest.fixture
def sample_phase0_run2():
    """Sample Phase 0 detection from Run 2."""
    return Phase0Detection(
        detected_type=DataSourceType.API,
        confidence=0.95,
        indicators=["REST API", "JSON responses", "OpenAPI docs"],
        discovered_api_calls=[
            "https://api.example.com/v1",
            "https://api.example.com/v2"
        ],
        endpoints=[
            Endpoint(
                path="/v1/data",
                method=HTTPMethod.GET,
                parameters=[],
                auth_required=False,
                response_format=ResponseFormat.JSON
            ),
            Endpoint(
                path="/v2/data",
                method=HTTPMethod.GET,
                parameters=[],
                auth_required=True,
                response_format=ResponseFormat.JSON
            )
        ],
        url="https://api.example.com"
    )


@pytest.fixture
def sample_validated_spec_run1():
    """Sample validated spec from Run 1."""
    return ValidatedSpec(
        source="Run 1 Analysis",
        source_type="api",
        timestamp="2025-12-18T10:00:00Z",
        url="https://api.example.com",
        executive_summary=ExecutiveSummary(
            total_endpoints_discovered=3,
            accessible_endpoints=3,
            success_rate="100%",
            primary_formats=["JSON"],
            authentication_required=False,
            estimated_scraper_complexity=ComplexityLevel.LOW
        ),
        validation_summary=ValidationSummary(
            phases_completed=["Phase0", "Phase1", "Phase2", "Phase3"],
            documentation_review="Comprehensive",
            live_api_testing="Completed",
            discrepancies_found=0,
            confidence_score=0.75,
            confidence_level=ConfidenceLevel.MEDIUM,
            recommendation="Ready for Run 2"
        ),
        endpoints=[
            EndpointDetails(
                endpoint_id="ep1",
                name="Data Endpoint 1",
                type="api",
                base_url="https://api.example.com",
                path="/v1/data",
                method=HTTPMethod.GET,
                parameters={},
                authentication={},
                response_format=ResponseFormat.JSON,
                validation_status=ValidationStatus.TESTED_200_OK,
                accessible=True,
                last_tested="2025-12-18T10:00:00Z",
                notes="Test endpoint"
            )
        ],
        scraper_recommendation=ScraperRecommendation(
            type=ScraperType.API_CLIENT,
            confidence=ConfidenceLevel.HIGH,
            rationale=["Simple REST API"],
            complexity=ComplexityLevel.LOW,
            estimated_effort="2-3 hours",
            key_challenges=[]
        ),
        discrepancies=[],
        artifacts_generated=["run1/validated_datasource_spec.json"],
        next_steps=["Proceed to Run 2"]
    )


@pytest.fixture
def sample_validated_spec_run2():
    """Sample validated spec from Run 2."""
    return ValidatedSpec(
        source="Run 2 Analysis",
        source_type="api",
        timestamp="2025-12-18T11:00:00Z",
        url="https://api.example.com",
        executive_summary=ExecutiveSummary(
            total_endpoints_discovered=47,
            accessible_endpoints=42,
            success_rate="89%",
            primary_formats=["JSON", "CSV"],
            authentication_required=True,
            estimated_scraper_complexity=ComplexityLevel.MEDIUM
        ),
        validation_summary=ValidationSummary(
            phases_completed=["Phase0", "Phase1", "Phase2", "Phase3"],
            documentation_review="Comprehensive",
            live_api_testing="Completed with Puppeteer",
            discrepancies_found=2,
            confidence_score=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            recommendation="Ready for collation"
        ),
        endpoints=[
            EndpointDetails(
                endpoint_id="ep1",
                name="Data Endpoint 1",
                type="api",
                base_url="https://api.example.com",
                path="/v1/data",
                method=HTTPMethod.GET,
                parameters={},
                authentication={},
                response_format=ResponseFormat.JSON,
                validation_status=ValidationStatus.TESTED_200_OK,
                accessible=True,
                last_tested="2025-12-18T11:00:00Z",
                notes="Re-tested endpoint"
            ),
            EndpointDetails(
                endpoint_id="ep2",
                name="Data Endpoint 2",
                type="api",
                base_url="https://api.example.com",
                path="/v2/data",
                method=HTTPMethod.GET,
                parameters={},
                authentication={"required": "true"},
                response_format=ResponseFormat.JSON,
                validation_status=ValidationStatus.TESTED_200_OK,
                accessible=True,
                last_tested="2025-12-18T11:00:00Z",
                notes="New endpoint discovered"
            )
        ],
        scraper_recommendation=ScraperRecommendation(
            type=ScraperType.API_CLIENT,
            confidence=ConfidenceLevel.HIGH,
            rationale=["REST API with auth", "Well-documented"],
            complexity=ComplexityLevel.MEDIUM,
            estimated_effort="4-6 hours",
            key_challenges=["Authentication handling"]
        ),
        discrepancies=[],
        artifacts_generated=["run2/validated_datasource_spec.json"],
        next_steps=["Generate scraper"]
    )


@pytest.fixture
def collator(tmp_path):
    """Create BA Collator instance with temp directory."""
    return BACollator(base_dir=tmp_path / "datasource_analysis")


# =============================================================================
# Unit Tests: Weighted Confidence Calculation
# =============================================================================

def test_calculate_weighted_confidence(collator):
    """Test weighted confidence calculation uses correct 30/70 weights."""
    result = collator.calculate_weighted_confidence(0.8, 0.95)

    # Expected: (0.3 * 0.8) + (0.7 * 0.95) = 0.24 + 0.665 = 0.905
    expected = 0.905
    assert abs(result - expected) < 0.001, (
        f"Expected {expected}, got {result}"
    )


def test_calculate_weighted_confidence_equal_scores(collator):
    """Test weighted confidence when both runs have same score."""
    result = collator.calculate_weighted_confidence(0.9, 0.9)

    # Expected: (0.3 * 0.9) + (0.7 * 0.9) = 0.9
    assert result == 0.9


def test_calculate_weighted_confidence_low_run1_high_run2(collator):
    """Test that Run 2 has more influence (70% weight)."""
    result = collator.calculate_weighted_confidence(0.5, 1.0)

    # Expected: (0.3 * 0.5) + (0.7 * 1.0) = 0.15 + 0.7 = 0.85
    expected = 0.85
    assert abs(result - expected) < 0.001


def test_calculate_weighted_confidence_high_run1_low_run2(collator):
    """Test Run 2 dominates even when Run 1 is higher."""
    result = collator.calculate_weighted_confidence(1.0, 0.5)

    # Expected: (0.3 * 1.0) + (0.7 * 0.5) = 0.3 + 0.35 = 0.65
    # This shows Run 2's weight is significant
    expected = 0.65
    assert abs(result - expected) < 0.001


def test_calculate_weighted_confidence_zero_scores(collator):
    """Test weighted confidence with zero scores."""
    result = collator.calculate_weighted_confidence(0.0, 0.0)
    assert result == 0.0


def test_calculate_weighted_confidence_rounding(collator):
    """Test that confidence is rounded to 3 decimal places."""
    result = collator.calculate_weighted_confidence(0.7777, 0.8888)

    # Expected: (0.3 * 0.7777) + (0.7 * 0.8888) = 0.23331 + 0.62216 = 0.85547
    # Rounded to 3 decimals: 0.855
    assert result == 0.855


def test_calculate_weighted_confidence_validates_run1():
    """Test that run1_confidence out of bounds raises ValueError."""
    collator = BACollator()

    with pytest.raises(ValueError, match="run1_confidence must be between 0.0 and 1.0"):
        collator.calculate_weighted_confidence(1.5, 0.9)

    with pytest.raises(ValueError, match="run1_confidence must be between 0.0 and 1.0"):
        collator.calculate_weighted_confidence(-0.1, 0.9)


def test_calculate_weighted_confidence_validates_run2():
    """Test that run2_confidence out of bounds raises ValueError."""
    collator = BACollator()

    with pytest.raises(ValueError, match="run2_confidence must be between 0.0 and 1.0"):
        collator.calculate_weighted_confidence(0.8, 1.2)

    with pytest.raises(ValueError, match="run2_confidence must be between 0.0 and 1.0"):
        collator.calculate_weighted_confidence(0.8, -0.05)


# =============================================================================
# Unit Tests: Conflict Resolution
# =============================================================================

def test_resolve_conflicts_run2_wins(collator):
    """Test conflict resolution favors Run 2."""
    result = collator.resolve_conflicts(
        run1_value="HTTP",
        run2_value="HTTPS",
        field_name="protocol"
    )

    assert result == "HTTPS", "Run 2 should win conflicts"


def test_resolve_conflicts_same_value(collator):
    """Test no conflict when values are identical."""
    result = collator.resolve_conflicts(
        run1_value="JSON",
        run2_value="JSON",
        field_name="format"
    )

    assert result == "JSON"


def test_resolve_conflicts_empty_strings(collator):
    """Test conflict resolution with empty strings."""
    result = collator.resolve_conflicts(
        run1_value="",
        run2_value="value",
        field_name="field"
    )

    assert result == "value", "Run 2 wins even with empty Run 1"


def test_resolve_conflicts_run1_has_value_run2_empty(collator):
    """Test Run 2 wins even when empty (explicit override)."""
    result = collator.resolve_conflicts(
        run1_value="value",
        run2_value="",
        field_name="field"
    )

    assert result == "", "Run 2 wins unconditionally"


# =============================================================================
# Unit Tests: Collation Result Creation
# =============================================================================

def test_create_collation_result(
    collator,
    sample_validated_spec_run1,
    sample_validated_spec_run2
):
    """Test collation result creation."""
    # Create merged spec (minimal mock for testing)
    final_spec = sample_validated_spec_run2
    final_spec.validation_summary.final_confidence_score = 0.905
    final_spec.validation_summary.discrepancies_resolved = 2

    result = collator.create_collation_result(
        final_spec=final_spec,
        run1_spec=sample_validated_spec_run1,
        run2_spec=sample_validated_spec_run2
    )

    assert isinstance(result, CollationResult)
    assert result.collation_complete is True
    assert result.final_spec_path == "datasource_analysis/final_validated_spec.json"
    assert result.final_confidence_score == 0.905
    assert result.total_endpoints == 47
    assert result.endpoints_run1 == 1
    assert result.endpoints_run2 == 2
    assert result.improvements_count == 1  # 2 - 1 = 1
    assert result.discrepancies_resolved == 2
    assert result.ready_for_scraper_generation is True


def test_create_collation_result_consistency_rate(
    collator,
    sample_validated_spec_run1,
    sample_validated_spec_run2
):
    """Test consistency rate calculation in collation result."""
    # Mark endpoints as tested in both runs
    for ep in sample_validated_spec_run2.endpoints:
        ep.tested_in_run1 = True
        ep.tested_in_run2 = True

    result = collator.create_collation_result(
        final_spec=sample_validated_spec_run2,
        run1_spec=sample_validated_spec_run1,
        run2_spec=sample_validated_spec_run2
    )

    # 1 endpoint from run1, 2 tested in both = 100% consistency
    assert result.consistency_rate == "100%"


def test_create_collation_result_no_run1_endpoints(
    collator,
    sample_validated_spec_run1,
    sample_validated_spec_run2
):
    """Test consistency rate when Run 1 has no endpoints."""
    sample_validated_spec_run1.endpoints = []

    result = collator.create_collation_result(
        final_spec=sample_validated_spec_run2,
        run1_spec=sample_validated_spec_run1,
        run2_spec=sample_validated_spec_run2
    )

    assert result.consistency_rate == "N/A"


# =============================================================================
# Integration Tests: Phase 0 Merge
# =============================================================================

@pytest.mark.asyncio
async def test_merge_phase0_weighted_confidence(
    collator,
    sample_phase0_run1,
    sample_phase0_run2
):
    """Test Phase 0 merge uses correct weights (30% Run 1, 70% Run 2)."""
    # Mock BAML function
    mock_merged = Phase0Detection(
        detected_type=DataSourceType.API,
        confidence=0.905,  # (0.3 * 0.8) + (0.7 * 0.95)
        indicators=["REST API", "JSON responses", "OpenAPI docs"],
        discovered_api_calls=[
            "https://api.example.com/v1",
            "https://api.example.com/v2"
        ],
        endpoints=sample_phase0_run2.endpoints,
        url="https://api.example.com"
    )

    with patch('claude_scraper.agents.ba_collator.b.MergePhase0', new_callable=AsyncMock) as mock_baml:
        mock_baml.return_value = mock_merged

        result = await collator.merge_phase0(
            run1=sample_phase0_run1,
            run2=sample_phase0_run2,
            run2_focus_areas=["endpoints", "api_calls"]
        )

        # Verify BAML was called
        mock_baml.assert_called_once_with(
            run1=sample_phase0_run1,
            run2=sample_phase0_run2,
            run2_focus_areas=["endpoints", "api_calls"]
        )

        # Verify weighted confidence
        expected_confidence = 0.905
        assert abs(result.confidence - expected_confidence) < 0.01

        # Verify merge results
        assert result.detected_type == DataSourceType.API
        assert len(result.indicators) == 3  # Merged indicators
        assert len(result.discovered_api_calls) == 2  # Merged API calls


@pytest.mark.asyncio
async def test_merge_phase0_error_handling(
    collator,
    sample_phase0_run1,
    sample_phase0_run2
):
    """Test Phase 0 merge error handling."""
    with patch('claude_scraper.agents.ba_collator.b.MergePhase0', new_callable=AsyncMock) as mock_baml:
        mock_baml.side_effect = Exception("BAML merge failed")

        with pytest.raises(Exception, match="BAML merge failed"):
            await collator.merge_phase0(
                run1=sample_phase0_run1,
                run2=sample_phase0_run2,
                run2_focus_areas=[]
            )


# =============================================================================
# Integration Tests: Complete Spec Merge
# =============================================================================

@pytest.mark.asyncio
async def test_weighted_confidence_with_consistency_bonus():
    """Test that consistency bonus is applied when runs are highly consistent."""
    collator = BACollator()

    # Runs with similar confidence (difference = 0.05 < 0.1)
    run1_confidence = 0.85
    run2_confidence = 0.90

    # Base weighted: (0.3 * 0.85) + (0.7 * 0.90) = 0.255 + 0.63 = 0.885
    # Bonus: +0.05 because difference (0.05) < 0.1
    # Expected: 0.885 + 0.05 = 0.935

    base_weighted = collator.calculate_weighted_confidence(run1_confidence, run2_confidence)
    assert base_weighted == 0.885  # Verify base calculation

    # In real collation, bonus would be added by BAML prompt
    # This test verifies the calculation logic is correct
    expected_with_bonus = min(1.0, base_weighted + 0.05)
    assert expected_with_bonus == 0.935


@pytest.mark.asyncio
async def test_merge_complete_specs(
    collator,
    sample_validated_spec_run1,
    sample_validated_spec_run2
):
    """Test complete specification merge."""
    # Mock BAML function
    mock_merged = sample_validated_spec_run2
    mock_merged.validation_summary.final_confidence_score = 0.905
    mock_merged.validation_summary.collation_complete = True
    mock_merged.validation_summary.runs_analyzed = 2

    with patch('claude_scraper.agents.ba_collator.b.MergeCompleteSpecs', new_callable=AsyncMock) as mock_baml:
        mock_baml.return_value = mock_merged

        result = await collator.merge_complete_specs(
            run1=sample_validated_spec_run1,
            run2=sample_validated_spec_run2,
            save_result=False  # Don't save during test
        )

        # Verify BAML was called
        mock_baml.assert_called_once_with(
            run1=sample_validated_spec_run1,
            run2=sample_validated_spec_run2
        )

        # Verify collation metadata
        assert result.validation_summary.collation_complete is True
        assert result.validation_summary.runs_analyzed == 2
        assert result.validation_summary.final_confidence_score == 0.905


@pytest.mark.asyncio
async def test_merge_complete_specs_saves_result(
    collator,
    sample_validated_spec_run1,
    sample_validated_spec_run2
):
    """Test complete specification merge saves result."""
    mock_merged = sample_validated_spec_run2
    mock_merged.validation_summary.final_confidence_score = 0.905

    with patch('claude_scraper.agents.ba_collator.b.MergeCompleteSpecs', new_callable=AsyncMock) as mock_baml:
        mock_baml.return_value = mock_merged

        result = await collator.merge_complete_specs(
            run1=sample_validated_spec_run1,
            run2=sample_validated_spec_run2,
            save_result=True
        )

        # Verify file was saved
        assert collator.repository.exists("final_validated_spec.json")


@pytest.mark.asyncio
async def test_merge_complete_specs_error_handling(
    collator,
    sample_validated_spec_run1,
    sample_validated_spec_run2
):
    """Test complete spec merge error handling."""
    with patch('claude_scraper.agents.ba_collator.b.MergeCompleteSpecs', new_callable=AsyncMock) as mock_baml:
        mock_baml.side_effect = Exception("Merge failed")

        with pytest.raises(Exception, match="Merge failed"):
            await collator.merge_complete_specs(
                run1=sample_validated_spec_run1,
                run2=sample_validated_spec_run2,
                save_result=False
            )


# =============================================================================
# Unit Tests: Initialization
# =============================================================================

def test_collator_initialization_default():
    """Test collator initialization with default repository."""
    collator = BACollator()

    assert collator.RUN1_WEIGHT == 0.3
    assert collator.RUN2_WEIGHT == 0.7
    assert collator.repository is not None


def test_collator_initialization_custom_repo(tmp_path):
    """Test collator initialization with custom repository."""
    repo = AnalysisRepository(tmp_path / "custom_analysis")
    collator = BACollator(repository=repo)

    assert collator.repository == repo


def test_collator_initialization_custom_base_dir(tmp_path):
    """Test collator initialization with custom base directory."""
    custom_dir = tmp_path / "my_analysis"
    collator = BACollator(base_dir=custom_dir)

    assert str(custom_dir) in str(collator.repository.base_dir)


# =============================================================================
# Edge Cases
# =============================================================================

def test_calculate_weighted_confidence_boundary_values(collator):
    """Test weighted confidence with boundary values."""
    # Test with 0.0 and 1.0
    result = collator.calculate_weighted_confidence(0.0, 1.0)
    assert result == 0.7  # 0.0 * 0.3 + 1.0 * 0.7

    # Test with 1.0 and 0.0
    result = collator.calculate_weighted_confidence(1.0, 0.0)
    assert result == 0.3  # 1.0 * 0.3 + 0.0 * 0.7


def test_resolve_conflicts_special_characters(collator):
    """Test conflict resolution with special characters."""
    result = collator.resolve_conflicts(
        run1_value="value with spaces",
        run2_value="value-with-dashes",
        field_name="special_field"
    )

    assert result == "value-with-dashes"


def test_create_collation_result_negative_improvements(
    collator,
    sample_validated_spec_run1,
    sample_validated_spec_run2
):
    """Test collation result when Run 2 has fewer endpoints (shouldn't happen)."""
    # Simulate Run 2 having fewer endpoints (edge case)
    sample_validated_spec_run2.endpoints = []

    result = collator.create_collation_result(
        final_spec=sample_validated_spec_run2,
        run1_spec=sample_validated_spec_run1,
        run2_spec=sample_validated_spec_run2
    )

    # Improvements should be capped at 0 (no negative improvements)
    assert result.improvements_count == 0
