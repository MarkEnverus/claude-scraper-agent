"""Validate generated code against BaseCollector interface."""

import ast
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set
from pathlib import Path

from .interface_extractor import InterfaceDefinition


class ValidationLevel(Enum):
    """Validation error severity levels."""

    CRITICAL = "CRITICAL"  # Blocks generation
    WARNING = "WARNING"  # Allows generation
    INFO = "INFO"  # Informational only


@dataclass
class ValidationError:
    """Single validation error or warning.

    Attributes:
        level: Error severity level
        category: Error category (return_type, import, method_signature, etc.)
        message: Human-readable error message
        line_number: Line number where error occurs
        code_snippet: Relevant code snippet
        fix_suggestion: Suggested fix for the error
    """

    level: ValidationLevel
    category: str
    message: str
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    fix_suggestion: Optional[str] = None


@dataclass
class ValidationReport:
    """Complete validation report.

    Attributes:
        is_valid: True if no critical errors
        errors: List of all validation errors/warnings
        validation_time_ms: Time taken to validate (milliseconds)
    """

    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    validation_time_ms: float = 0.0

    def has_critical_errors(self) -> bool:
        """Check if report contains critical errors."""
        return any(e.level == ValidationLevel.CRITICAL for e in self.errors)

    def get_critical_errors(self) -> List[ValidationError]:
        """Get only critical errors."""
        return [e for e in self.errors if e.level == ValidationLevel.CRITICAL]

    def get_warnings(self) -> List[ValidationError]:
        """Get only warnings."""
        return [e for e in self.errors if e.level == ValidationLevel.WARNING]

    def format_errors(self) -> str:
        """Format errors for display."""
        if not self.errors:
            return "✓ No errors found"

        lines = []
        critical = self.get_critical_errors()
        warnings = self.get_warnings()

        if critical:
            lines.append(f"CRITICAL ERRORS ({len(critical)}):")
            for err in critical:
                lines.append(f"  [{err.category}] {err.message}")
                if err.fix_suggestion:
                    lines.append(f"    Fix: {err.fix_suggestion}")

        if warnings:
            lines.append(f"\nWARNINGS ({len(warnings)}):")
            for warn in warnings:
                lines.append(f"  [{warn.category}] {warn.message}")

        return "\n".join(lines)


class CodeValidator:
    """Validate generated scraper code against BaseCollector interface."""

    def __init__(self, interface: InterfaceDefinition):
        """Initialize validator.

        Args:
            interface: InterfaceDefinition to validate against
        """
        self.interface = interface

    def validate_code(self, code: str, file_path: Optional[str] = None) -> ValidationReport:
        """Validate generated code.

        Args:
            code: Generated Python code
            file_path: Optional file path for context

        Returns:
            ValidationReport with all errors/warnings
        """
        errors: List[ValidationError] = []

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return ValidationReport(
                is_valid=False,
                errors=[
                    ValidationError(
                        level=ValidationLevel.CRITICAL,
                        category="syntax_error",
                        message=f"Syntax error: {e}",
                        line_number=e.lineno,
                        fix_suggestion="Check Python syntax - code must be valid Python",
                    )
                ],
            )

        # Find the collector class
        collector_class = self._find_collector_class(tree)
        if not collector_class:
            errors.append(
                ValidationError(
                    level=ValidationLevel.CRITICAL,
                    category="class_not_found",
                    message="Could not find collector class inheriting from BaseCollector",
                    fix_suggestion="Ensure class inherits from BaseCollector",
                )
            )
            return ValidationReport(is_valid=False, errors=errors)

        # Validate collect_content method
        errors.extend(self._validate_collect_content(collector_class, code))

        # Validate validate_content method
        errors.extend(self._validate_validate_content(collector_class, code))

        # Validate generate_candidates method
        errors.extend(self._validate_generate_candidates(collector_class, code))

        # Validate imports
        errors.extend(self._validate_imports(tree))

        # Validate DownloadCandidate usage
        errors.extend(self._validate_download_candidate_usage(tree, code))

        # Check for critical errors
        has_critical = any(e.level == ValidationLevel.CRITICAL for e in errors)

        return ValidationReport(is_valid=not has_critical, errors=errors)

    def _find_collector_class(self, tree: ast.AST) -> Optional[ast.ClassDef]:
        """Find the collector class in the AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if inherits from BaseCollector
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "BaseCollector":
                        return node
        return None

    def _validate_collect_content(
        self, class_node: ast.ClassDef, code: str
    ) -> List[ValidationError]:
        """Validate collect_content method."""
        errors = []

        # Find method
        method = self._find_method(class_node, "collect_content")
        if not method:
            errors.append(
                ValidationError(
                    level=ValidationLevel.CRITICAL,
                    category="missing_method",
                    message="collect_content() method not found",
                    fix_suggestion="Implement collect_content(self, candidate: DownloadCandidate) -> bytes",
                )
            )
            return errors

        # Check signature
        expected_params = ["self", "candidate"]
        actual_params = [arg.arg for arg in method.args.args]

        if actual_params != expected_params:
            errors.append(
                ValidationError(
                    level=ValidationLevel.CRITICAL,
                    category="method_signature",
                    message=f"collect_content() has wrong parameters: {actual_params}, expected {expected_params}",
                    line_number=method.lineno,
                    fix_suggestion="Change signature to: def collect_content(self, candidate: DownloadCandidate) -> bytes",
                )
            )

        # Check return type annotation
        if method.returns:
            return_type = ast.unparse(method.returns)
            if return_type != "bytes":
                errors.append(
                    ValidationError(
                        level=ValidationLevel.CRITICAL,
                        category="return_type",
                        message=f"collect_content() returns {return_type}, expected bytes",
                        line_number=method.lineno,
                        fix_suggestion="Change return type to 'bytes' and return response.content (raw bytes)",
                    )
                )
        else:
            errors.append(
                ValidationError(
                    level=ValidationLevel.WARNING,
                    category="missing_type_annotation",
                    message="collect_content() missing return type annotation",
                    line_number=method.lineno,
                    fix_suggestion="Add '-> bytes' return type annotation",
                )
            )

        # Check for wrong return types in method body
        for node in ast.walk(method):
            if isinstance(node, ast.Return) and node.value:
                # Check if returning a Call (like CollectedContent(...))
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Name):
                        func_name = node.value.func.id
                        if func_name in ["CollectedContent", "ValidationResult"]:
                            errors.append(
                                ValidationError(
                                    level=ValidationLevel.CRITICAL,
                                    category="wrong_return_value",
                                    message=f"collect_content() returns {func_name}(...) but should return bytes",
                                    line_number=node.lineno,
                                    fix_suggestion="Return response.content directly (which is bytes), not a wrapper object",
                                )
                            )

        return errors

    def _validate_validate_content(
        self, class_node: ast.ClassDef, code: str
    ) -> List[ValidationError]:
        """Validate validate_content method."""
        errors = []

        # Find method
        method = self._find_method(class_node, "validate_content")
        if not method:
            # validate_content is optional (has default implementation)
            return errors

        # Check signature
        expected_params = ["self", "content", "candidate"]
        actual_params = [arg.arg for arg in method.args.args]

        if actual_params != expected_params:
            errors.append(
                ValidationError(
                    level=ValidationLevel.CRITICAL,
                    category="method_signature",
                    message=f"validate_content() has wrong parameters: {actual_params}, expected {expected_params}",
                    line_number=method.lineno,
                    fix_suggestion="Change signature to: def validate_content(self, content: bytes, candidate: DownloadCandidate) -> bool",
                )
            )

        # Check return type annotation
        if method.returns:
            return_type = ast.unparse(method.returns)
            if return_type != "bool":
                errors.append(
                    ValidationError(
                        level=ValidationLevel.CRITICAL,
                        category="return_type",
                        message=f"validate_content() returns {return_type}, expected bool",
                        line_number=method.lineno,
                        fix_suggestion="Change return type to 'bool' and return True or False",
                    )
                )

        # Check for wrong return types in method body
        for node in ast.walk(method):
            if isinstance(node, ast.Return) and node.value:
                if isinstance(node.value, ast.Call):
                    if isinstance(node.value.func, ast.Name):
                        func_name = node.value.func.id
                        if func_name == "ValidationResult":
                            errors.append(
                                ValidationError(
                                    level=ValidationLevel.CRITICAL,
                                    category="wrong_return_value",
                                    message="validate_content() returns ValidationResult(...) but should return bool",
                                    line_number=node.lineno,
                                    fix_suggestion="Return True or False directly, not a ValidationResult object",
                                )
                            )

        return errors

    def _validate_generate_candidates(
        self, class_node: ast.ClassDef, code: str
    ) -> List[ValidationError]:
        """Validate generate_candidates method."""
        errors = []

        # Find method
        method = self._find_method(class_node, "generate_candidates")
        if not method:
            errors.append(
                ValidationError(
                    level=ValidationLevel.CRITICAL,
                    category="missing_method",
                    message="generate_candidates() method not found",
                    fix_suggestion="Implement generate_candidates() method",
                )
            )
            return errors

        # Check return type annotation
        if method.returns:
            return_type = ast.unparse(method.returns)
            if "List[DownloadCandidate]" not in return_type:
                errors.append(
                    ValidationError(
                        level=ValidationLevel.WARNING,
                        category="return_type",
                        message=f"generate_candidates() returns {return_type}, expected List[DownloadCandidate]",
                        line_number=method.lineno,
                        fix_suggestion="Change return type to 'List[DownloadCandidate]'",
                    )
                )

        return errors

    def _validate_imports(self, tree: ast.AST) -> List[ValidationError]:
        """Validate imports - check for non-existent types."""
        errors = []
        forbidden_imports = {"CollectedContent", "ValidationResult"}

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "collection_framework" in node.module:
                    for alias in node.names:
                        if alias.name in forbidden_imports:
                            errors.append(
                                ValidationError(
                                    level=ValidationLevel.CRITICAL,
                                    category="invalid_import",
                                    message=f"Trying to import {alias.name} but this type doesn't exist in collection_framework",
                                    line_number=node.lineno,
                                    fix_suggestion=f"Remove {alias.name} from imports - this type is not part of BaseCollector interface",
                                )
                            )

        return errors

    def _validate_download_candidate_usage(
        self, tree: ast.AST, code: str
    ) -> List[ValidationError]:
        """Validate DownloadCandidate instantiation uses correct fields."""
        errors = []

        # Expected fields
        expected_fields = {"identifier", "source_location", "metadata", "collection_params", "file_date"}
        wrong_fields = {"url", "expected_filename"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "DownloadCandidate":
                    # Check keyword arguments
                    used_fields = {kw.arg for kw in node.keywords if kw.arg}

                    # Check for wrong fields
                    for wrong_field in wrong_fields:
                        if wrong_field in used_fields:
                            errors.append(
                                ValidationError(
                                    level=ValidationLevel.CRITICAL,
                                    category="wrong_field",
                                    message=f"DownloadCandidate uses '{wrong_field}' field but should use 'identifier' or 'source_location'",
                                    line_number=node.lineno,
                                    fix_suggestion="Use 'identifier' instead of 'expected_filename' and 'source_location' instead of 'url'",
                                )
                            )

                    # Check for missing required fields
                    missing_fields = expected_fields - used_fields
                    if missing_fields:
                        errors.append(
                            ValidationError(
                                level=ValidationLevel.CRITICAL,
                                category="missing_field",
                                message=f"DownloadCandidate missing required fields: {missing_fields}",
                                line_number=node.lineno,
                                fix_suggestion=f"Add missing fields: {', '.join(missing_fields)}",
                            )
                        )

        return errors

    def _find_method(self, class_node: ast.ClassDef, method_name: str) -> Optional[ast.FunctionDef]:
        """Find a method in a class by name."""
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef) and item.name == method_name:
                return item
        return None
