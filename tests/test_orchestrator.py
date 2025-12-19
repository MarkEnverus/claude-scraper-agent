"""Tests for ScraperOrchestrator."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from claude_scraper.generators.orchestrator import (
    ScraperOrchestrator,
    OrchestrationResult,
    BAAnalysisError,
    GenerationError,
)
from claude_scraper.generators.hybrid_generator import GeneratedFiles


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_ba_spec():
    """Sample BA spec for testing."""
    return {
        "source": "MISO",
        "source_type": "API",
        "executive_summary": {
            "data_type": "energy_pricing",
            "base_url": "https://api.misoenergy.org",
        },
        "endpoints": [{"endpoint_id": "test", "path": "/api/v1/test"}],
        "authentication": {"required": True, "method": "API_KEY"},
        "validation_summary": {"confidence_score": 0.92},
    }


@pytest.fixture
def ba_spec_file(tmp_path, sample_ba_spec):
    """Create temp BA spec file."""
    spec_file = tmp_path / "validated_datasource_spec.json"
    spec_file.write_text(json.dumps(sample_ba_spec))
    return spec_file


@pytest.fixture
def mock_generated_files(tmp_path):
    """Mock GeneratedFiles."""
    return GeneratedFiles(
        scraper_path=tmp_path / "scraper_miso_energy_pricing_http.py",
        test_path=tmp_path / "test_scraper_miso_energy_pricing_http.py",
        readme_path=tmp_path / "README.md",
        metadata={
            "source": "MISO",
            "data_type": "energy_pricing",
            "collection_method": "HTTP_REST_API",
            "ai_generated": False,
        },
    )


@pytest.fixture
def mock_hybrid_generator(mock_generated_files):
    """Create mock HybridGenerator."""
    generator = Mock()
    generator.validate_ba_spec = Mock(return_value=[])  # No errors
    generator.generate_scraper = AsyncMock(return_value=mock_generated_files)
    return generator


@pytest.fixture
def orchestrator(mock_hybrid_generator, tmp_path):
    """Create orchestrator with mocked generator."""
    return ScraperOrchestrator(
        hybrid_generator=mock_hybrid_generator,
        analysis_output_dir=str(tmp_path / "analysis"),
    )


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================

@patch("claude_scraper.generators.orchestrator.HybridGenerator")
def test_orchestrator_initialization_defaults(mock_hybrid_generator_class):
    """Test orchestrator initializes with default dependencies."""
    # Mock HybridGenerator creation to avoid BAML requirement
    mock_instance = Mock()
    mock_hybrid_generator_class.return_value = mock_instance

    orchestrator = ScraperOrchestrator()

    # Verify HybridGenerator was created with no arguments (defaults)
    mock_hybrid_generator_class.assert_called_once_with()
    assert orchestrator.hybrid_generator is not None
    assert orchestrator.analysis_output_dir == Path("datasource_analysis")


def test_orchestrator_initialization_custom(mock_hybrid_generator):
    """Test orchestrator initializes with custom dependencies."""
    orchestrator = ScraperOrchestrator(
        hybrid_generator=mock_hybrid_generator,
        analysis_output_dir="custom_analysis",
    )

    assert orchestrator.hybrid_generator == mock_hybrid_generator
    assert orchestrator.analysis_output_dir == Path("custom_analysis")


# ============================================================================
# GENERATE_FROM_SPEC TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_generate_from_spec_success(orchestrator, ba_spec_file, tmp_path):
    """Test successful generation from existing spec."""
    result = await orchestrator.generate_from_spec(
        ba_spec_file=str(ba_spec_file),
        output_dir=tmp_path / "output",
        requires_ai=False,
    )

    # Verify result
    assert isinstance(result, OrchestrationResult)
    assert result.source_type == "API"
    assert result.analysis_performed is False
    assert result.ba_spec_path == ba_spec_file
    assert result.generated_files is not None
    assert result.generated_files.scraper_path is not None

    # Verify generator was called
    orchestrator.hybrid_generator.generate_scraper.assert_called_once()


@pytest.mark.asyncio
async def test_generate_from_spec_file_not_found(orchestrator):
    """Test handling of missing spec file."""
    with pytest.raises(FileNotFoundError, match="BA spec file not found"):
        await orchestrator.generate_from_spec(ba_spec_file="nonexistent.json")


@pytest.mark.asyncio
async def test_generate_from_spec_invalid_json(orchestrator, tmp_path):
    """Test handling of invalid JSON."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{invalid json")

    with pytest.raises(ValueError, match="Invalid JSON"):
        await orchestrator.generate_from_spec(ba_spec_file=str(invalid_file))


@pytest.mark.asyncio
async def test_generate_from_spec_validation_fails(orchestrator, tmp_path):
    """Test handling of BA spec that fails validation."""
    # Create spec with missing required fields
    invalid_spec = tmp_path / "invalid_spec.json"
    invalid_spec.write_text(json.dumps({"source": "TEST"}))

    # Mock validator to return errors
    orchestrator.hybrid_generator.validate_ba_spec = Mock(
        return_value=["Missing required field: source_type"]
    )

    with pytest.raises(ValueError, match="BA spec validation failed"):
        await orchestrator.generate_from_spec(ba_spec_file=str(invalid_spec))


@pytest.mark.asyncio
async def test_generate_from_spec_custom_output_dir(orchestrator, ba_spec_file, tmp_path):
    """Test generation with custom output directory."""
    custom_dir = tmp_path / "my_custom_scrapers"

    result = await orchestrator.generate_from_spec(
        ba_spec_file=str(ba_spec_file),
        output_dir=custom_dir,
        requires_ai=False,
    )

    assert result.generated_files.scraper_path is not None
    # Verify custom output dir was passed to generator
    call_args = orchestrator.hybrid_generator.generate_scraper.call_args
    assert call_args[1]["output_dir"] == custom_dir


@pytest.mark.asyncio
async def test_generate_from_spec_smart_default_output_dir(orchestrator, ba_spec_file):
    """Test generation with smart default output directory."""
    result = await orchestrator.generate_from_spec(
        ba_spec_file=str(ba_spec_file),
        requires_ai=False,
    )

    # Verify smart default was used
    call_args = orchestrator.hybrid_generator.generate_scraper.call_args
    output_dir = call_args[1]["output_dir"]
    assert "generated_scrapers" in str(output_dir)
    assert "miso" in str(output_dir).lower()


@pytest.mark.asyncio
async def test_generate_from_spec_generation_fails(orchestrator, ba_spec_file):
    """Test handling of generation failure."""
    # Mock generator to fail
    orchestrator.hybrid_generator.generate_scraper = AsyncMock(
        side_effect=RuntimeError("BAML failed")
    )

    with pytest.raises(GenerationError, match="Scraper generation failed"):
        await orchestrator.generate_from_spec(ba_spec_file=str(ba_spec_file))


# ============================================================================
# GENERATE_FROM_URL TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_generate_from_url_success(orchestrator, sample_ba_spec, tmp_path):
    """Test successful generation from URL."""
    # Setup: Create BA spec file that BA Analyzer would create
    spec_file = orchestrator.analysis_output_dir / "validated_datasource_spec.json"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(json.dumps(sample_ba_spec))

    # Mock BA Analyzer
    mock_validated_spec = Mock()
    mock_validated_spec.source_type = "API"
    mock_validated_spec.validation_summary = Mock(confidence_score=0.92)
    mock_validated_spec.endpoints = [{"path": "/test"}]

    with patch("claude_scraper.agents.ba_analyzer.BAAnalyzer") as MockBAAnalyzer:
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.run_full_analysis = AsyncMock(return_value=mock_validated_spec)
        MockBAAnalyzer.return_value = mock_analyzer_instance

        # Execute
        result = await orchestrator.generate_from_url(
            url="https://api.test.com",
            output_dir=tmp_path / "output",
        )

        # Verify
        assert isinstance(result, OrchestrationResult)
        assert result.source_type == "API"
        assert result.confidence_score == 0.92
        assert result.analysis_performed is True

        # Verify BA Analyzer was called
        mock_analyzer_instance.run_full_analysis.assert_called_once_with("https://api.test.com")

        # Verify generator was called
        orchestrator.hybrid_generator.generate_scraper.assert_called_once()


@pytest.mark.asyncio
async def test_generate_from_url_empty_url(orchestrator):
    """Test handling of empty URL."""
    with pytest.raises(ValueError, match="url cannot be empty"):
        await orchestrator.generate_from_url(url="")


@pytest.mark.asyncio
async def test_generate_from_url_ba_analyzer_fails(orchestrator):
    """Test handling of BA Analyzer failure."""
    with patch("claude_scraper.agents.ba_analyzer.BAAnalyzer") as MockBAAnalyzer:
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.run_full_analysis = AsyncMock(
            side_effect=Exception("Network error")
        )
        MockBAAnalyzer.return_value = mock_analyzer_instance

        with pytest.raises(BAAnalysisError, match="BA Analyzer failed"):
            await orchestrator.generate_from_url(url="https://api.test.com")


@pytest.mark.asyncio
async def test_generate_from_url_spec_file_not_created(orchestrator):
    """Test handling when BA Analyzer doesn't create expected file."""
    mock_validated_spec = Mock()
    mock_validated_spec.source_type = "API"
    mock_validated_spec.endpoints = []
    mock_validated_spec.validation_summary.confidence_score = 0.9

    with patch("claude_scraper.agents.ba_analyzer.BAAnalyzer") as MockBAAnalyzer:
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.run_full_analysis = AsyncMock(return_value=mock_validated_spec)
        MockBAAnalyzer.return_value = mock_analyzer_instance

        # Don't create the spec file - BA Analyzer "forgot" to write it
        with pytest.raises(BAAnalysisError, match="did not create expected output file"):
            await orchestrator.generate_from_url(url="https://api.test.com")


@pytest.mark.asyncio
async def test_generate_from_url_generation_fails(orchestrator, sample_ba_spec, tmp_path):
    """Test handling of generation failure after successful BA analysis."""
    # Setup spec file
    spec_file = orchestrator.analysis_output_dir / "validated_datasource_spec.json"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(json.dumps(sample_ba_spec))

    # Mock BA Analyzer success
    mock_validated_spec = Mock()
    mock_validated_spec.source_type = "API"
    mock_validated_spec.validation_summary = Mock(confidence_score=0.92)
    mock_validated_spec.endpoints = []

    # Mock generator failure
    orchestrator.hybrid_generator.generate_scraper = AsyncMock(
        side_effect=RuntimeError("Template rendering failed")
    )

    with patch("claude_scraper.agents.ba_analyzer.BAAnalyzer") as MockBAAnalyzer:
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.run_full_analysis = AsyncMock(return_value=mock_validated_spec)
        MockBAAnalyzer.return_value = mock_analyzer_instance

        with pytest.raises(GenerationError, match="Scraper generation failed"):
            await orchestrator.generate_from_url(url="https://api.test.com")


# ============================================================================
# ROUTING TESTS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("source_type", ["API", "FTP", "WEBSITE", "EMAIL"])
async def test_generate_scraper_routes(orchestrator, sample_ba_spec, tmp_path, source_type):
    """Test routing for all supported source types."""
    sample_ba_spec["source_type"] = source_type

    result = await orchestrator._generate_scraper(
        ba_spec_dict=sample_ba_spec,
        output_dir=tmp_path / "output",
        requires_ai=False,
    )

    assert result is not None
    orchestrator.hybrid_generator.generate_scraper.assert_called_once()


@pytest.mark.asyncio
async def test_generate_scraper_unsupported_source_type(orchestrator, sample_ba_spec, tmp_path):
    """Test handling of unsupported source type."""
    sample_ba_spec["source_type"] = "INVALID"

    with pytest.raises(GenerationError, match="Unsupported source_type"):
        await orchestrator._generate_scraper(
            ba_spec_dict=sample_ba_spec,
            output_dir=tmp_path / "output",
            requires_ai=False,
        )


# ============================================================================
# OUTPUT DIRECTORY TESTS
# ============================================================================

def test_determine_output_dir(orchestrator, sample_ba_spec):
    """Test smart output directory determination."""
    output_dir = orchestrator._determine_output_dir(sample_ba_spec)

    assert "generated_scrapers" in str(output_dir)
    assert "miso" in str(output_dir).lower()


# ============================================================================
# LOAD BA SPEC TESTS
# ============================================================================

def test_load_ba_spec_file_success(orchestrator, ba_spec_file):
    """Test loading valid BA spec file."""
    ba_spec = orchestrator._load_ba_spec_file(ba_spec_file)

    assert ba_spec["source"] == "MISO"
    assert ba_spec["source_type"] == "API"


def test_load_ba_spec_file_invalid_json(orchestrator, tmp_path):
    """Test loading invalid JSON."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{invalid json")

    with pytest.raises(ValueError, match="Invalid JSON"):
        orchestrator._load_ba_spec_file(invalid_file)


def test_load_ba_spec_file_validation_fails(orchestrator, tmp_path):
    """Test loading BA spec that fails validation."""
    invalid_spec = tmp_path / "invalid_spec.json"
    invalid_spec.write_text(json.dumps({"source": "TEST"}))

    # Mock validator to return errors
    orchestrator.hybrid_generator.validate_ba_spec = Mock(
        return_value=["Missing source_type"]
    )

    with pytest.raises(ValueError, match="BA spec validation failed"):
        orchestrator._load_ba_spec_file(invalid_spec)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_full_generation_workflow_from_spec(orchestrator, ba_spec_file):
    """Test full generation workflow from spec file to output."""
    result = await orchestrator.generate_from_spec(
        ba_spec_file=str(ba_spec_file),
        requires_ai=False,
    )

    # Verify complete result
    assert result.generated_files is not None
    assert result.source_type == "API"
    assert result.analysis_performed is False
    assert result.generated_files.scraper_path is not None
    assert result.generated_files.test_path is not None

    # Verify generator was called with correct args
    call_args = orchestrator.hybrid_generator.generate_scraper.call_args
    assert call_args[1]["requires_ai"] is False
