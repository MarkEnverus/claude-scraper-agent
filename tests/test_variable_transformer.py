"""Tests for VariableTransformer."""

import pytest

from agentic_scraper.generators.variable_transformer import VariableTransformer


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def transformer():
    """Create VariableTransformer instance."""
    return VariableTransformer()


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
                "authentication": {"required": True},
            }
        ],
    }


# ============================================================================
# TRANSFORMATION TESTS
# ============================================================================

def test_transform_basic(transformer, sample_ba_spec):
    """Test basic transformation."""
    result = transformer.transform(sample_ba_spec)

    assert "template_vars" in result
    assert "baml_inputs" in result

    template_vars = result["template_vars"]
    assert template_vars["source"] == "MISO"
    assert template_vars["data_type"] == "energy_pricing"


def test_extract_template_vars(transformer, sample_ba_spec):
    """Test template variable extraction."""
    result = transformer.transform(sample_ba_spec)
    template_vars = result["template_vars"]

    # Check basic fields
    assert template_vars["source"] == "MISO"
    assert template_vars["source_lower"] == "miso"
    assert template_vars["source_upper"] == "MISO"
    assert template_vars["source_snake"] == "miso"
    assert template_vars["data_type"] == "energy_pricing"

    # Check generated names
    assert template_vars["class_name"] == "MisoEnergyPricingCollector"
    assert template_vars["dgroup"] == "miso_energy_pricing"
    assert template_vars["filename"] == "main.py"

    # Check auth fields
    assert template_vars["auth_required"] is True
    assert template_vars["auth_method"] == "API_KEY"
    assert template_vars["auth_header_name"] == "Ocp-Apim-Subscription-Key"
    assert template_vars["auth_env_var"] == "MISO_API_KEY"

    # Check endpoints
    assert len(template_vars["endpoints"]) == 1
    assert template_vars["endpoints"][0]["name"] == "da_exante_lmp"


def test_extract_baml_inputs(transformer, sample_ba_spec):
    """Test BAML input extraction."""
    result = transformer.transform(sample_ba_spec)
    baml_inputs = result["baml_inputs"]

    assert baml_inputs["auth_method"] == "API_KEY"
    assert baml_inputs["collection_method"] == "HTTP_REST_API"
    assert baml_inputs["update_frequency"] == "hourly"
    assert baml_inputs["historical_support"] is True
    assert len(baml_inputs["endpoints"]) == 1


def test_clean_source_name(transformer):
    """Test source name cleaning."""
    assert transformer._clean_source_name("MISO Energy") == "MISO"
    assert transformer._clean_source_name("NYISO API") == "NYISO"
    assert transformer._clean_source_name("Test-Data-Exchange") == "TestDataExchange"


def test_to_snake_case(transformer):
    """Test snake_case conversion."""
    assert transformer._to_snake_case("MISO") == "miso"
    assert transformer._to_snake_case("MISO Energy") == "miso_energy"
    assert transformer._to_snake_case("DataType") == "data_type"
    assert transformer._to_snake_case("already_snake") == "already_snake"


def test_to_camel_case(transformer):
    """Test CamelCase conversion."""
    assert transformer._to_camel_case("miso") == "Miso"
    assert transformer._to_camel_case("miso_energy") == "MisoEnergy"
    assert transformer._to_camel_case("miso-energy") == "MisoEnergy"
    assert transformer._to_camel_case("MISO ENERGY") == "MisoEnergy"


def test_generate_class_name(transformer):
    """Test class name generation."""
    assert transformer._generate_class_name("MISO", "energy_pricing") == "MisoEnergyPricingCollector"
    assert transformer._generate_class_name("nyiso", "load_forecast") == "NyisoLoadForecastCollector"


def test_generate_dgroup(transformer):
    """Test dgroup generation."""
    assert transformer._generate_dgroup("MISO", "energy_pricing") == "miso_energy_pricing"
    assert transformer._generate_dgroup("NYISO", "load forecast") == "nyiso_load_forecast"


def test_generate_filename(transformer):
    """Test filename generation."""
    assert transformer._generate_filename("MISO", "energy_pricing") == "main.py"
    assert transformer._generate_filename("nyiso", "load") == "main.py"


def test_generate_auth_env_var(transformer):
    """Test auth env var generation."""
    assert transformer._generate_auth_env_var("MISO") == "MISO_API_KEY"
    assert transformer._generate_auth_env_var("ny_iso") == "NY_ISO_API_KEY"


# ============================================================================
# AUTH METHOD TESTS
# ============================================================================

def test_extract_auth_method_api_key(transformer, sample_ba_spec):
    """Test API key auth method extraction."""
    result = transformer.transform(sample_ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["auth_method"] == "API_KEY"


def test_extract_auth_method_bearer(transformer, sample_ba_spec):
    """Test Bearer token auth method extraction."""
    sample_ba_spec["authentication"]["method"] = "BEARER_TOKEN"

    result = transformer.transform(sample_ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["auth_method"] == "BEARER_TOKEN"


def test_extract_auth_method_none(transformer, sample_ba_spec):
    """Test no auth method extraction."""
    sample_ba_spec["authentication"]["required"] = False
    sample_ba_spec["authentication"]["method"] = "NONE"

    result = transformer.transform(sample_ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["auth_required"] is False
    assert template_vars["auth_method"] == "NONE"


# ============================================================================
# COLLECTION METHOD TESTS
# ============================================================================

def test_determine_collection_method_api(transformer, sample_ba_spec):
    """Test API collection method determination."""
    result = transformer.transform(sample_ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["collection_method"] == "HTTP_REST_API"


def test_determine_collection_method_ftp(transformer, sample_ba_spec):
    """Test FTP collection method determination."""
    sample_ba_spec["source_type"] = "FTP"

    result = transformer.transform(sample_ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["collection_method"] == "FTP_SFTP"


def test_determine_collection_method_website(transformer, sample_ba_spec):
    """Test website collection method determination."""
    sample_ba_spec["source_type"] = "WEBSITE"

    result = transformer.transform(sample_ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["collection_method"] == "WEBSITE_PARSER"


# ============================================================================
# VALIDATION TESTS
# ============================================================================

def test_validate_success(transformer, sample_ba_spec):
    """Test successful validation."""
    result = transformer.transform(sample_ba_spec)
    errors = transformer.validate(result)

    assert len(errors) == 0


def test_validate_missing_source(transformer, sample_ba_spec):
    """Test validation with missing source uses default."""
    del sample_ba_spec["source"]

    result = transformer.transform(sample_ba_spec)

    # Should use "Unknown" as default, validation passes
    assert result["template_vars"]["source"] == "Unknown"

    errors = transformer.validate(result)
    # No error because default is provided
    assert len(errors) == 0


def test_validate_invalid_collection_method(transformer, sample_ba_spec):
    """Test validation with invalid collection method."""
    sample_ba_spec["source_type"] = "INVALID"

    result = transformer.transform(sample_ba_spec)
    # Force invalid collection method
    result["template_vars"]["collection_method"] = "INVALID_METHOD"

    errors = transformer.validate(result)

    assert any("collection_method" in err for err in errors)


def test_validate_missing_endpoints_for_api(transformer, sample_ba_spec):
    """Test validation with missing endpoints for API scraper."""
    sample_ba_spec["endpoints"] = []

    result = transformer.transform(sample_ba_spec)
    errors = transformer.validate(result)

    assert any("endpoint" in err.lower() for err in errors)


def test_validate_missing_auth_header_when_required(transformer, sample_ba_spec):
    """Test validation with missing auth header when auth required."""
    del sample_ba_spec["authentication"]["header_name"]

    result = transformer.transform(sample_ba_spec)
    # Force auth_header_name to empty
    result["template_vars"]["auth_header_name"] = ""

    errors = transformer.validate(result)

    assert any("auth_header_name" in err for err in errors)


# ============================================================================
# DATA TYPE INFERENCE TESTS
# ============================================================================

def test_infer_data_type_from_executive_summary(transformer, sample_ba_spec):
    """Test data type inference from executive summary."""
    result = transformer.transform(sample_ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["data_type"] == "energy_pricing"


def test_infer_data_type_from_source_name(transformer):
    """Test data type inference from source name."""
    ba_spec = {
        "source": "Pricing API",
        "source_type": "API",
        "endpoints": [],
    }

    result = transformer.transform(ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["data_type"] == "pricing"


def test_infer_data_type_fallback(transformer):
    """Test data type inference fallback."""
    ba_spec = {
        "source": "Unknown Source",
        "source_type": "API",
        "endpoints": [],
    }

    result = transformer.transform(ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["data_type"] == "data"


# ============================================================================
# BASE URL EXTRACTION TESTS
# ============================================================================

def test_extract_base_url_from_executive_summary(transformer, sample_ba_spec):
    """Test base URL extraction from executive summary."""
    result = transformer.transform(sample_ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["api_base_url"] == "https://api.misoenergy.org"


def test_extract_base_url_from_endpoint(transformer):
    """Test base URL extraction from endpoint."""
    ba_spec = {
        "source": "Test",
        "source_type": "API",
        "endpoints": [
            {
                "full_url": "https://api.example.com/v1/data",
                "method": "GET",
            }
        ],
    }

    result = transformer.transform(ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["api_base_url"] == "https://api.example.com"


def test_extract_base_url_empty_when_missing(transformer):
    """Test base URL extraction when missing."""
    ba_spec = {
        "source": "Test",
        "source_type": "API",
        "endpoints": [],
    }

    result = transformer.transform(ba_spec)
    template_vars = result["template_vars"]

    assert template_vars["api_base_url"] == ""
