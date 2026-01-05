"""Extract BaseCollector interface definition for validation and anchoring."""

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional


@dataclass
class MethodSignature:
    """Signature of a method in the interface.

    Attributes:
        name: Method name
        params: List of (parameter_name, type_annotation) tuples
        return_type: Return type annotation as string
        is_abstract: Whether method is abstract
        docstring: Method docstring
    """

    name: str
    params: List[Tuple[str, str]]
    return_type: str
    is_abstract: bool
    docstring: Optional[str] = None


@dataclass
class InterfaceDefinition:
    """Complete interface definition for BaseCollector.

    Attributes:
        class_name: Name of the interface class
        methods: Dictionary of method_name -> MethodSignature
        dataclasses: Dictionary of dataclass_name -> list of (field_name, type_annotation)
        source_code: Full source code of the interface
        file_path: Path to the source file
    """

    class_name: str
    methods: Dict[str, MethodSignature]
    dataclasses: Dict[str, List[Tuple[str, str]]]
    source_code: str
    file_path: str


class InterfaceExtractor:
    """Extract interface definitions from Python source files.

    This extractor uses AST parsing to extract method signatures, dataclass
    definitions, and other interface information from the BaseCollector class.
    """

    def __init__(self, infrastructure_path: Optional[str] = None):
        """Initialize extractor.

        Args:
            infrastructure_path: Path to infrastructure directory.
                               If None, will search relative to this file.
        """
        if infrastructure_path is None:
            # Default: look for sourcing/commons/ directory relative to project root
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent
            infrastructure_path = str(project_root / "sourcing" / "commons")

        self.infrastructure_path = Path(infrastructure_path)
        self.collection_framework_path = (
            self.infrastructure_path / "collection_framework.py"
        )

        if not self.collection_framework_path.exists():
            raise FileNotFoundError(
                f"collection_framework.py not found at {self.collection_framework_path}"
            )

    def extract_base_collector_interface(self) -> InterfaceDefinition:
        """Extract BaseCollector interface from collection_framework.py.

        Returns:
            InterfaceDefinition with complete interface information

        Raises:
            FileNotFoundError: If collection_framework.py doesn't exist
            ValueError: If BaseCollector class not found in file
        """
        # Read source file
        source_code = self.collection_framework_path.read_text()

        # Parse AST
        tree = ast.parse(source_code)

        # Find BaseCollector class
        base_collector_class = None
        download_candidate_class = None

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name == "BaseCollector":
                    base_collector_class = node
                elif node.name == "DownloadCandidate":
                    download_candidate_class = node

        if base_collector_class is None:
            raise ValueError("BaseCollector class not found in collection_framework.py")

        # Extract methods
        methods = {}
        for item in base_collector_class.body:
            if isinstance(item, ast.FunctionDef):
                method_sig = self._extract_method_signature(item)
                methods[method_sig.name] = method_sig

        # Extract dataclasses
        dataclasses = {}
        if download_candidate_class:
            dataclasses["DownloadCandidate"] = self._extract_dataclass_fields(
                download_candidate_class, source_code
            )

        return InterfaceDefinition(
            class_name="BaseCollector",
            methods=methods,
            dataclasses=dataclasses,
            source_code=source_code,
            file_path=str(self.collection_framework_path),
        )

    def _extract_method_signature(self, func_node: ast.FunctionDef) -> MethodSignature:
        """Extract method signature from AST function definition.

        Args:
            func_node: AST FunctionDef node

        Returns:
            MethodSignature with extracted information
        """
        # Extract parameters
        params = []
        for arg in func_node.args.args:
            if arg.arg == "self":
                continue  # Skip self parameter

            # Get type annotation
            type_annotation = "Any"
            if arg.annotation:
                type_annotation = ast.unparse(arg.annotation)

            params.append((arg.arg, type_annotation))

        # Extract return type
        return_type = "None"
        if func_node.returns:
            return_type = ast.unparse(func_node.returns)

        # Check if abstract
        is_abstract = False
        for decorator in func_node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "abstractmethod":
                is_abstract = True

        # Extract docstring
        docstring = ast.get_docstring(func_node)

        return MethodSignature(
            name=func_node.name,
            params=params,
            return_type=return_type,
            is_abstract=is_abstract,
            docstring=docstring,
        )

    def _extract_dataclass_fields(
        self, class_node: ast.ClassDef, source_code: str
    ) -> List[Tuple[str, str]]:
        """Extract fields from a dataclass.

        Args:
            class_node: AST ClassDef node
            source_code: Full source code for context

        Returns:
            List of (field_name, type_annotation) tuples
        """
        fields = []

        for item in class_node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field_name = item.target.id
                type_annotation = ast.unparse(item.annotation)
                fields.append((field_name, type_annotation))

        return fields

    def get_interface_summary(self, interface: InterfaceDefinition) -> str:
        """Generate a human-readable summary of the interface.

        Args:
            interface: InterfaceDefinition to summarize

        Returns:
            Formatted string with interface summary
        """
        lines = [
            f"Interface: {interface.class_name}",
            "",
            "Abstract Methods:",
        ]

        for name, method in interface.methods.items():
            if method.is_abstract:
                params_str = ", ".join(f"{p[0]}: {p[1]}" for p in method.params)
                lines.append(f"  def {name}({params_str}) -> {method.return_type}")

        lines.append("")
        lines.append("Dataclasses:")

        for dc_name, dc_fields in interface.dataclasses.items():
            lines.append(f"  {dc_name}:")
            for field_name, field_type in dc_fields:
                lines.append(f"    {field_name}: {field_type}")

        return "\n".join(lines)

    def get_reference_code(self, interface: InterfaceDefinition) -> str:
        """Get reference code snippet for BAML prompts.

        Extracts the essential parts of the interface for use in
        code generation prompts.

        Args:
            interface: InterfaceDefinition

        Returns:
            Clean Python code snippet showing the interface
        """
        lines = [
            "# BaseCollector Interface Contract",
            "# This is the EXACT interface your code must implement",
            "",
            "@dataclass",
            "class DownloadCandidate:",
        ]

        # Add DownloadCandidate fields
        if "DownloadCandidate" in interface.dataclasses:
            for field_name, field_type in interface.dataclasses["DownloadCandidate"]:
                lines.append(f"    {field_name}: {field_type}")

        lines.extend(
            [
                "",
                "class BaseCollector(ABC):",
                "    '''Abstract base for all collectors.'''",
                "",
            ]
        )

        # Add abstract methods only
        for name, method in sorted(interface.methods.items()):
            if method.is_abstract:
                params_str = ", ".join(f"{p[0]}: {p[1]}" for p in method.params)
                lines.append("    @abstractmethod")
                lines.append(f"    def {name}(self, {params_str}) -> {method.return_type}:")

                # Add simplified docstring
                if method.docstring:
                    first_line = method.docstring.split("\n")[0]
                    lines.append(f"        '''{first_line}'''")

                lines.append("        pass")
                lines.append("")

        return "\n".join(lines)
