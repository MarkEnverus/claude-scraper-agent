"""End-to-end integration tests for scraper generation pipeline.

Tests the complete workflow:
1. BA Analyzer spec → Orchestrator → HybridGenerator → Generated files
2. Validates generated Python code is syntactically correct
3. Validates generated tests are executable
4. Validates file structure matches expectations
"""

import ast
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from agentic_scraper.generators.orchestrator import ScraperOrchestrator
from agentic_scraper.generators.hybrid_generator import HybridGenerator


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def realistic_ba_spec():
    """Realistic BA Analyzer spec based on MISO example."""
    return {
        "source": "MISO",
        "source_type": "API",
        "executive_summary": {
            "data_type": "energy_pricing",
            "base_url": "https://api.misoenergy.org",
            "data_format": "json",
            "update_frequency": "hourly",
            "historical_support": True,
            "collection_method": "HTTP_REST_API",
            "registration_required": True,
            "registration_url": "https://www.misoenergy.org/markets-and-operations/real-time--market-data/",
        },
        "authentication": {
            "required": True,
            "method": "API_KEY",
            "header_name": "Ocp-Apim-Subscription-Key",
            "notes": "API key required for all endpoints",
        },
        "endpoints": [
            {
                "endpoint_id": "da_exante_lmp",
                "name": "Day-Ahead Ex-Ante LMP",
                "path": "/api/v1/da/{date}/exante/lmp",
                "method": "GET",
                "description": "Day-ahead ex-ante locational marginal pricing data",
                "parameters": {
                    "date": {
                        "type": "string",
                        "format": "YYYY-MM-DD",
                        "required": True,
                        "description": "Date for which to retrieve LMP data"
                    }
                },
                "response_format": "json",
                "pagination": False,
            },
            {
                "endpoint_id": "rt_lmp",
                "name": "Real-Time LMP",
                "path": "/api/v1/rt/{date}/lmp",
                "method": "GET",
                "description": "Real-time 5-minute locational marginal pricing data",
                "parameters": {
                    "date": {
                        "type": "string",
                        "format": "YYYY-MM-DD",
                        "required": True,
                    }
                },
                "response_format": "json",
                "pagination": False,
            }
        ],
        "validation_summary": {
            "confidence_score": 0.92,
            "validation_date": "2024-01-15",
            "notes": "High confidence - well-documented API with clear endpoints",
        }
    }


@pytest.fixture
def ba_spec_file(tmp_path, realistic_ba_spec):
    """Create BA spec file in temporary analysis directory."""
    analysis_dir = tmp_path / "datasource_analysis"
    analysis_dir.mkdir()
    spec_file = analysis_dir / "validated_datasource_spec.json"
    spec_file.write_text(json.dumps(realistic_ba_spec, indent=2))
    return spec_file


# ============================================================================
# END-TO-END INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_orchestrator_to_generated_files(ba_spec_file, tmp_path, mock_llm_factory):
    """Test complete workflow from BA spec file to generated scraper files."""
    # Setup
    output_dir = tmp_path / "generated_scrapers" / "miso"
    generator = HybridGenerator(factory=mock_llm_factory)
    orchestrator = ScraperOrchestrator(
        hybrid_generator=generator,
        analysis_output_dir=ba_spec_file.parent
    )

    # Execute: Generate scraper from spec file
    result = await orchestrator.generate_from_spec(
        ba_spec_file=ba_spec_file,
        output_dir=output_dir,
    )

    # Verify: Result structure
    assert result.generated_files is not None
    assert isinstance(result.generated_files, list)  # Orchestrator returns list (one per endpoint)
    assert len(result.generated_files) > 0
    assert result.ba_spec_path == ba_spec_file
    assert result.source_type == "API"
    assert result.analysis_performed is False
    assert result.confidence_score == 0.92

    # Verify: Files exist (check first generated scraper)
    first_files = result.generated_files[0]
    assert first_files.scraper_path.exists()
    assert first_files.test_path.exists()
    assert first_files.readme_path.exists()

    # Verify: Metadata
    metadata = first_files.metadata
    assert metadata["source"] == "MISO"
    assert metadata["data_type"] == "energy_pricing"
    assert metadata["dgroup"] == "miso_energy_pricing"
    assert metadata["collection_method"] == "HTTP_REST_API"
    assert metadata["ai_generated"] is True  # Now uses LLM-generated code


@pytest.mark.asyncio
async def test_e2e_generated_scraper_is_valid_python(ba_spec_file, tmp_path, mock_llm_factory):
    """Test generated scraper code is syntactically valid Python."""
    # Setup
    output_dir = tmp_path / "generated_scrapers" / "miso"
    generator = HybridGenerator(factory=mock_llm_factory)
    orchestrator = ScraperOrchestrator(
        hybrid_generator=generator,
        analysis_output_dir=ba_spec_file.parent
    )

    # Execute
    result = await orchestrator.generate_from_spec(
        ba_spec_file=ba_spec_file,
        output_dir=output_dir,
    )

    # Read generated scraper code (first endpoint)
    first_files = result.generated_files[0]
    scraper_code = first_files.scraper_path.read_text()

    # Verify: Code is valid Python (AST parsing)
    try:
        ast.parse(scraper_code)
    except SyntaxError as e:
        pytest.fail(f"Generated scraper has syntax errors: {e}")

    # Verify: Contains expected class structure
    assert "class" in scraper_code
    assert "MisoEnergyPricingCollector" in scraper_code
    assert "def collect_content" in scraper_code


@pytest.mark.asyncio
async def test_e2e_generated_tests_are_valid_python(ba_spec_file, tmp_path, mock_llm_factory):
    """Test generated test file is syntactically valid Python."""
    # Setup
    output_dir = tmp_path / "generated_scrapers" / "miso"
    generator = HybridGenerator(factory=mock_llm_factory)
    orchestrator = ScraperOrchestrator(
        hybrid_generator=generator,
        analysis_output_dir=ba_spec_file.parent
    )

    # Execute
    result = await orchestrator.generate_from_spec(
        ba_spec_file=ba_spec_file,
        output_dir=output_dir,
    )

    # Read generated test code (first endpoint)
    first_files = result.generated_files[0]
    test_code = first_files.test_path.read_text()

    # Verify: Code is valid Python (AST parsing)
    try:
        ast.parse(test_code)
    except SyntaxError as e:
        pytest.fail(f"Generated test file has syntax errors: {e}")

    # Verify: Contains test structure
    assert "def test_" in test_code


@pytest.mark.asyncio
async def test_e2e_readme_contains_required_sections(ba_spec_file, tmp_path, mock_llm_factory):
    """Test generated README contains all required sections."""
    # Setup
    output_dir = tmp_path / "generated_scrapers" / "miso"
    generator = HybridGenerator(factory=mock_llm_factory)
    orchestrator = ScraperOrchestrator(
        hybrid_generator=generator,
        analysis_output_dir=ba_spec_file.parent
    )

    # Execute
    result = await orchestrator.generate_from_spec(
        ba_spec_file=ba_spec_file,
        output_dir=output_dir,
    )

    # Read README (first endpoint)
    first_files = result.generated_files[0]
    readme_content = first_files.readme_path.read_text()

    # Verify: Contains required sections
    assert "MISO" in readme_content
    assert "energy_pricing" in readme_content or "Energy Pricing" in readme_content
    assert "#" in readme_content  # Has markdown headers


@pytest.mark.asyncio
async def test_e2e_hybrid_generator_directly(realistic_ba_spec, tmp_path, mock_llm_factory):
    """Test HybridGenerator directly (bypass orchestrator)."""
    # Setup
    output_dir = tmp_path / "generated_scrapers" / "direct_test"
    generator = HybridGenerator(factory=mock_llm_factory)

    # Execute
    result = await generator.generate_scraper(
        ba_spec=realistic_ba_spec,
        output_dir=output_dir,
    )

    # Verify: Files created
    assert result.scraper_path.exists()
    assert result.test_path.exists()
    assert result.readme_path.exists()

    # Verify: Metadata correct
    assert result.metadata["source"] == "MISO"
    assert result.metadata["ai_generated"] is True  # Now uses LLM-generated code

    # Verify: Scraper code valid Python
    scraper_code = result.scraper_path.read_text()
    try:
        ast.parse(scraper_code)
    except SyntaxError as e:
        pytest.fail(f"Generated scraper has syntax errors: {e}")


@pytest.mark.asyncio
async def test_e2e_multiple_source_types(tmp_path, mock_llm_factory):
    """Test generation for all supported source types."""
    source_types = ["API", "FTP", "WEBSITE", "EMAIL"]

    for source_type in source_types:
        # Create BA spec for this source type
        ba_spec = {
            "source": f"Test{source_type}",
            "source_type": source_type,
            "executive_summary": {
                "data_type": "test_data",
                "base_url": "https://test.example.com",
                "data_format": "json",
                "update_frequency": "daily",
                "historical_support": False,
            },
            "endpoints": [{
                "endpoint_id": "test_endpoint",
                "path": "/test",
                "method": "GET",
                "description": f"Test {source_type} endpoint"
            }],
            "authentication": {"required": False, "method": "NONE"},
        }

        # Generate scraper
        output_dir = tmp_path / "source_types" / source_type.lower()
        generator = HybridGenerator(factory=mock_llm_factory)

        result = await generator.generate_scraper(
            ba_spec=ba_spec,
            output_dir=output_dir,
        )

        # Verify: Files exist and code is valid Python
        assert result.scraper_path.exists()
        scraper_code = result.scraper_path.read_text()
        try:
            ast.parse(scraper_code)
        except SyntaxError as e:
            pytest.fail(f"Generated {source_type} scraper has syntax errors: {e}")


@pytest.mark.asyncio
async def test_e2e_orchestrator_smart_output_dir(ba_spec_file, tmp_path, mock_llm_factory):
    """Test orchestrator creates smart default output directory."""
    # Setup
    generator = HybridGenerator(factory=mock_llm_factory)
    orchestrator = ScraperOrchestrator(
        hybrid_generator=generator,
        analysis_output_dir=ba_spec_file.parent
    )

    # Execute: Don't specify output_dir, let orchestrator choose
    result = await orchestrator.generate_from_spec(
        ba_spec_file=ba_spec_file,
    )

    # Verify: Smart default used (should contain source name)
    first_files = result.generated_files[0]
    scraper_path = str(first_files.scraper_path)
    assert "miso" in scraper_path.lower()
    # Orchestrator generates to sourcing/scraping/<source>/ by default
    assert "sourcing" in scraper_path or "generated_scrapers" in scraper_path


@pytest.mark.asyncio
async def test_e2e_validation_error_handling(tmp_path, mock_llm_factory):
    """Test end-to-end validation error handling."""
    # Create invalid BA spec (missing required fields)
    invalid_spec = {
        "source": "InvalidSource",
        # Missing source_type
        # Missing endpoints
    }

    # Generate scraper should fail with validation error
    generator = HybridGenerator(factory=mock_llm_factory)
    output_dir = tmp_path / "invalid_test"

    with pytest.raises(ValueError, match="validation failed"):
        await generator.generate_scraper(
            ba_spec=invalid_spec,
            output_dir=output_dir,
        )


@pytest.mark.asyncio
async def test_e2e_file_naming_conventions(ba_spec_file, tmp_path, mock_llm_factory):
    """Test generated files follow naming conventions."""
    # Setup
    output_dir = tmp_path / "naming_test"
    generator = HybridGenerator(factory=mock_llm_factory)
    orchestrator = ScraperOrchestrator(
        hybrid_generator=generator,
        analysis_output_dir=ba_spec_file.parent
    )

    # Execute
    result = await orchestrator.generate_from_spec(
        ba_spec_file=ba_spec_file,
        output_dir=output_dir,
    )

    # Verify: File naming conventions
    first_files = result.generated_files[0]
    scraper_filename = first_files.scraper_path.name
    test_filename = first_files.test_path.name

    # Scraper file should be: scraper_{source}_{data_type}_{method}.py or main.py
    assert scraper_filename.endswith(".py")
    assert scraper_filename.startswith("scraper_") or scraper_filename == "main.py"
    if scraper_filename.startswith("scraper_"):
        assert "miso" in scraper_filename.lower()

    # Test file should be: test_{scraper_filename} or test_main.py
    assert test_filename.endswith(".py")
    assert test_filename.startswith("test_")

    # README should be README.md or exists
    assert first_files.readme_path.name.upper().startswith("README")


# ============================================================================
# ORCHESTRATOR ROUTING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_orchestrator_routes_correctly(tmp_path, mock_llm_factory):
    """Test orchestrator correctly routes to HybridGenerator for all source types."""
    source_types = ["API", "FTP", "WEBSITE", "EMAIL"]

    for source_type in source_types:
        # Create BA spec
        ba_spec = {
            "source": f"Test{source_type}",
            "source_type": source_type,
            "executive_summary": {
                "data_type": "test_data",
                "base_url": "https://test.example.com",
                "data_format": "json",
                "update_frequency": "daily",
            },
            "endpoints": [{"endpoint_id": "test", "path": "/test"}],
            "authentication": {"required": False, "method": "NONE"},
        }

        # Write to file
        analysis_dir = tmp_path / "routing_test" / source_type
        analysis_dir.mkdir(parents=True, exist_ok=True)
        spec_file = analysis_dir / "validated_datasource_spec.json"
        spec_file.write_text(json.dumps(ba_spec))

        # Generate via orchestrator
        generator = HybridGenerator(factory=mock_llm_factory)
        orchestrator = ScraperOrchestrator(
            hybrid_generator=generator,
            analysis_output_dir=analysis_dir
        )
        result = await orchestrator.generate_from_spec(
            ba_spec_file=spec_file,
        )

        # Verify: Routing worked
        assert result.source_type == source_type
        first_files = result.generated_files[0]
        assert first_files.scraper_path.exists()


# ============================================================================
# PERFORMANCE AND STRESS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_generation_performance(realistic_ba_spec, tmp_path, mock_llm_factory):
    """Test generation completes in reasonable time."""
    import time

    # Setup
    output_dir = tmp_path / "performance_test"
    generator = HybridGenerator(factory=mock_llm_factory)

    # Execute: Measure time
    start_time = time.time()
    result = await generator.generate_scraper(
        ba_spec=realistic_ba_spec,
        output_dir=output_dir,
    )
    duration = time.time() - start_time

    # Verify: Completes in under 5 seconds (generous threshold)
    assert duration < 5.0, f"Generation took {duration:.2f}s (expected < 5s)"

    # Verify: Files created successfully
    assert result.scraper_path.exists()
