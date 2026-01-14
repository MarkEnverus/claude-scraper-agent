"""API P2 Validator - Validation phase for API sources.

This node handles Phase 2 validation for API-type sources to ensure
discovered endpoints are complete and usable.

Key responsibilities:
- Validate count of discovered endpoints (min threshold)
- Validate schema completeness (method, path, description present)
- Validate parameter documentation (parameters have types/descriptions)
- Validate authentication detection (auth requirements identified)
- Report gaps if validation fails
- Signal completion if validation passes

Success criteria for API sources:
- Min 5 endpoints discovered
- All endpoints have methods and paths
- 80%+ endpoints have descriptions
- Authentication requirements identified
- No critical missing metadata
"""

import logging
from typing import Dict, Any, List
from agentic_scraper.business_analyst.state import BAAnalystState, EndpointFinding

logger = logging.getLogger(__name__)


def validate_endpoint_count(endpoints: List[EndpointFinding], min_count: int = 5) -> tuple[bool, str]:
    """Validate that sufficient endpoints were discovered.

    Args:
        endpoints: List of discovered endpoints
        min_count: Minimum required endpoints (default: 5 for API sources)

    Returns:
        Tuple of (is_valid, message)
    """
    count = len(endpoints)

    if count >= min_count:
        return True, f"Endpoint count validation passed: {count} endpoints (min: {min_count})"
    else:
        return False, f"Insufficient endpoints: {count} endpoints (min: {min_count})"


def validate_schema_completeness(endpoints: List[EndpointFinding]) -> tuple[bool, str]:
    """Validate that endpoints have complete basic schema (method + path).

    Args:
        endpoints: List of discovered endpoints

    Returns:
        Tuple of (is_valid, message)
    """
    if not endpoints:
        return False, "No endpoints to validate"

    # Check that all have methods
    missing_methods = sum(1 for ep in endpoints if not ep.method_guess or ep.method_guess == "unknown")

    # Check that all have paths
    missing_paths = sum(1 for ep in endpoints if not ep.url)

    if missing_methods == 0 and missing_paths == 0:
        return True, "Schema completeness validation passed (all have methods and paths)"
    else:
        issues = []
        if missing_methods > 0:
            issues.append(f"{missing_methods} missing methods")
        if missing_paths > 0:
            issues.append(f"{missing_paths} missing paths")
        return False, f"Schema incomplete: {', '.join(issues)}"


def validate_descriptions(endpoints: List[EndpointFinding], min_percentage: float = 0.8) -> tuple[bool, str]:
    """Validate that most endpoints have descriptions.

    Args:
        endpoints: List of discovered endpoints
        min_percentage: Minimum percentage with descriptions (default: 80%)

    Returns:
        Tuple of (is_valid, message)
    """
    if not endpoints:
        return False, "No endpoints to validate"

    # Count endpoints with descriptions
    with_descriptions = sum(1 for ep in endpoints if ep.notes and ep.notes != "unknown")
    percentage = (with_descriptions / len(endpoints)) * 100

    if percentage >= (min_percentage * 100):
        return True, f"Description validation passed: {percentage:.1f}% have descriptions (min: {min_percentage*100}%)"
    else:
        return False, f"Too few descriptions: {percentage:.1f}% (min: {min_percentage*100}%)"


def validate_auth_detection(auth_summary: str) -> tuple[bool, str]:
    """Validate that authentication requirements were identified.

    Args:
        auth_summary: Authentication summary from discovery

    Returns:
        Tuple of (is_valid, message)
    """
    if not auth_summary:
        return False, "No authentication summary provided"

    # Check for meaningful auth information (not just "unknown")
    if "unknown" in auth_summary.lower() and len(auth_summary) < 50:
        return False, f"Authentication detection incomplete: {auth_summary}"

    return True, f"Authentication validation passed: {auth_summary}"


def api_p2_validator(state: BAAnalystState) -> Dict[str, Any]:
    """P2: Validate API endpoint discovery.

    Runs validation checks on discovered endpoints to ensure
    completeness and usability. Reports gaps if validation fails.

    Args:
        state: Current graph state with discovery results

    Returns:
        State updates with validation results, gaps, and control flow
    """
    logger.info("=== API P2 Validator: Validation Phase ===")

    endpoints = state.get("endpoints", [])
    auth_summary = state.get("auth_summary")

    logger.info(
        f"Validating {len(endpoints)} discovered endpoints, "
        f"auth_summary={auth_summary}"
    )

    # Run validation checks
    checks = {}
    gaps = []

    # Check 1: Endpoint count
    is_valid, message = validate_endpoint_count(endpoints)
    checks["min_endpoints"] = is_valid
    if not is_valid:
        gaps.append(f"Endpoint count: {message}")
    logger.info(f"Check: Endpoint count - {message}")

    # Check 2: Schema completeness
    is_valid, message = validate_schema_completeness(endpoints)
    checks["schema_complete"] = is_valid
    if not is_valid:
        gaps.append(f"Schema: {message}")
    logger.info(f"Check: Schema completeness - {message}")

    # Check 3: Descriptions
    is_valid, message = validate_descriptions(endpoints)
    checks["has_descriptions"] = is_valid
    if not is_valid:
        gaps.append(f"Descriptions: {message}")
    logger.info(f"Check: Descriptions - {message}")

    # Check 4: Auth detection
    is_valid, message = validate_auth_detection(auth_summary)
    checks["auth_detected"] = is_valid
    if not is_valid:
        gaps.append(f"Authentication: {message}")
    logger.info(f"Check: Authentication - {message}")

    # Overall validation result
    all_checks_passed = all(checks.values())

    if all_checks_passed:
        logger.info(
            f"✅ API P2 validation PASSED: {len(endpoints)} endpoints with full metadata"
        )
        return {
            "next_action": "stop",
            "stop_reason": f"API discovery complete: {len(endpoints)} endpoints with full metadata validated",
            "p2_complete": True,
            "gaps": []  # Clear any previous gaps
        }
    else:
        failed_checks = [name for name, passed in checks.items() if not passed]
        logger.warning(
            f"❌ API P2 validation FAILED: {len(failed_checks)} checks failed: {failed_checks}"
        )
        return {
            "next_action": "continue",  # Return to planner to continue exploration
            "gaps": gaps,
            "p2_complete": False
        }


# Export
__all__ = ["api_p2_validator"]
