"""Hybrid scraper generator combining Jinja2 templates with LLM AI code generation.

This module orchestrates scraper generation using:
- VariableTransformer: Transforms BA Analyzer specs to template variables
- LLM Provider: Generates complex code (collect_content, validate_content, auth)
- TemplateRenderer: Renders Jinja2 templates with AI-generated code
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field

from agentic_scraper.generators.variable_transformer import VariableTransformer
from agentic_scraper.generators.template_renderer import TemplateRenderer
from agentic_scraper.infrastructure_manager import InfrastructureManager
from agentic_scraper.validators import (
    ValidationConfig,
    InterfaceExtractor,
    CodeValidator,
    ValidationLevel,
)
from agentic_scraper.prompts.scraper_generator import (
    generate_collect_content_prompt,
    generate_validate_content_prompt,
    generate_complex_auth_prompt,
)
from agentic_scraper.llm.factory import LLMFactory

logger = logging.getLogger(__name__)


class GeneratedCode(BaseModel):
    """Generated code from LLM."""
    code: str
    imports: list[str] = Field(default_factory=list)
    notes: str = ""


@dataclass
class GeneratedFiles:
    """Paths to generated scraper files."""
    scraper_path: Path
    test_path: Path
    readme_path: Path
    metadata: Dict[str, Any]


class HybridGenerator:
    """Generate scrapers using hybrid template + AI approach.

    This generator combines:
    1. Jinja2 templates for structural boilerplate
    2. LLM provider for complex logic generation
    3. Variable transformation from BA Analyzer specs
    """

    def __init__(
        self,
        factory: LLMFactory,
        template_dir: Optional[Path] = None,
        validation_config: Optional[ValidationConfig] = None,
    ):
        """Initialize hybrid generator.

        Args:
            factory: LLMFactory for creating reasoning model (code generation)
            template_dir: Directory containing Jinja2 templates
            validation_config: Validation configuration (None = from environment)
        """
        self.factory = factory
        self.llm = factory.create_reasoning_model()  # Haiku with extended thinking for code quality
        self.transformer = VariableTransformer()
        self.renderer = TemplateRenderer(template_dir)
        self.infra_manager = InfrastructureManager()

        # Initialize validation
        self.validation_config = validation_config or ValidationConfig.from_environment()
        if self.validation_config.is_enabled():
            try:
                extractor = InterfaceExtractor()
                self.interface = extractor.extract_base_collector_interface()
                self.validator = CodeValidator(self.interface)
            except Exception as e:
                # If validation setup fails, log warning but don't block
                print(f"Warning: Validation setup failed: {e}. Validation disabled.")
                self.validation_config = ValidationConfig.disabled()
                self.validator = None
        else:
            self.validator = None

    def _ensure_sourcing_commons(self) -> bool:
        """Ensure sourcing/commons/ exists with all commons files.

        Copies files from /commons/ to sourcing/commons/ if they don't exist
        or are outdated.

        Returns:
            True if sourcing/commons/ is ready, False otherwise
        """
        import shutil
        from pathlib import Path

        commons_src = Path("commons")
        commons_dst = Path("sourcing/commons")

        if not commons_src.exists():
            raise FileNotFoundError(
                "commons/ directory not found. Did you rename infrastructure/ to commons/?"
            )

        # Create sourcing/commons/ if doesn't exist
        commons_dst.mkdir(parents=True, exist_ok=True)

        # Copy all commons files
        commons_files = [
            "collection_framework.py",
            "hash_registry.py",
            "s3_utils.py",
            "kafka_utils.py",
            "logging_json.py",
        ]

        for filename in commons_files:
            src_file = commons_src / filename
            dst_file = commons_dst / filename

            if not src_file.exists():
                print(f"Warning: Commons file not found: {src_file}")
                continue

            # Copy file (overwrite if exists to ensure up-to-date)
            shutil.copy2(src_file, dst_file)

        # Create __init__.py if doesn't exist
        init_file = commons_dst / "__init__.py"
        if not init_file.exists():
            init_file.write_text(
                '"""Sourcing commons - infrastructure utilities for data collectors."""\n',
                encoding="utf-8"
            )

        return True

    async def generate_scraper(
        self,
        ba_spec: Dict[str, Any],
        output_dir: Path,
    ) -> GeneratedFiles:
        """Generate complete scraper from BA Analyzer spec.

        Args:
            ba_spec: Validated data source spec from BA Analyzer
            output_dir: Directory to write generated files

        Returns:
            GeneratedFiles with paths to created files

        Raises:
            ValueError: If spec validation fails
            RuntimeError: If code generation fails
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 0: Ensure sourcing/commons/ exists and is up-to-date
        if not self._ensure_sourcing_commons():
            raise RuntimeError("Failed to initialize sourcing/commons/")

        # Step 1: Validate BA spec
        validation_errors = self.validate_ba_spec(ba_spec)
        if validation_errors:
            raise ValueError(
                f"BA spec validation failed:\n" + "\n".join(f"  - {err}" for err in validation_errors)
            )

        # Step 2: Transform BA spec to template variables
        transformed = self.transformer.transform(ba_spec)
        template_vars = transformed["template_vars"]
        baml_inputs = transformed["baml_inputs"]

        # Step 3: Validate transformed variables
        errors = self.transformer.validate(transformed)
        if errors:
            raise ValueError(
                f"Variable transformation validation failed:\n" + "\n".join(errors)
            )

        # Step 4: Generate AI code via LLM provider
        ai_code = await self._generate_ai_code(ba_spec, baml_inputs, template_vars)

        # Add AI-generated code to template variables
        template_vars["init_code"] = ai_code["init_code"]
        template_vars["collect_content_code"] = ai_code["collect_content_code"]
        template_vars["validate_content_code"] = ai_code["validate_content_code"]

        # Step 5: Render templates
        scraper_code = self.renderer.render_scraper_main(template_vars)
        test_code = self.renderer.render_scraper_tests(template_vars)
        readme_content = self.renderer.render_readme(template_vars)
        integration_test_content = self.renderer.render_integration_test(template_vars)

        # Step 5.5: Validate generated code (if enabled)
        if self.validator and self.validation_config.is_enabled():
            validation_report = self.validator.validate_code(scraper_code)

            if validation_report.has_critical_errors():
                critical_errors = validation_report.get_critical_errors()
                error_summary = "\n".join(
                    f"  [{e.category}] {e.message}" for e in critical_errors
                )

                if self.validation_config.strict_mode:
                    raise RuntimeError(
                        f"Generated code has {len(critical_errors)} critical interface violations:\n"
                        f"{error_summary}\n\n"
                        f"The generated code does not conform to BaseCollector interface.\n"
                        f"This usually means LLM prompts need updating or templates have errors."
                    )
                else:
                    print(f"⚠️  Warning: Generated code has {len(critical_errors)} critical errors:")
                    print(error_summary)

            # Log warnings (non-blocking)
            warnings = validation_report.get_warnings()
            if warnings:
                print(f"ℹ️  Generated code has {len(warnings)} warnings (non-critical)")
                for warning in warnings[:5]:  # Show first 5
                    print(f"  [{warning.category}] {warning.message}")

        # Step 6: Create directory structure
        # output_dir should already be sourcing/scraping/{datasource}/{dataset}/
        scraper_dir = output_dir  # No nesting - use directly
        tests_dir = scraper_dir / "tests"
        fixtures_dir = tests_dir / "fixtures"

        scraper_dir.mkdir(parents=True, exist_ok=True)
        tests_dir.mkdir(exist_ok=True)
        fixtures_dir.mkdir(exist_ok=True)

        # Step 7: Write scraper files
        scraper_filename = template_vars["filename"]
        scraper_path = scraper_dir / scraper_filename
        test_path = tests_dir / "test_main.py"
        readme_path = scraper_dir / "README.md"
        integration_test_path = scraper_dir / "INTEGRATION_TEST.md"

        scraper_path.write_text(scraper_code, encoding="utf-8")
        test_path.write_text(test_code, encoding="utf-8")
        readme_path.write_text(readme_content, encoding="utf-8")
        integration_test_path.write_text(integration_test_content, encoding="utf-8")

        # Step 7.5: Create package structure
        (scraper_dir / "__init__.py").write_text(
            f'"""Generated scraper for {template_vars["source"]} - {template_vars.get("dataset", "data")} dataset."""\n',
            encoding="utf-8"
        )
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")

        # Step 8: Generate project files (skipped for sourcing/ scrapers)
        # pyproject.toml and .gitignore only needed for standalone scrapers
        # For sourcing/ scrapers, these are managed at the repository root
        # if standalone_mode:
        #     if not self.infra_manager.generate_pyproject_toml(output_dir, source_snake):
        #         pass
        #     if not self.infra_manager.generate_gitignore(output_dir):
        #         pass

        # Step 9: Return generated files
        metadata = {
            "source": template_vars["source"],
            "data_type": template_vars["data_type"],
            "dgroup": template_vars["dgroup"],
            "collection_method": template_vars["collection_method"],
            "generated_date": template_vars["generated_date"],
            "infrastructure_version": template_vars["infrastructure_version"],
            "ai_generated": True,
        }

        return GeneratedFiles(
            scraper_path=scraper_path,
            test_path=test_path,
            readme_path=readme_path,
            metadata=metadata,
        )

    async def _generate_ai_code(
        self,
        ba_spec: Dict[str, Any],
        baml_inputs: Dict[str, Any],
        template_vars: Dict[str, Any],
    ) -> Dict[str, str]:
        """Generate AI code using LLM provider.

        Args:
            ba_spec: Original BA Analyzer spec
            baml_inputs: Extracted inputs for LLM prompts
            template_vars: Template variables (for context)

        Returns:
            Dictionary with generated code:
                - init_code: Custom initialization code
                - collect_content_code: collect_content() method body
                - validate_content_code: validate_content() method body
        """
        ba_spec_json = json.dumps(ba_spec, indent=2)

        # Extract endpoint for AI generation
        if not baml_inputs["endpoints"]:
            raise ValueError("No endpoints found in BA spec")

        # Should be single endpoint after orchestrator split
        endpoint_id = baml_inputs["endpoints"][0].get("endpoint_id", "")
        endpoint_name = baml_inputs["endpoints"][0].get("name", "unknown")

        logger.info(f"Generating AI code for endpoint: {endpoint_name} ({endpoint_id})")

        # Create prompts
        collect_prompt = generate_collect_content_prompt(
            ba_spec_json=ba_spec_json,
            endpoint=endpoint_id,
            auth_method=baml_inputs["auth_method"],
            data_format=template_vars["data_format"],
            timeout_seconds=template_vars["timeout_seconds"],
            retry_attempts=template_vars["retry_attempts"]
        )

        validate_prompt = generate_validate_content_prompt(
            ba_spec_json=ba_spec_json,
            endpoint=endpoint_id,
            data_format=template_vars["data_format"],
            validation_requirements=json.dumps({
                "data_format": template_vars["data_format"],
                "update_frequency": baml_inputs["update_frequency"],
                "historical_support": baml_inputs["historical_support"],
            })
        )

        # Build tasks list for parallel execution
        # Use asyncio.to_thread() since factory.invoke_structured is synchronous
        tasks = [
            asyncio.to_thread(
                self.factory.invoke_structured,
                self.llm,
                collect_prompt,
                GeneratedCode,
                system="You are an expert Python developer generating production-ready scraper code."
            ),
            asyncio.to_thread(
                self.factory.invoke_structured,
                self.llm,
                validate_prompt,
                GeneratedCode,
                system="You are an expert Python developer generating production-ready data validation code."
            )
        ]

        # Add complex auth if needed
        auth_method = baml_inputs["auth_method"]
        if auth_method in ["OAUTH", "SAML", "MFA", "COOKIE"]:
            auth_prompt = generate_complex_auth_prompt(
                auth_spec=json.dumps(baml_inputs),
                auth_method=auth_method,
                registration_url=baml_inputs.get("registration_url", "")
            )
            tasks.append(
                asyncio.to_thread(
                    self.factory.invoke_structured,
                    self.llm,
                    auth_prompt,
                    GeneratedCode,
                    system="You are an expert Python developer generating authentication setup code."
                )
            )
        else:
            # No complex auth needed - use dummy
            tasks.append(self._dummy_init_code())

        # Execute all LLM calls in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise RuntimeError(
                    f"LLM code generation failed (task {i}): {result}"
                )

        # Extract code from GeneratedCode objects
        collect_code = results[0]
        validate_code = results[1]
        init_code = results[2]

        return {
            "collect_content_code": collect_code.code,
            "validate_content_code": validate_code.code,
            "init_code": init_code.code,
        }

    async def _dummy_init_code(self) -> GeneratedCode:
        """Return empty init code for non-complex auth."""
        return GeneratedCode(
            code="# Standard authentication configured in __init__",
            imports=[],
            notes="No complex authentication required",
        )

    def generate_scraper_sync(
        self,
        ba_spec: Dict[str, Any],
        output_dir: Path,
    ) -> GeneratedFiles:
        """Synchronous wrapper for generate_scraper.

        Args:
            ba_spec: Validated data source spec
            output_dir: Directory for generated files

        Returns:
            GeneratedFiles with paths
        """
        return asyncio.run(
            self.generate_scraper(ba_spec, output_dir)
        )

    def validate_ba_spec(self, ba_spec: Dict[str, Any]) -> list[str]:
        """Validate BA Analyzer spec before generation.

        Args:
            ba_spec: BA Analyzer validated spec

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required top-level fields
        required_fields = ["source", "source_type", "endpoints"]
        for field in required_fields:
            if field not in ba_spec:
                errors.append(f"Missing required field: {field}")

        # Validate source_type
        valid_types = ["API", "FTP", "WEBSITE", "EMAIL"]
        source_type = ba_spec.get("source_type", "").upper()
        if source_type not in valid_types:
            errors.append(
                f"Invalid source_type: {source_type}. Must be one of {valid_types}"
            )

        # Validate endpoints
        if "endpoints" in ba_spec:
            endpoints = ba_spec["endpoints"]
            if not isinstance(endpoints, list):
                errors.append("endpoints must be a list")
            elif len(endpoints) == 0:
                errors.append("At least one endpoint required")

        return errors
