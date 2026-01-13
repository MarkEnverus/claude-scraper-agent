"""Unit tests for BA Validator Agent"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from pathlib import Path

from agentic_scraper.agents.ba_validator import BAValidator, RUN2_CONFIDENCE_THRESHOLD
from agentic_scraper.types import (
    Phase0Detection,
    Phase1Documentation,
    Phase2Tests,
    ValidatedSpec,
    ValidationReport,
    ValidationResult,
    ValidationOverallStatus,
    DataSourceType,
    HTTPMethod,
    AuthenticationMethod,
    DocQuality,
    ResponseFormat,
    EndpointSpec,
    # Missing imports identified by QA:
    Endpoint,
    ExecutiveSummary,
    ComplexityLevel,
    ValidationSummary,
    ConfidenceLevel,
    EndpointDetails,
    ValidationStatus,
    ScraperType,
    ScraperRecommendation,
    PhaseValidation,
    CriticalGap,
)
from agentic_scraper.storage.repository import AnalysisRepository


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_repository():
    """Mock repository for testing"""
    return MagicMock(spec=AnalysisRepository)


@pytest.fixture
def validator(mock_llm_provider, mock_repository):
    """BA Validator instance with mocked repository"""
    return BAValidator(
        llm_provider=mock_llm_provider,
        repository=mock_repository
    )


@pytest.fixture
def high_confidence_phase0():
    """High confidence Phase 0 detection result"""
    return Phase0Detection(
        detected_type=DataSourceType.API,
        confidence=0.95,
        indicators=["REST endpoints", "JSON responses", "API documentation"],
        discovered_api_calls=["https://api.example.com/v1/data"],
        discovered_endpoint_urls=["https://api.example.com/v1/data"],
        auth_method="API_KEY",
        base_url="https://api.example.com",
        url="https://api.example.com"
    )


@pytest.fixture
def low_confidence_phase0():
    """Low confidence Phase 0 detection result"""
    return Phase0Detection(
        detected_type=DataSourceType.WEBSITE,
        confidence=0.45,
        indicators=["HTML pages"],
        discovered_api_calls=[],
        discovered_endpoint_urls=[],
        auth_method="NONE",
        base_url="https://example.com",
        url="https://example.com"
    )


@pytest.fixture
def complete_phase1():
    """Complete Phase 1 documentation result"""
    return Phase1Documentation(
        source="Documentation Analysis",
        timestamp="2025-01-20T10:00:00Z",
        url="https://api.example.com/docs",
        endpoints=[],
        doc_quality=DocQuality.HIGH,
        notes="Comprehensive documentation found"
    )


@pytest.fixture
def complete_phase2():
    """Complete Phase 2 testing result"""
    return Phase2Tests(
        source="Live API Testing",
        timestamp="2025-01-20T10:30:00Z",
        files_saved=["test_results.txt", "response.json"]
    )


@pytest.fixture
def high_confidence_spec():
    """High confidence validated specification"""
    return ValidatedSpec(
        source="BA Agent",
        source_type="api",
        datasource="example_api",
        dataset="test_data",
        timestamp="2025-01-20T11:00:00Z",
        url="https://api.example.com",
        executive_summary=ExecutiveSummary(
            total_endpoints_discovered=10,
            accessible_endpoints=10,
            success_rate="100%",
            primary_formats=["JSON"],
            authentication_required=True,
            estimated_scraper_complexity=ComplexityLevel.MEDIUM
        ),
        validation_summary=ValidationSummary(
            phases_completed=["phase0", "phase1", "phase2", "phase3"],
            documentation_review="completed",
            live_api_testing="completed",
            discrepancies_found=0,
            confidence_score=0.92,
            confidence_level=ConfidenceLevel.HIGH,
            recommendation="Spec validated - ready for scraper generation"
        ),
        endpoints=[
            EndpointDetails(
                endpoint_id="endpoint-1",
                name="Get Data",
                type="api",
                base_url="https://api.example.com",
                path="/v1/data",
                method=HTTPMethod.GET,
                parameters={},
                authentication={},
                response_format=ResponseFormat.JSON,
                validation_status=ValidationStatus.TESTED_200_OK,
                accessible=True,
                last_tested="2025-01-20T10:30:00Z",
                notes="Working endpoint"
            )
        ] * 10,  # 10 endpoints to match executive_summary
        scraper_recommendation=ScraperRecommendation(
            type=ScraperType.API_CLIENT,
            rationale=["Well-documented API", "Consistent responses"],
            complexity=ComplexityLevel.MEDIUM,
            estimated_effort="2-4 hours",
            key_challenges=["Authentication handling"]
        ),
        discrepancies=[],
        artifacts_generated=["phase0.json", "phase1.json", "phase2.json"],
        next_steps=["Generate scraper"]
    )


@pytest.fixture
def low_confidence_spec():
    """Low confidence validated specification"""
    return ValidatedSpec(
        source="BA Agent",
        source_type="api",
        datasource="example_api",
        dataset="test_data",
        timestamp="2025-01-20T11:00:00Z",
        url="https://api.example.com",
        executive_summary=ExecutiveSummary(
            total_endpoints_discovered=50,
            accessible_endpoints=5,
            success_rate="10%",
            primary_formats=["JSON"],
            authentication_required=True,
            estimated_scraper_complexity=ComplexityLevel.HIGH
        ),
        validation_summary=ValidationSummary(
            phases_completed=["phase0", "phase1", "phase2", "phase3"],
            documentation_review="partial",
            live_api_testing="limited",
            discrepancies_found=5,
            confidence_score=0.45,
            confidence_level=ConfidenceLevel.LOW,
            recommendation="Human review recommended"
        ),
        endpoints=[
            EndpointDetails(
                endpoint_id="endpoint-1",
                name="Get Data",
                type="api",
                base_url="https://api.example.com",
                path="/v1/data",
                method=HTTPMethod.GET,
                parameters={},
                authentication={},
                response_format=ResponseFormat.JSON,
                validation_status=ValidationStatus.NOT_TESTED,
                accessible=False,
                last_tested="2025-01-20T10:30:00Z",
                notes="Incomplete"
            )
        ] * 5,  # Only 5 documented, but 50 discovered
        scraper_recommendation=ScraperRecommendation(
            type=ScraperType.API_CLIENT,
            rationale=["Needs more investigation"],
            complexity=ComplexityLevel.HIGH,
            estimated_effort="8-16 hours",
            key_challenges=["Incomplete endpoint enumeration", "Authentication unclear"]
        ),
        discrepancies=[],
        artifacts_generated=["phase0.json"],
        next_steps=["Run second analysis pass"]
    )


@pytest.fixture
def validation_report_pass():
    """Validation report with PASS status"""
    return ValidationReport(
        validation_timestamp="2025-01-20T12:00:00Z",
        input_file="validated_datasource_spec.json",
        overall_status=ValidationOverallStatus.PASS,
        overall_confidence=0.92,
        phase_validations={
            "phase0": PhaseValidation(
                status=ValidationOverallStatus.PASS,
                issues=[],
                notes="Phase 0 complete and valid"
            ),
            "phase1": PhaseValidation(
                status=ValidationOverallStatus.PASS,
                issues=[],
                notes="Phase 1 complete and valid"
            ),
            "phase2": PhaseValidation(
                status=ValidationOverallStatus.PASS,
                issues=[],
                notes="Phase 2 complete and valid"
            )
        },
        critical_gaps=[],
        recommendations_for_second_pass=[],
        validation_summary="All phases complete and high quality"
    )


@pytest.fixture
def validation_report_fail():
    """Validation report with FAIL status and critical gaps"""
    return ValidationReport(
        validation_timestamp="2025-01-20T12:00:00Z",
        input_file="validated_datasource_spec.json",
        overall_status=ValidationOverallStatus.FAIL,
        overall_confidence=0.45,
        phase_validations={
            "phase0": PhaseValidation(
                status=ValidationOverallStatus.PASS,
                issues=[],
                notes="Phase 0 OK"
            ),
            "phase1": PhaseValidation(
                status=ValidationOverallStatus.NEEDS_IMPROVEMENT,
                issues=[
                    {
                        "severity": "medium",
                        "issue": "Extraction quality marked as PARTIAL",
                        "recommendation": "Use Puppeteer in second pass"
                    }
                ],
                notes="Phase 1 incomplete"
            ),
            "phase3": PhaseValidation(
                status=ValidationOverallStatus.FAIL,
                issues=[
                    {
                        "severity": "critical",
                        "issue": "Incomplete endpoint enumeration",
                        "recommendation": "MUST enumerate all endpoints"
                    }
                ],
                notes="Critical gaps found"
            )
        },
        critical_gaps=[
            CriticalGap(
                gap_type="incomplete_enumeration",
                description="Only 5/50 endpoints documented",
                action_required="Second pass must enumerate ALL endpoints",
                discovered=50,
                documented=5,
                missing=45
            ),
            CriticalGap(
                gap_type="puppeteer_not_used",
                description="JavaScript-rendered site, but Puppeteer not used",
                action_required="Second pass MUST use Puppeteer"
            )
        ],
        recommendations_for_second_pass=[
            "Use Puppeteer to extract complete menu/navigation structure",
            "Test ALL discovered dataset slugs (not just 2-3 samples)",
            "Enumerate every endpoint with full specifications"
        ],
        validation_summary="First pass incomplete - second pass required"
    )


# ============================================================================
# BAValidator Initialization Tests
# ============================================================================


def test_validator_initialization(mock_llm_provider, mock_repository):
    """Test validator initializes with correct defaults"""
    validator = BAValidator(llm_provider=mock_llm_provider, repository=mock_repository)

    assert validator.repository == mock_repository
    assert validator.confidence_threshold == RUN2_CONFIDENCE_THRESHOLD


def test_validator_initialization_default_repository(mock_llm_provider):
    """Test validator creates default repository if none provided"""
    validator = BAValidator(llm_provider=mock_llm_provider)

    assert isinstance(validator.repository, AnalysisRepository)


def test_validator_initialization_custom_threshold(mock_llm_provider, mock_repository):
    """Test validator accepts custom confidence threshold"""
    custom_threshold = 0.7
    validator = BAValidator(
        llm_provider=mock_llm_provider,
        repository=mock_repository,
        confidence_threshold=custom_threshold
    )

    assert validator.confidence_threshold == custom_threshold


def test_validator_initialization_invalid_threshold(mock_llm_provider, mock_repository):
    """Test validator rejects invalid confidence threshold"""
    with pytest.raises(ValueError, match="confidence_threshold must be <= 1.0"):
        BAValidator(llm_provider=mock_llm_provider, repository=mock_repository, confidence_threshold=1.5)

    with pytest.raises(ValueError, match="confidence_threshold must be >= 0.0"):
        BAValidator(llm_provider=mock_llm_provider, repository=mock_repository, confidence_threshold=-0.1)


# ============================================================================
# Phase Validation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_validate_phase0_high_confidence(validator, high_confidence_phase0):
    """Test validation passes with high confidence Phase 0"""
    # Mock LLM provider
    validator.llm.invoke_structured = Mock(return_value=ValidationResult(
        confidence=0.95,
        identified_gaps=[],
        recommendations=[],
        validation_notes="Phase 0 detection is high quality"
    ))

    result = await validator.validate_phase0(
        high_confidence_phase0,
        "https://api.example.com"
    )

    assert result["confidence"] == 0.95
    assert len(result["identified_gaps"]) == 0


@pytest.mark.asyncio
async def test_validate_phase0_low_confidence(validator, low_confidence_phase0):
    """Test validation identifies issues with low confidence Phase 0"""
    # Mock LLM provider
    validator.llm.invoke_structured = Mock(return_value=ValidationResult(
        confidence=0.45,
        identified_gaps=["Few indicators", "No API endpoints found"],
        recommendations=["Use network monitoring", "Try Puppeteer"],
        validation_notes="Phase 0 needs improvement"
    ))

    result = await validator.validate_phase0(
        low_confidence_phase0,
        "https://example.com"
    )

    assert result["confidence"] < 0.8
    assert len(result["identified_gaps"]) > 0
    assert len(result["recommendations"]) > 0


@pytest.mark.asyncio
async def test_validate_phase1(validator, complete_phase1, high_confidence_phase0):
    """Test Phase 1 validation"""
    # Mock LLM provider
    validator.llm.invoke_structured = Mock(return_value=ValidationResult(
        confidence=0.85,
        identified_gaps=[],
        recommendations=[],
        validation_notes="Phase 1 documentation is complete"
    ))

    result = await validator.validate_phase1(
        complete_phase1,
        high_confidence_phase0
    )

    assert result["confidence"] >= 0.8


@pytest.mark.asyncio
async def test_validate_phase2(validator, complete_phase2, complete_phase1):
    """Test Phase 2 validation"""
    # Mock LLM provider
    validator.llm.invoke_structured = Mock(return_value=ValidationResult(
        confidence=0.88,
        identified_gaps=[],
        recommendations=[],
        validation_notes="Phase 2 testing is evidence-based"
    ))

    result = await validator.validate_phase2(complete_phase2, complete_phase1)

    assert result["confidence"] >= 0.8
    assert "validation_notes" in result


# ============================================================================
# Complete Spec Validation Tests
# ============================================================================


@pytest.mark.asyncio
async def test_validate_complete_spec_high_confidence(
    validator,
    high_confidence_spec,
    validation_report_pass
):
    """Test complete spec validation with high confidence"""
    # Mock LLM provider
    validator.llm.invoke_structured = Mock(return_value=validation_report_pass)

    report = await validator.validate_complete_spec(high_confidence_spec)

    assert report.overall_status == ValidationOverallStatus.PASS
    assert report.overall_confidence >= 0.8
    assert len(report.critical_gaps) == 0
    validator.repository.save.assert_called_once_with(
        "ba_validation_report.json",
        validation_report_pass
    )


@pytest.mark.asyncio
async def test_validate_complete_spec_low_confidence(
    validator,
    low_confidence_spec,
    validation_report_fail
):
    """Test complete spec validation with low confidence"""
    # Mock LLM provider
    validator.llm.invoke_structured = Mock(return_value=validation_report_fail)

    report = await validator.validate_complete_spec(low_confidence_spec)

    assert report.overall_status == ValidationOverallStatus.FAIL
    assert report.overall_confidence < 0.8
    assert len(report.critical_gaps) > 0
    assert len(report.recommendations_for_second_pass) > 0


@pytest.mark.asyncio
async def test_validate_complete_spec_saves_report(validator, high_confidence_spec):
    """Test that validation report is saved to repository"""
    mock_report = MagicMock(spec=ValidationReport)
    mock_report.overall_status = ValidationOverallStatus.PASS
    mock_report.overall_confidence = 0.92
    mock_report.critical_gaps = []
    mock_report.recommendations_for_second_pass = []

    # Mock LLM provider
    validator.llm.invoke_structured = Mock(return_value=mock_report)

    await validator.validate_complete_spec(high_confidence_spec)

    validator.repository.save.assert_called_once_with(
        "ba_validation_report.json",
        mock_report
    )


@pytest.mark.asyncio
async def test_validate_complete_spec_save_fails_gracefully(validator, high_confidence_spec):
    """Test that validation continues even if report save fails."""
    mock_report = MagicMock(spec=ValidationReport)
    mock_report.overall_confidence = 0.92
    validator.repository.save.side_effect = Exception("Disk full")

    # Mock LLM provider
    validator.llm.invoke_structured = Mock(return_value=mock_report)

    # Should not raise exception even though save fails
    result = await validator.validate_complete_spec(high_confidence_spec)

    assert result == mock_report  # Report still returned
    # Verify save was attempted
    validator.repository.save.assert_called_once()


# ============================================================================
# Run 2 Decision Logic Tests
# ============================================================================


def test_should_run_second_analysis_low_confidence(validator, validation_report_fail):
    """Test Run 2 triggered when confidence < 0.8"""
    assert validator.should_run_second_analysis(validation_report_fail) is True


def test_should_not_run_second_analysis_high_confidence(validator, validation_report_pass):
    """Test Run 2 skipped when confidence >= 0.8"""
    assert validator.should_run_second_analysis(validation_report_pass) is False


def test_should_run_second_analysis_at_threshold(validator):
    """Test Run 2 decision at exact threshold"""
    # Exactly at threshold (0.8) should NOT trigger Run 2
    report = ValidationReport(
        validation_timestamp="2025-01-20T12:00:00Z",
        input_file="test.json",
        overall_status=ValidationOverallStatus.PASS,
        overall_confidence=0.8,
        phase_validations={},
        critical_gaps=[],
        recommendations_for_second_pass=[],
        validation_summary="At threshold"
    )

    assert validator.should_run_second_analysis(report) is False

    # Just below threshold should trigger Run 2
    report.overall_confidence = 0.79
    assert validator.should_run_second_analysis(report) is True


def test_should_run_second_analysis_custom_threshold(mock_llm_provider, mock_repository):
    """Test Run 2 decision with custom threshold"""
    custom_threshold = 0.9
    validator = BAValidator(
        llm_provider=mock_llm_provider,
        repository=mock_repository,
        confidence_threshold=custom_threshold
    )

    report = ValidationReport(
        validation_timestamp="2025-01-20T12:00:00Z",
        input_file="test.json",
        overall_status=ValidationOverallStatus.PASS,
        overall_confidence=0.85,
        phase_validations={},
        critical_gaps=[],
        recommendations_for_second_pass=[],
        validation_summary="Test"
    )

    # 0.85 < 0.9, so should trigger Run 2
    assert validator.should_run_second_analysis(report) is True

    # 0.91 >= 0.9, so should not trigger Run 2
    report.overall_confidence = 0.91
    assert validator.should_run_second_analysis(report) is False


# ============================================================================
# Run 2 Focus Areas Tests
# ============================================================================


def test_get_run2_focus_areas_with_gaps(validator, validation_report_fail):
    """Test extracting focus areas from validation report with gaps"""
    focus_areas = validator.get_run2_focus_areas(validation_report_fail)

    assert len(focus_areas) > 0
    # Should include recommendations
    assert any("Puppeteer" in area for area in focus_areas)
    # Should include critical gaps
    assert any("incomplete_enumeration" in area for area in focus_areas)
    # Should include phase issues
    assert any("phase1" in area.lower() or "phase3" in area.lower() for area in focus_areas)


def test_get_run2_focus_areas_no_gaps(validator, validation_report_pass):
    """Test extracting focus areas when no gaps exist"""
    focus_areas = validator.get_run2_focus_areas(validation_report_pass)

    assert len(focus_areas) == 0


def test_get_run2_focus_areas_includes_recommendations(validator):
    """Test that recommendations are included in focus areas"""
    report = ValidationReport(
        validation_timestamp="2025-01-20T12:00:00Z",
        input_file="test.json",
        overall_status=ValidationOverallStatus.NEEDS_IMPROVEMENT,
        overall_confidence=0.7,
        phase_validations={},
        critical_gaps=[],
        recommendations_for_second_pass=[
            "Use Puppeteer for extraction",
            "Test all endpoints",
            "Verify authentication"
        ],
        validation_summary="Needs improvement"
    )

    focus_areas = validator.get_run2_focus_areas(report)

    assert len(focus_areas) == 3
    assert "Use Puppeteer for extraction" in focus_areas
    assert "Test all endpoints" in focus_areas


def test_get_run2_focus_areas_includes_critical_gaps(validator):
    """Test that critical gaps are included in focus areas"""
    report = ValidationReport(
        validation_timestamp="2025-01-20T12:00:00Z",
        input_file="test.json",
        overall_status=ValidationOverallStatus.FAIL,
        overall_confidence=0.5,
        phase_validations={},
        critical_gaps=[
            CriticalGap(
                gap_type="incomplete_enumeration",
                description="Only 5/50 endpoints documented",
                action_required="Enumerate all 50 endpoints",
                discovered=50,
                documented=5,
                missing=45
            )
        ],
        recommendations_for_second_pass=[],
        validation_summary="Critical gaps"
    )

    focus_areas = validator.get_run2_focus_areas(report)

    assert len(focus_areas) > 0
    assert any("incomplete_enumeration" in area for area in focus_areas)
    assert any("50 endpoints" in area for area in focus_areas)


# ============================================================================
# Validation Summary Tests
# ============================================================================


def test_create_validation_summary_pass(validator, validation_report_pass):
    """Test creating summary for passing validation"""
    summary = validator.create_validation_summary(validation_report_pass)

    assert summary["status"] == "PASS"
    assert summary["confidence"] >= 0.8
    assert summary["needs_run2"] is False
    assert summary["critical_gaps_count"] == 0
    assert "phase_validations" in summary


def test_create_validation_summary_fail(validator, validation_report_fail):
    """Test creating summary for failing validation"""
    summary = validator.create_validation_summary(validation_report_fail)

    assert summary["status"] == "FAIL"
    assert summary["confidence"] < 0.8
    assert summary["needs_run2"] is True
    assert summary["critical_gaps_count"] > 0
    assert summary["recommendations_count"] > 0


def test_create_validation_summary_includes_phase_details(validator, validation_report_fail):
    """Test that summary includes phase-level details"""
    summary = validator.create_validation_summary(validation_report_fail)

    assert "phase_validations" in summary
    assert "phase0" in summary["phase_validations"]
    assert "phase1" in summary["phase_validations"]
    assert "phase3" in summary["phase_validations"]

    # Check phase validation details
    phase1 = summary["phase_validations"]["phase1"]
    assert phase1["status"] == "NEEDS_IMPROVEMENT"
    assert phase1["issues_count"] == 1

    phase3 = summary["phase_validations"]["phase3"]
    assert phase3["status"] == "FAIL"
    assert phase3["issues_count"] == 1
