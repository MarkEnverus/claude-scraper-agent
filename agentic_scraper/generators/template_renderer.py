"""Jinja2 template rendering for scraper code generation.

This module provides a wrapper around Jinja2 for rendering scraper templates
with variables extracted from BA Analyzer specs.
"""

import ast
from pathlib import Path
from typing import Dict, Any, Optional

from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound, TemplateSyntaxError, StrictUndefined


class TemplateRenderer:
    """Render Jinja2 templates for scraper generation.

    This class handles loading and rendering Jinja2 templates with proper
    error handling and Python syntax validation.
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize template renderer.

        Args:
            template_dir: Directory containing Jinja2 templates.
                         Defaults to claude_scraper/templates/
        """
        if template_dir is None:
            # Default to templates/ directory relative to this file
            template_dir = Path(__file__).parent.parent / "templates"

        self.template_dir = Path(template_dir)

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            autoescape=False,  # No HTML escaping for Python code
            undefined=StrictUndefined,  # Raise error on undefined variables
        )

        # Add custom filters
        self._add_custom_filters()

    def _add_custom_filters(self) -> None:
        """Add custom Jinja2 filters for template rendering."""
        # Add snake_case filter
        def to_snake_case(text: str) -> str:
            """Convert text to snake_case."""
            import re
            text = re.sub(r'[\s\-]+', '_', text)
            text = re.sub(r'([a-z])([A-Z])', r'\1_\2', text)
            return text.lower()

        # Add camel_case filter
        def to_camel_case(text: str) -> str:
            """Convert text to CamelCase."""
            import re
            words = re.split(r'[\s\-_]+', text)
            return ''.join(word.capitalize() for word in words if word)

        # Add dedent filter for AI-generated code
        def dedent(text: str) -> str:
            """Remove leading whitespace from code blocks."""
            import textwrap
            return textwrap.dedent(text)

        self.env.filters['snake_case'] = to_snake_case
        self.env.filters['camel_case'] = to_camel_case
        self.env.filters['dedent'] = dedent

    def render(self, template_name: str, variables: Dict[str, Any]) -> str:
        """Render a template with variables.

        Args:
            template_name: Name of template file (e.g., "scraper_main.py.j2")
            variables: Dictionary of template variables

        Returns:
            Rendered template content as string

        Raises:
            TemplateNotFound: If template file doesn't exist
            TemplateSyntaxError: If template has syntax errors
            ValueError: If rendered Python code has syntax errors
        """
        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound:
            raise TemplateNotFound(
                f"Template not found: {template_name} in {self.template_dir}"
            )
        except TemplateSyntaxError as e:
            raise TemplateSyntaxError(
                f"Template syntax error in {template_name}: {e.message}",
                e.lineno,
                name=e.name,
                filename=e.filename,
            )

        # Render template
        rendered = template.render(**variables)

        # Validate Python syntax if it's a .py template
        if template_name.endswith('.py.j2'):
            self._validate_python_syntax(rendered, template_name)

        return rendered

    def _validate_python_syntax(self, code: str, template_name: str) -> None:
        """Validate that rendered code is syntactically valid Python.

        Args:
            code: Rendered Python code
            template_name: Name of template (for error messages)

        Raises:
            ValueError: If code has syntax errors
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise ValueError(
                f"Rendered template {template_name} produced invalid Python syntax:\n"
                f"Line {e.lineno}: {e.msg}\n"
                f"Code: {e.text}"
            )

    def render_scraper_main(self, variables: Dict[str, Any]) -> str:
        """Render main scraper file.

        Args:
            variables: Template variables from VariableTransformer

        Returns:
            Rendered scraper Python code
        """
        return self.render("scraper_main.py.j2", variables)

    def render_scraper_tests(self, variables: Dict[str, Any]) -> str:
        """Render test file for scraper.

        Args:
            variables: Template variables from VariableTransformer

        Returns:
            Rendered test Python code
        """
        return self.render("scraper_tests.py.j2", variables)

    def render_readme(self, variables: Dict[str, Any]) -> str:
        """Render README documentation file.

        Args:
            variables: Template variables from VariableTransformer

        Returns:
            Rendered README markdown
        """
        return self.render("scraper_readme.md.j2", variables)

    def render_integration_test(self, variables: Dict[str, Any]) -> str:
        """Render INTEGRATION_TEST.md documentation file.

        Args:
            variables: Template variables from VariableTransformer

        Returns:
            Rendered integration test markdown
        """
        return self.render("INTEGRATION_TEST.md.j2", variables)

    def list_templates(self) -> list[str]:
        """List all available templates in template directory.

        Returns:
            List of template filenames
        """
        return self.env.list_templates()

    def template_exists(self, template_name: str) -> bool:
        """Check if a template exists.

        Args:
            template_name: Name of template file

        Returns:
            True if template exists, False otherwise
        """
        try:
            self.env.get_template(template_name)
            return True
        except TemplateNotFound:
            return False

    def validate_variables(
        self,
        template_name: str,
        variables: Dict[str, Any],
    ) -> list[str]:
        """Validate that all required variables are present for a template.

        Args:
            template_name: Name of template file
            variables: Dictionary of variables to validate

        Returns:
            List of missing required variables (empty if all present)
        """
        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound:
            return [f"Template not found: {template_name}"]

        # Get undeclared variables from template
        from jinja2.meta import find_undeclared_variables

        source = self.env.loader.get_source(self.env, template_name)
        parsed = self.env.parse(source)
        undeclared = find_undeclared_variables(parsed)

        # Check which required variables are missing
        missing = []
        for var in undeclared:
            if var not in variables:
                missing.append(var)

        return missing
