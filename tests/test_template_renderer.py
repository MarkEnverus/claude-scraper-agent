"""Tests for TemplateRenderer."""

import ast
from pathlib import Path

import pytest
from jinja2 import TemplateNotFound, TemplateSyntaxError

from agentic_scraper.generators.template_renderer import TemplateRenderer


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def template_dir(tmp_path):
    """Create temporary template directory with test templates."""
    templates = tmp_path / "templates"
    templates.mkdir()

    # Create test templates
    (templates / "test_simple.j2").write_text("Hello {{ name }}!")

    (templates / "test_python.py.j2").write_text("""
def hello(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(hello("{{ name }}"))
""")

    (templates / "test_invalid_python.py.j2").write_text("""
def broken(
    # Missing closing paren
""")

    (templates / "test_with_loop.j2").write_text("""
{% for item in items %}
- {{ item }}
{% endfor %}
""")

    return templates


@pytest.fixture
def renderer(template_dir):
    """Create TemplateRenderer with test templates."""
    return TemplateRenderer(template_dir)


@pytest.fixture
def sample_template_vars():
    """Sample template variables."""
    return {
        "source": "MISO",
        "source_lower": "miso",
        "source_upper": "MISO",
        "source_snake": "miso",
        "data_type": "energy_pricing",
        "data_type_lower": "energy_pricing",
        "data_type_snake": "energy_pricing",
        "class_name": "MisoEnergyPricingCollector",
        "dgroup": "miso_energy_pricing",
        "filename": "scraper_miso_energy_pricing_http.py",
        "scraper_version": "2.0.0",
        "infrastructure_version": "1.13.0",
        "generated_date": "2025-12-19",
        "generator_agent": "hybrid-template-baml",
        "collection_method": "HTTP_REST_API",
        "scraper_type": "http-rest-api",
        "api_base_url": "https://api.misoenergy.org",
        "endpoints": [
            {
                "name": "da_exante_lmp",
                "display_name": "Day-Ahead Ex-Ante LMP",
                "path": "/api/v1/da/{date}/exante/lmp",
                "method": "GET",
                "params": {},
                "auth_required": True,
                "description": "Day-ahead ex-ante LMP data",
            }
        ],
        "auth_required": True,
        "auth_method": "API_KEY",
        "auth_header_name": "Ocp-Apim-Subscription-Key",
        "auth_env_var": "MISO_API_KEY",
        "data_format": "json",
        "output_format": "json",
        "update_frequency": "hourly",
        "historical_support": True,
        "timeout_seconds": 30,
        "retry_attempts": 3,
        "base_imports": [],
        "init_code": "# Custom init code",
        "generate_candidates_code": "# Generate candidates",
        "collect_content_code": "# Collect content code",
        "validate_content_code": "# Validate content code",
    }


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================

def test_renderer_initialization(renderer):
    """Test renderer initializes correctly."""
    assert renderer.template_dir.exists()
    assert renderer.env is not None


def test_renderer_default_template_dir():
    """Test renderer uses default template directory."""
    renderer = TemplateRenderer()
    expected_dir = Path(__file__).parent.parent / "claude_scraper" / "templates"

    # May not exist yet in test environment, but should be the correct path
    assert renderer.template_dir == expected_dir


# ============================================================================
# RENDERING TESTS
# ============================================================================

def test_render_simple_template(renderer):
    """Test rendering simple template."""
    result = renderer.render("test_simple.j2", {"name": "World"})
    assert result == "Hello World!"


def test_render_python_template(renderer):
    """Test rendering Python template."""
    result = renderer.render("test_python.py.j2", {"name": "Alice"})

    assert "def hello(name: str) -> str:" in result
    assert 'print(hello("Alice"))' in result


def test_render_with_loop(renderer):
    """Test rendering template with loop."""
    result = renderer.render("test_with_loop.j2", {"items": ["A", "B", "C"]})

    assert "- A" in result
    assert "- B" in result
    assert "- C" in result


def test_render_template_not_found(renderer):
    """Test rendering non-existent template."""
    with pytest.raises(TemplateNotFound):
        renderer.render("nonexistent.j2", {})


def test_render_validates_python_syntax(renderer):
    """Test renderer validates Python syntax."""
    with pytest.raises(ValueError, match="invalid Python syntax"):
        renderer.render("test_invalid_python.py.j2", {"name": "Test"})


# ============================================================================
# CUSTOM FILTERS TESTS
# ============================================================================

def test_snake_case_filter(template_dir):
    """Test snake_case custom filter."""
    (template_dir / "test_filter.j2").write_text("{{ text | snake_case }}")

    renderer = TemplateRenderer(template_dir)

    assert renderer.render("test_filter.j2", {"text": "HelloWorld"}) == "hello_world"
    assert renderer.render("test_filter.j2", {"text": "MISO Energy"}) == "miso_energy"


def test_camel_case_filter(template_dir):
    """Test camel_case custom filter."""
    (template_dir / "test_filter.j2").write_text("{{ text | camel_case }}")

    renderer = TemplateRenderer(template_dir)

    assert renderer.render("test_filter.j2", {"text": "hello_world"}) == "HelloWorld"
    assert renderer.render("test_filter.j2", {"text": "miso energy"}) == "MisoEnergy"


# ============================================================================
# CONVENIENCE METHOD TESTS
# ============================================================================

def test_render_scraper_main(sample_template_vars):
    """Test render_scraper_main convenience method."""
    # Use actual templates directory
    renderer = TemplateRenderer()

    # This will fail if templates don't exist yet, but tests the interface
    try:
        result = renderer.render_scraper_main(sample_template_vars)
        assert isinstance(result, str)
        assert len(result) > 0
    except TemplateNotFound:
        # Templates not created yet in test environment
        pytest.skip("Templates not available yet")


def test_render_scraper_tests(sample_template_vars):
    """Test render_scraper_tests convenience method."""
    renderer = TemplateRenderer()

    try:
        result = renderer.render_scraper_tests(sample_template_vars)
        assert isinstance(result, str)
        assert len(result) > 0
    except TemplateNotFound:
        pytest.skip("Templates not available yet")


def test_render_readme(sample_template_vars):
    """Test render_readme convenience method."""
    renderer = TemplateRenderer()

    try:
        result = renderer.render_readme(sample_template_vars)
        assert isinstance(result, str)
        assert len(result) > 0
    except TemplateNotFound:
        pytest.skip("Templates not available yet")


# ============================================================================
# UTILITY METHOD TESTS
# ============================================================================

def test_list_templates(renderer):
    """Test listing available templates."""
    templates = renderer.list_templates()

    assert "test_simple.j2" in templates
    assert "test_python.py.j2" in templates
    assert "test_with_loop.j2" in templates


def test_template_exists(renderer):
    """Test checking template existence."""
    assert renderer.template_exists("test_simple.j2") is True
    assert renderer.template_exists("nonexistent.j2") is False


def test_validate_variables(renderer):
    """Test variable validation."""
    # Create template with specific variables
    template_path = renderer.template_dir / "test_vars.j2"
    template_path.write_text("{{ required_var }} and {{ another_var }}")

    # Missing variables
    missing = renderer.validate_variables("test_vars.j2", {})
    assert "required_var" in missing
    assert "another_var" in missing

    # All variables present
    missing = renderer.validate_variables(
        "test_vars.j2",
        {"required_var": "value1", "another_var": "value2"},
    )
    assert len(missing) == 0


def test_validate_variables_template_not_found(renderer):
    """Test variable validation with non-existent template."""
    missing = renderer.validate_variables("nonexistent.j2", {})
    assert "Template not found" in missing[0]


# ============================================================================
# PYTHON SYNTAX VALIDATION TESTS
# ============================================================================

def test_python_syntax_validation_valid_code(renderer, template_dir):
    """Test Python syntax validation with valid code."""
    (template_dir / "valid.py.j2").write_text("""
def add(a: int, b: int) -> int:
    return a + b
""")

    result = renderer.render("valid.py.j2", {})

    # Should not raise, and code should be valid
    ast.parse(result)


def test_python_syntax_validation_invalid_code(renderer, template_dir):
    """Test Python syntax validation with invalid code."""
    (template_dir / "invalid.py.j2").write_text("""
def broken(
    # Missing closing paren
""")

    with pytest.raises(ValueError, match="invalid Python syntax"):
        renderer.render("invalid.py.j2", {})


def test_non_python_templates_not_validated(renderer):
    """Test non-.py templates are not syntax validated."""
    # This should not raise even though it's invalid Python
    result = renderer.render("test_simple.j2", {"name": "Test"})
    assert result == "Hello Test!"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

def test_render_handles_missing_variables(renderer, template_dir):
    """Test rendering with missing variables."""
    (template_dir / "test_missing.j2").write_text("{{ missing_var }}")

    # Should raise due to strict undefined
    with pytest.raises(Exception):  # UndefinedError or similar
        renderer.render("test_missing.j2", {})


def test_render_with_complex_variables(renderer, template_dir):
    """Test rendering with complex nested variables."""
    (template_dir / "test_complex.j2").write_text("""
{{ data.nested.value }}
{% for item in data.item_list %}
- {{ item.name }}: {{ item.value }}
{% endfor %}
""")

    variables = {
        "data": {
            "nested": {"value": "nested_value"},
            "item_list": [
                {"name": "Item1", "value": "Value1"},
                {"name": "Item2", "value": "Value2"},
            ],
        }
    }

    result = renderer.render("test_complex.j2", variables)

    assert "nested_value" in result
    assert "Item1: Value1" in result
    assert "Item2: Value2" in result


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_full_render_workflow(renderer, template_dir, sample_template_vars):
    """Test full rendering workflow."""
    # Update sample vars to have valid Python code
    sample_template_vars["collect_content_code"] = "# Collect content code\npass"

    # Create a realistic template
    (template_dir / "scraper.py.j2").write_text("""
\"\"\"{{ source }} {{ data_type }} collector.\"\"\"

class {{ class_name }}:
    def __init__(self):
        self.base_url = "{{ api_base_url }}"
        self.dgroup = "{{ dgroup }}"

    def collect(self):
        {{ collect_content_code | indent(8) }}
""")

    result = renderer.render("scraper.py.j2", sample_template_vars)

    # Check template variables were substituted
    assert "MISO energy_pricing collector" in result
    assert "class MisoEnergyPricingCollector:" in result
    assert 'self.base_url = "https://api.misoenergy.org"' in result
    assert 'self.dgroup = "miso_energy_pricing"' in result
    assert "# Collect content code" in result

    # Check Python syntax is valid
    ast.parse(result)
