"""Tests for HybridGenerator."""

import json
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

import pytest

from claude_scraper.generators.hybrid_generator import (
    HybridGenerator,
    GeneratedFiles,
    BAML_AVAILABLE,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_ba_spec():
    """Sample BA Analyzer validated spec."""
    return {
        "source": "MISO",
        "source_type": "API",
        "executive_summary": {
            "data_type": "energy_pricing",
            "base_url": "https://api.misoenergy.org",
            "data_format": "json",
            "update_frequency": "hourly",
            "historical_support": True,
        },
        "authentication": {
            "required": True,
            "method": "API_KEY",
            "header_name": "Ocp-Apim-Subscription-Key",
            "notes": "API key required",
        },
        "endpoints": [
            {
                "endpoint_id": "da_exante_lmp",
                "name": "Day-Ahead LMP",
                "path": "/api/v1/da/{date}/exante/lmp",
                "method": "GET",
                "description": "Day-ahead ex-ante LMP data",
                "parameters": {"date": "YYYY-MM-DD"},
            }
        ],
    }


@pytest.fixture
def generator_no_baml(tmp_path):
    """Create HybridGenerator without BAML (for testing)."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir()

    # Create minimal templates
    (template_dir / "scraper_main.py.j2").write_text("""
class {{ class_name }}:
    def collect_content(self):
        {{ collect_content_code | indent(8) }}
""")

    (template_dir / "scraper_tests.py.j2").write_text("""
def test_{{ source_snake }}():
    assert True
""")

    (template_dir / "scraper_readme.md.j2").write_text("""
# {{ source }} {{ data_type }}
""")

    return HybridGenerator(template_dir=template_dir, use_baml=False)


@pytest.fixture
def mock_baml_code():
    """Mock BAML generated code."""
    class MockGeneratedCode:
        def __init__(self, code):
            self.code = code
            self.imports = []
            self.notes = ""

    return {
        "collect_content": MockGeneratedCode("# AI-generated collect code"),
        "validate_content": MockGeneratedCode("# AI-generated validate code"),
        "init": MockGeneratedCode("# AI-generated init code"),
    }


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================

def test_generator_initialization_without_baml(generator_no_baml):
    """Test generator initializes without BAML."""
    assert generator_no_baml.transformer is not None
    assert generator_no_baml.renderer is not None
    assert generator_no_baml.use_baml is False


def test_generator_initialization_baml_not_available():
    """Test generator raises error when BAML requested but not available."""
    if BAML_AVAILABLE:
        # BAML is available, skip test
        pytest.skip("BAML client is available")
    else:
        with pytest.raises(ImportError, match="BAML client not available"):
            HybridGenerator(use_baml=True)


# ============================================================================
# VALIDATION TESTS
# ============================================================================

def test_validate_ba_spec_valid(generator_no_baml, sample_ba_spec):
    """Test BA spec validation with valid spec."""
    errors = generator_no_baml.validate_ba_spec(sample_ba_spec)
    assert len(errors) == 0


def test_validate_ba_spec_missing_source(generator_no_baml, sample_ba_spec):
    """Test BA spec validation with missing source."""
    del sample_ba_spec["source"]

    errors = generator_no_baml.validate_ba_spec(sample_ba_spec)
    assert any("source" in err for err in errors)


def test_validate_ba_spec_missing_source_type(generator_no_baml, sample_ba_spec):
    """Test BA spec validation with missing source_type."""
    del sample_ba_spec["source_type"]

    errors = generator_no_baml.validate_ba_spec(sample_ba_spec)
    assert any("source_type" in err for err in errors)


def test_validate_ba_spec_invalid_source_type(generator_no_baml, sample_ba_spec):
    """Test BA spec validation with invalid source_type."""
    sample_ba_spec["source_type"] = "INVALID"

    errors = generator_no_baml.validate_ba_spec(sample_ba_spec)
    assert any("Invalid source_type" in err for err in errors)


def test_validate_ba_spec_missing_endpoints(generator_no_baml, sample_ba_spec):
    """Test BA spec validation with missing endpoints."""
    del sample_ba_spec["endpoints"]

    errors = generator_no_baml.validate_ba_spec(sample_ba_spec)
    assert any("endpoints" in err for err in errors)


def test_validate_ba_spec_empty_endpoints(generator_no_baml, sample_ba_spec):
    """Test BA spec validation with empty endpoints."""
    sample_ba_spec["endpoints"] = []

    errors = generator_no_baml.validate_ba_spec(sample_ba_spec)
    assert any("endpoint" in err for err in errors)


# ============================================================================
# GENERATION TESTS (WITHOUT BAML)
# ============================================================================

@pytest.mark.asyncio
async def test_generate_scraper_without_baml(generator_no_baml, sample_ba_spec, tmp_path):
    """Test scraper generation without BAML."""
    output_dir = tmp_path / "output"

    result = await generator_no_baml.generate_scraper(
        sample_ba_spec,
        output_dir,
        requires_ai=False,
    )

    # Check returned GeneratedFiles
    assert isinstance(result, GeneratedFiles)
    assert result.scraper_path.exists()
    assert result.test_path.exists()
    assert result.readme_path.exists()

    # Check metadata
    assert result.metadata["source"] == "MISO"
    assert result.metadata["data_type"] == "energy_pricing"
    assert result.metadata["dgroup"] == "miso_energy_pricing"
    assert result.metadata["ai_generated"] is False


@pytest.mark.asyncio
async def test_generate_scraper_creates_files(generator_no_baml, sample_ba_spec, tmp_path):
    """Test scraper generation creates expected files."""
    output_dir = tmp_path / "output"

    result = await generator_no_baml.generate_scraper(
        sample_ba_spec,
        output_dir,
        requires_ai=False,
    )

    # Check files exist
    assert result.scraper_path.name == "scraper_miso_energy_pricing_http.py"
    assert result.test_path.name == "test_scraper_miso_energy_pricing_http.py"
    assert result.readme_path.name == "README.md"

    # Check content
    scraper_code = result.scraper_path.read_text()
    assert "class MisoEnergyPricingCollector:" in scraper_code
    assert "# TODO: Implement collect_content logic" in scraper_code

    test_code = result.test_path.read_text()
    assert "def test_miso():" in test_code

    readme = result.readme_path.read_text()
    assert "# MISO energy_pricing" in readme


def test_generate_scraper_sync_wrapper(generator_no_baml, sample_ba_spec, tmp_path):
    """Test synchronous wrapper for generate_scraper."""
    output_dir = tmp_path / "output"

    result = generator_no_baml.generate_scraper_sync(
        sample_ba_spec,
        output_dir,
        requires_ai=False,
    )

    assert isinstance(result, GeneratedFiles)
    assert result.scraper_path.exists()


@pytest.mark.asyncio
async def test_generate_scraper_validation_error(generator_no_baml, sample_ba_spec, tmp_path):
    """Test scraper generation with validation error."""
    # Remove required field to trigger validation error
    del sample_ba_spec["source"]

    output_dir = tmp_path / "output"

    with pytest.raises(ValueError, match="validation failed"):
        await generator_no_baml.generate_scraper(sample_ba_spec, output_dir)


# ============================================================================
# AI CODE GENERATION TESTS (MOCKED BAML)
# ============================================================================

@pytest.mark.asyncio
@patch("claude_scraper.generators.hybrid_generator.BAML_AVAILABLE", True)
@patch("claude_scraper.generators.hybrid_generator.b")
async def test_generate_ai_code_mocked(mock_baml, generator_no_baml, sample_ba_spec, mock_baml_code):
    """Test AI code generation with mocked BAML."""
    # Mock BAML function calls
    mock_baml.GenerateCollectContent = AsyncMock(return_value=mock_baml_code["collect_content"])
    mock_baml.GenerateValidateContent = AsyncMock(return_value=mock_baml_code["validate_content"])

    # Enable BAML for this test
    generator_no_baml.use_baml = True

    transformed = generator_no_baml.transformer.transform(sample_ba_spec)
    baml_inputs = transformed["baml_inputs"]
    template_vars = transformed["template_vars"]

    result = await generator_no_baml._generate_ai_code(
        sample_ba_spec,
        baml_inputs,
        template_vars,
    )

    # Check AI code was generated
    assert "collect_content_code" in result
    assert "validate_content_code" in result
    assert "init_code" in result

    # Check BAML functions were called
    assert mock_baml.GenerateCollectContent.called
    assert mock_baml.GenerateValidateContent.called


@pytest.mark.asyncio
async def test_dummy_init_code(generator_no_baml):
    """Test dummy init code for non-complex auth."""
    result = await generator_no_baml._dummy_init_code()

    assert hasattr(result, "code")
    assert "# Standard authentication" in result.code


# ============================================================================
# COMPLEX AUTH TESTS
# ============================================================================

@pytest.mark.asyncio
@patch("claude_scraper.generators.hybrid_generator.BAML_AVAILABLE", True)
@patch("claude_scraper.generators.hybrid_generator.b")
async def test_generate_ai_code_with_oauth(
    mock_baml,
    generator_no_baml,
    sample_ba_spec,
    mock_baml_code,
):
    """Test AI code generation with OAuth authentication."""
    # Set OAuth auth
    sample_ba_spec["authentication"]["method"] = "OAUTH"

    # Mock BAML function calls
    mock_baml.GenerateCollectContent = AsyncMock(return_value=mock_baml_code["collect_content"])
    mock_baml.GenerateValidateContent = AsyncMock(return_value=mock_baml_code["validate_content"])
    mock_baml.GenerateComplexAuth = AsyncMock(return_value=mock_baml_code["init"])

    # Enable BAML
    generator_no_baml.use_baml = True

    transformed = generator_no_baml.transformer.transform(sample_ba_spec)
    baml_inputs = transformed["baml_inputs"]
    template_vars = transformed["template_vars"]

    result = await generator_no_baml._generate_ai_code(
        sample_ba_spec,
        baml_inputs,
        template_vars,
    )

    # Check GenerateComplexAuth was called for OAuth
    assert mock_baml.GenerateComplexAuth.called


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

@pytest.mark.asyncio
@patch("claude_scraper.generators.hybrid_generator.BAML_AVAILABLE", True)
@patch("claude_scraper.generators.hybrid_generator.b")
async def test_generate_ai_code_baml_error(mock_baml, generator_no_baml, sample_ba_spec):
    """Test AI code generation handles BAML errors."""
    # Mock all BAML functions - GenerateCollectContent raises error
    mock_baml.GenerateCollectContent = AsyncMock(side_effect=RuntimeError("BAML failed"))
    mock_baml.GenerateValidateContent = AsyncMock(return_value=Mock(code="# validate"))
    # Note: GenerateComplexAuth not needed since sample_ba_spec uses API_KEY (not complex auth)

    # Enable BAML
    generator_no_baml.use_baml = True

    transformed = generator_no_baml.transformer.transform(sample_ba_spec)
    baml_inputs = transformed["baml_inputs"]
    template_vars = transformed["template_vars"]

    with pytest.raises(RuntimeError, match="BAML code generation failed"):
        await generator_no_baml._generate_ai_code(
            sample_ba_spec,
            baml_inputs,
            template_vars,
        )


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_full_generation_workflow(generator_no_baml, sample_ba_spec, tmp_path):
    """Test full scraper generation workflow."""
    output_dir = tmp_path / "output"

    # Generate scraper
    result = await generator_no_baml.generate_scraper(
        sample_ba_spec,
        output_dir,
        requires_ai=False,
    )

    # Verify all files created
    assert result.scraper_path.exists()
    assert result.test_path.exists()
    assert result.readme_path.exists()

    # Verify metadata
    assert result.metadata["source"] == "MISO"
    assert result.metadata["collection_method"] == "HTTP_REST_API"
    assert result.metadata["requires_ai"] is False

    # Verify file content
    scraper_code = result.scraper_path.read_text()
    assert "MisoEnergyPricingCollector" in scraper_code

    test_code = result.test_path.read_text()
    assert "test_miso" in test_code

    readme = result.readme_path.read_text()
    assert "MISO" in readme


@pytest.mark.asyncio
async def test_generation_with_multiple_endpoints(generator_no_baml, sample_ba_spec, tmp_path):
    """Test generation with multiple endpoints."""
    # Add more endpoints
    sample_ba_spec["endpoints"].append({
        "endpoint_id": "rt_lmp",
        "name": "Real-Time LMP",
        "path": "/api/v1/rt/{date}/lmp",
        "method": "GET",
        "description": "Real-time LMP data",
    })

    output_dir = tmp_path / "output"

    result = await generator_no_baml.generate_scraper(
        sample_ba_spec,
        output_dir,
        requires_ai=False,
    )

    # Verify scraper generated successfully with multiple endpoints
    assert result.scraper_path.exists()

    # Verify metadata includes correct endpoint count
    transformed = generator_no_baml.transformer.transform(sample_ba_spec)
    assert len(transformed["baml_inputs"]["endpoints"]) == 2

    # Verify both endpoints were processed
    endpoints = transformed["baml_inputs"]["endpoints"]
    endpoint_ids = [ep.get("endpoint_id") for ep in endpoints]
    assert "da_exante_lmp" in endpoint_ids
    assert "rt_lmp" in endpoint_ids


@pytest.mark.asyncio
async def test_generation_with_different_auth_methods(generator_no_baml, sample_ba_spec, tmp_path):
    """Test generation with different authentication methods."""
    auth_methods = ["API_KEY", "BEARER_TOKEN", "BASIC_AUTH", "NONE"]

    for auth_method in auth_methods:
        sample_ba_spec["authentication"]["method"] = auth_method
        sample_ba_spec["authentication"]["required"] = auth_method != "NONE"

        output_dir = tmp_path / f"output_{auth_method.lower()}"

        result = await generator_no_baml.generate_scraper(
            sample_ba_spec,
            output_dir,
            requires_ai=False,
        )

        assert result.scraper_path.exists()

        # Verify auth method in generated code
        scraper_code = result.scraper_path.read_text()
        if auth_method != "NONE":
            assert auth_method in scraper_code or "# TODO" in scraper_code


# ============================================================================
# GENERATED FILES DATACLASS TESTS
# ============================================================================

def test_generated_files_dataclass():
    """Test GeneratedFiles dataclass."""
    files = GeneratedFiles(
        scraper_path=Path("/tmp/scraper.py"),
        test_path=Path("/tmp/test_scraper.py"),
        readme_path=Path("/tmp/README.md"),
        metadata={"source": "TEST"},
    )

    assert files.scraper_path == Path("/tmp/scraper.py")
    assert files.test_path == Path("/tmp/test_scraper.py")
    assert files.readme_path == Path("/tmp/README.md")
    assert files.metadata["source"] == "TEST"
