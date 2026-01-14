"""Summarizer Node for BA Analyst LangGraph system.

This node generates the final report after all analysis is complete.
It creates both a structured JSON report (SiteReport) and an executive
markdown summary for stakeholders.

The node is responsible for:
1. Aggregating all findings from the state
2. Generating a structured SiteReport with all metrics
3. Using the Phase 3 prompt to generate executive markdown summary
4. Saving both outputs to the outputs/ directory
5. Linking to evidence (screenshots, visited URLs)
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse
from datetime import datetime

from agentic_scraper.business_analyst.state import BAAnalystState, SiteReport, EndpointFinding
from agentic_scraper.llm.factory import LLMFactory
from agentic_scraper.business_analyst.prompts.phase3 import executive_summary_prompt
from agentic_scraper.business_analyst.filtering.endpoint_filter import run_hybrid_filter, FilteringResult
from agentic_scraper.types.ba_analysis import (
    EndpointDetails,
    HTTPMethod,
    ResponseFormat,
    ValidationStatus,
    ExecutiveSummary,
    ValidationSummary,
    ComplexityLevel,
    ConfidenceLevel,
    AuthenticationMethod,
    DataSourceType,
    Parameter,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

def extract_next_actions(state: BAAnalystState) -> List[str]:
    """Extract suggested next actions from the analysis state.

    Generates actionable recommendations based on the analysis findings:
    - Authentication setup if auth is required
    - Endpoint testing recommendations
    - Gap investigation suggestions
    - Documentation requests

    Args:
        state: Complete BA Analyst state with all findings

    Returns:
        List of actionable next step strings
    """
    actions = []

    # Check authentication needs
    auth_summary = state.get('auth_summary') or ''
    auth_summary_lower = auth_summary.lower() if auth_summary else ''
    if auth_summary_lower and ('required' in auth_summary_lower or 'auth' in auth_summary_lower):
        actions.append("Obtain API credentials or authentication tokens")
        actions.append("Test authenticated endpoints with valid credentials")

    # Check for accessible endpoints
    endpoints = state.get('endpoints', [])
    if endpoints:
        actions.append(f"Test {len(endpoints)} discovered endpoints with sample requests")

        # Check for untested endpoints
        untested = [ep for ep in endpoints if ep.auth_required == 'unknown']
        if untested:
            actions.append(f"Validate authentication requirements for {len(untested)} endpoints")

    # Check for gaps
    gaps = state.get('gaps', [])
    if gaps:
        actions.append(f"Investigate {len(gaps)} identified knowledge gaps")
        for gap in gaps[:3]:  # Include first 3 gaps as specific actions
            actions.append(f"Research: {gap}")

    # Check queue for unvisited high-value links
    queue = state.get('queue', [])
    high_value_links = [item for item in queue if item.get('score', 0) > 0.7]
    if high_value_links:
        actions.append(f"Review {len(high_value_links)} high-value unvisited links manually")

    # Default actions if nothing specific found
    if not actions:
        actions.append("Review documentation for additional endpoint details")
        actions.append("Test discovered endpoints with sample data")
        actions.append("Implement scraper based on findings")

    return actions


def count_screenshots(state: BAAnalystState) -> int:
    """Count total screenshots captured during analysis.

    Args:
        state: Complete BA Analyst state

    Returns:
        Number of screenshots captured
    """
    screenshots = state.get('screenshots', {})
    return len(screenshots)


def sum_tokens(state: BAAnalystState) -> int:
    """Aggregate total token usage from all LLM interactions.

    Sums token usage from llm_interactions stored in PageArtifacts.

    Args:
        state: Complete BA Analyst state

    Returns:
        Total tokens used across all LLM calls
    """
    total = 0
    artifacts = state.get('artifacts', {})

    for artifact in artifacts.values():
        if hasattr(artifact, 'llm_interactions'):
            for interaction in artifact.llm_interactions:
                # Sum input and output tokens if available
                if isinstance(interaction, dict):
                    total += interaction.get('input_tokens', 0)
                    total += interaction.get('output_tokens', 0)

    return total


def get_hostname(url: str) -> str:
    """Extract hostname from URL for directory naming.

    Args:
        url: Full URL

    Returns:
        Hostname (e.g., 'api.example.com')
    """
    parsed = urlparse(url)
    return parsed.netloc or 'unknown_host'


def ensure_output_directory(hostname: str) -> Path:
    """Ensure output directory exists for the given hostname.

    Creates directory structure: outputs/{hostname}/screenshots/

    Args:
        hostname: Hostname from seed URL

    Returns:
        Path to output directory
    """
    output_dir = Path('outputs') / hostname
    output_dir.mkdir(parents=True, exist_ok=True)

    # Also ensure screenshots directory exists
    screenshots_dir = output_dir / 'screenshots'
    screenshots_dir.mkdir(exist_ok=True)

    return output_dir


def save_json_report(report: SiteReport, output_dir: Path) -> Path:
    """Save structured JSON report to file.

    Args:
        report: SiteReport instance
        output_dir: Directory to save to

    Returns:
        Path to saved JSON file
    """
    json_path = output_dir / 'site_report.json'

    # Convert to JSON-serializable dict
    report_dict = report.model_dump()

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report_dict, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved JSON report: {json_path}")
    return json_path


def save_markdown_report(markdown: str, output_dir: Path) -> Path:
    """Save executive markdown report to file.

    Args:
        markdown: Generated markdown content
        output_dir: Directory to save to

    Returns:
        Path to saved markdown file
    """
    md_path = output_dir / 'site_report.md'

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

    logger.info(f"Saved markdown report: {md_path}")
    return md_path


def build_validation_stats(state: BAAnalystState) -> Dict:
    """Build validation statistics for executive summary prompt.

    This provides pre-calculated stats to avoid overwhelming the LLM
    with raw data (optimization from Phase 3 executive_summary_prompt).

    Args:
        state: Complete BA Analyst state

    Returns:
        Dictionary with validation statistics
    """
    endpoints = state.get('endpoints', [])

    # Count endpoint status
    accessible = sum(1 for ep in endpoints if 'accessible' in ep.notes.lower() or '200' in ep.notes)
    protected = sum(1 for ep in endpoints if 'auth' in ep.auth_required.lower() or '401' in ep.notes or '403' in ep.notes)
    broken = sum(1 for ep in endpoints if '404' in ep.notes or '500' in ep.notes)

    total_endpoints = len(endpoints)
    success_rate = (accessible / total_endpoints) if total_endpoints > 0 else 0.0

    # Calculate confidence score
    auth_summary = state.get('auth_summary') or ''
    auth_summary_lower = auth_summary.lower() if auth_summary else ''
    pages_visited = len(state.get('visited', set()))

    # High confidence if: auth detected and confirmed, OR no auth and endpoints accessible
    if protected > 0 and 'required' in auth_summary_lower:
        confidence_score = 0.85  # Auth requirement confirmed
    elif accessible > total_endpoints * 0.7:
        confidence_score = 0.9  # Most endpoints accessible
    elif total_endpoints == 0:
        confidence_score = 0.3  # No endpoints found
    else:
        confidence_score = 0.6  # Mixed results

    return {
        'total_endpoints': total_endpoints,
        'accessible_endpoints': accessible,
        'protected_endpoints': protected,
        'broken_endpoints': broken,
        'success_rate': success_rate,
        'confidence_score': confidence_score,
        'auth_prediction_correct': protected > 0 if 'required' in auth_summary_lower else accessible > 0,
        'pages_visited': pages_visited,
    }


def generate_executive_markdown(state: BAAnalystState, report: SiteReport) -> str:
    """Generate executive markdown summary using Phase 3 prompt.

    Uses the executive_summary_prompt from Phase 3 to generate a concise,
    stakeholder-friendly markdown report with key findings and recommendations.

    Args:
        state: Complete BA Analyst state
        report: Structured SiteReport

    Returns:
        Generated markdown string
    """
    config = state.get('config')
    if not config:
        logger.warning("No config found in state, using default LLM settings")
        from agentic_scraper.business_analyst.config import BAConfig
        config = BAConfig()

    # Create LLM instance (use reasoning model for quality summary writing)
    factory = LLMFactory(config=config, region=config.aws_region)
    reasoning_model = factory.create_reasoning_model()

    # Build validation statistics for the prompt
    validation_stats = build_validation_stats(state)

    # Extract phase results from state (if available)
    # These will be populated during actual graph execution
    phase0 = state.get('phase0_result')
    phase1 = state.get('phase1_result')
    phase2 = state.get('phase2_result')

    # If phase results are not available, use fallback markdown generation
    # (This happens during development or if nodes didn't populate phase results)
    if not (phase0 and phase1 and phase2):
        logger.warning("Phase results not available in state, using fallback markdown generation")
        return generate_fallback_markdown(report, validation_stats)

    # Generate prompt
    prompt = executive_summary_prompt(validation_stats, phase0, phase1, phase2)

    logger.info("Generating executive markdown with LLM...")

    try:
        # Invoke LLM for markdown generation
        response = factory.invoke_text(reasoning_model, prompt)

        # Extract markdown content from response
        if isinstance(response, str):
            markdown = response
        elif hasattr(response, 'content'):
            markdown = response.content
        else:
            markdown = str(response)

        logger.info(f"Generated markdown summary ({len(markdown)} chars)")
        return markdown

    except Exception as e:
        logger.error(f"Failed to generate executive markdown: {e}")
        # Fallback to basic markdown
        return generate_fallback_markdown(report, validation_stats)


def generate_fallback_markdown(report: SiteReport, stats: Dict) -> str:
    """Generate basic markdown if LLM generation fails.

    Args:
        report: SiteReport instance
        stats: Validation statistics

    Returns:
        Basic markdown report
    """
    md = f"""# {report.site} - Data Source Analysis

## Executive Summary

- **Data Source**: {report.site}
- **Analysis Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Total Endpoints Discovered**: {len(report.endpoints)}
- **Authentication Required**: {report.auth_summary}
- **Pages Visited**: {report.pages_visited}
- **Screenshots Captured**: {report.screenshots_captured}
- **Stop Reason**: {report.stop_reason or 'Analysis completed'}

## Overview

This analysis visited {report.pages_visited} pages and discovered {len(report.endpoints)} endpoints.

## Auth Posture

{report.auth_summary or 'Authentication status unknown'}

## High-Value Endpoints

"""

    # Add endpoint list
    if report.endpoints:
        for ep in report.endpoints[:10]:  # Top 10
            md += f"- **{ep.name}**: `{ep.method_guess} {ep.url}`\n"
            if ep.notes:
                md += f"  - {ep.notes}\n"
    else:
        md += "No endpoints discovered.\n"

    md += "\n## Suggested Next Steps\n\n"

    # Add next actions
    for i, action in enumerate(report.next_actions, 1):
        md += f"{i}. {action}\n"

    # Add gaps if any
    if report.gaps:
        md += "\n## Known Gaps\n\n"
        for gap in report.gaps:
            md += f"- {gap}\n"

    # Add evidence section
    md += f"\n## Evidence\n\n"
    md += f"- Pages visited: {report.pages_visited}\n"
    md += f"- Screenshots: {report.screenshots_captured}\n"
    md += f"- Total tokens: {report.total_tokens}\n"

    md += "\n---\n\n*Generated by BA Agent - Business Analyst*\n"

    return md


# ============================================================================
# NEW_GRAPH_v2: Validated Data Spec Output Functions
# ============================================================================

def convert_endpoint_finding_to_details(
    finding: EndpointFinding,
    base_url: str,
    auth_method: Optional[str] = None
) -> EndpointDetails:
    """Convert EndpointFinding (BA format) to EndpointDetails (Generator format).

    Args:
        finding: Endpoint from BA discovery
        base_url: Base URL for the data source
        auth_method: Optional authentication method override

    Returns:
        EndpointDetails compatible with generator input
    """
    # Parse URL to extract base_url and path
    try:
        parsed = urlparse(finding.url)
        endpoint_base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else base_url
        endpoint_path = parsed.path or '/'
    except Exception:
        endpoint_base_url = base_url
        endpoint_path = finding.url

    # Convert method_guess to HTTPMethod enum
    method_map = {
        "GET": HTTPMethod.GET,
        "POST": HTTPMethod.POST,
        "PUT": HTTPMethod.PUT,
        "DELETE": HTTPMethod.DELETE,
        "PATCH": HTTPMethod.PATCH,
    }
    method = method_map.get(finding.method_guess.upper(), HTTPMethod.GET)

    # Convert format to ResponseFormat enum
    format_map = {
        "json": ResponseFormat.JSON,
        "xml": ResponseFormat.XML,
        "csv": ResponseFormat.CSV,
        "html": ResponseFormat.HTML,
        "xlsx": ResponseFormat.BINARY,
        "binary": ResponseFormat.BINARY,
    }
    response_format = format_map.get(finding.format.lower(), ResponseFormat.JSON)

    # Convert auth_required to authentication dict
    authentication = {}
    if finding.auth_required.lower() == "true":
        authentication["required"] = "true"
        if auth_method:
            authentication["method"] = auth_method
    else:
        authentication["required"] = "false"

    # Generate endpoint_id (kebab-case from name)
    endpoint_id = finding.name.lower().replace(' ', '-').replace('_', '-')

    # Convert EndpointFinding.parameters (List[Dict]) to EndpointDetails.parameters (dict[str, Parameter])
    # E3: Preserve Phase 1.5 parameter enrichment in generator inputs
    converted_parameters: dict[str, Parameter] = {}
    for param_dict in finding.parameters:
        param_name = param_dict.get("name", "")
        if not param_name:
            continue  # Skip parameters without names

        # Build Parameter model from dict, with safe defaults
        converted_parameters[param_name] = Parameter(
            name=param_name,
            type=param_dict.get("type", "string"),
            required=param_dict.get("required", False),
            description=param_dict.get("description", ""),
            location=param_dict.get("location"),
            format=param_dict.get("format"),
            example=param_dict.get("example"),
            default=param_dict.get("default"),
            enum=param_dict.get("enum"),
            minimum=param_dict.get("minimum"),
            maximum=param_dict.get("maximum"),
            pattern=param_dict.get("pattern"),
        )

    return EndpointDetails(
        endpoint_id=endpoint_id,
        name=finding.name,
        type="REST",  # Default to REST for discovered endpoints
        base_url=endpoint_base_url,
        path=endpoint_path,
        method=method,
        parameters=converted_parameters,
        authentication=authentication,
        response_format=response_format,
        validation_status=ValidationStatus.NOT_TESTED,
        accessible=finding.auth_required.lower() == "false",
        last_tested=datetime.now().isoformat(),
        notes=finding.notes
    )


def write_validated_spec(
    filtering_result: FilteringResult,
    state: BAAnalystState,
    output_dir: Path
) -> None:
    """Write validated_datasource_spec.json for scraper generator.

    This is the PRIMARY input file for the generator. It contains only
    data-relevant endpoints (≤max_endpoints_for_generation) with auth metadata.

    Args:
        filtering_result: Result from hybrid filtering pipeline
        state: Full BA analyst state
        output_dir: Directory to write output file

    Output File: validated_datasource_spec.json (generator input)
    """
    seed_url = state.get('seed_url', '')
    hostname = get_hostname(seed_url)

    # Extract source type from state
    detected_source_type = state.get('detected_source_type', 'API')
    source_type_str = detected_source_type if isinstance(detected_source_type, str) else detected_source_type.value

    # Generate datasource/dataset identifiers (snake_case)
    datasource = hostname.replace('.', '_').replace('-', '_')
    dataset = "data"  # Default dataset name

    # Convert EndpointFindings to EndpointDetails
    auth_notes = filtering_result.auth_metadata.get('auth_notes', '')
    auth_method = None
    if 'bearer' in auth_notes.lower() or 'token' in auth_notes.lower():
        auth_method = "bearer_token"
    elif 'api key' in auth_notes.lower() or 'api_key' in auth_notes.lower():
        auth_method = "api_key"
    elif 'basic' in auth_notes.lower():
        auth_method = "basic_auth"

    endpoint_details = [
        convert_endpoint_finding_to_details(ep, seed_url, auth_method)
        for ep in filtering_result.kept_endpoints
    ]

    # Build ExecutiveSummary
    total_discovered = filtering_result.filtering_summary['total_endpoints']
    kept_count = filtering_result.filtering_summary['kept_for_generation']

    primary_formats = list(set(ep.format for ep in filtering_result.kept_endpoints))
    auth_required = len(filtering_result.auth_metadata.get('auth_endpoints', [])) > 0

    # Estimate complexity based on endpoint count and auth
    if kept_count == 0:
        complexity = ComplexityLevel.LOW
    elif kept_count <= 2 and not auth_required:
        complexity = ComplexityLevel.LOW
    elif kept_count <= 5 and auth_required:
        complexity = ComplexityLevel.MEDIUM
    else:
        complexity = ComplexityLevel.HIGH

    executive_summary = ExecutiveSummary(
        total_endpoints_discovered=total_discovered,
        accessible_endpoints=kept_count,
        success_rate=f"{kept_count}/{total_discovered}" if total_discovered > 0 else "0/0",
        primary_formats=primary_formats or ["json"],
        authentication_required=auth_required,
        estimated_scraper_complexity=complexity
    )

    # Build ValidationSummary
    confidence_score = 0.9 if kept_count > 0 else 0.3
    confidence_level = ConfidenceLevel.HIGH if confidence_score >= 0.8 else (
        ConfidenceLevel.MEDIUM if confidence_score >= 0.5 else ConfidenceLevel.LOW
    )

    validation_summary = ValidationSummary(
        phases_completed=["Phase0", "Phase1", "Filtering"],
        documentation_review="Completed via BA analysis",
        live_api_testing="Not performed (discovery only)",
        discrepancies_found=0,
        confidence_score=confidence_score,
        confidence_level=confidence_level,
        recommendation=f"Proceed with scraper generation for {kept_count} data endpoints"
    )

    # Build ValidatedSpec-compatible dict (not full ValidatedSpec - generator only needs subset)
    validated_spec = {
        "source": hostname,
        "source_type": source_type_str,
        "datasource": datasource,
        "dataset": dataset,
        "url": seed_url,
        "timestamp": datetime.now().isoformat(),
        "executive_summary": executive_summary.model_dump(),
        "validation_summary": validation_summary.model_dump(),
        "endpoints": [ep.model_dump() for ep in endpoint_details],
        "authentication": {
            "required": auth_required,
            "method": auth_method or "unknown",
            "notes": auth_notes
        },
        "discovered_data_links": state.get('discovered_data_links', []),
        "filtering_applied": True,
        "filtering_summary": filtering_result.filtering_summary,
    }

    # Write to file
    output_path = output_dir / 'validated_datasource_spec.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(validated_spec, f, indent=2, ensure_ascii=False)

    logger.info(f"Wrote validated datasource spec: {output_path}")
    logger.info(f"  - {kept_count} endpoints for generation (filtered from {total_discovered})")
    logger.info(f"  - Authentication: {auth_required} ({auth_method or 'none'})")


def write_endpoint_inventory(
    filtering_result: FilteringResult,
    output_dir: Path
) -> None:
    """Write endpoint_inventory.json with full categorization.

    This is the AUDIT TRAIL file with complete transparency about filtering.
    Contains all endpoints (kept + discarded) with categories and reasons.

    Args:
        filtering_result: Result from hybrid filtering pipeline
        output_dir: Directory to write output file

    Output File: endpoint_inventory.json (audit trail)
    """
    inventory = {
        "filtering_summary": filtering_result.filtering_summary,
        "kept_endpoints": [
            {
                "name": ep.name,
                "url": ep.url,
                "method_guess": ep.method_guess,
                "format": ep.format,
                "data_type": ep.data_type,
                "notes": ep.notes,
                "status": "kept_for_generation"
            }
            for ep in filtering_result.kept_endpoints
        ],
        "discarded_endpoints": [
            discarded.to_dict()
            for discarded in filtering_result.discarded_endpoints
        ],
        "auth_metadata": filtering_result.auth_metadata,
    }

    output_path = output_dir / 'endpoint_inventory.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)

    logger.info(f"Wrote endpoint inventory: {output_path}")
    logger.info(f"  - Total: {filtering_result.filtering_summary['total_endpoints']}")
    logger.info(f"  - Kept: {filtering_result.filtering_summary['kept_for_generation']}")
    logger.info(f"  - Discarded: {filtering_result.filtering_summary['discarded_total']}")


def write_executive_data_summary(
    filtering_result: FilteringResult,
    state: BAAnalystState,
    output_dir: Path
) -> None:
    """Write executive_data_summary.md (data-focused summary).

    This is a HUMAN-READABLE summary focused on data collection only.
    Excludes portal plumbing (auth/nav/system endpoints) and focuses on:
    - What data is available
    - How to access it
    - Recommended collection method

    Args:
        filtering_result: Result from hybrid filtering pipeline
        state: Full BA analyst state
        output_dir: Directory to write output file

    Output File: executive_data_summary.md (data-focused markdown)
    """
    seed_url = state.get('seed_url', '')
    hostname = get_hostname(seed_url)
    detected_type = state.get('detected_source_type', 'API')
    type_str = detected_type if isinstance(detected_type, str) else detected_type.value

    # Extract data
    kept_endpoints = filtering_result.kept_endpoints
    auth_metadata = filtering_result.auth_metadata
    auth_notes = auth_metadata.get('auth_notes', 'Unknown')
    filtering_summary = filtering_result.filtering_summary

    # Build markdown
    md = f"""# {hostname} - Data Collection Summary

**Analysis Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Source URL**: {seed_url}
**Source Type**: {type_str}

---

## Data Collection Overview

This analysis identified **{filtering_summary['kept_for_generation']} data-relevant endpoint(s)** suitable for scraper generation.

**Filtering Results**:
- Total endpoints discovered: {filtering_summary['total_endpoints']}
- Data endpoints (kept): {filtering_summary['kept_for_generation']}
- Non-data endpoints (filtered): {filtering_summary['discarded_total']}
  - Stage 1 (pre-filter): {filtering_summary['discarded_stage1_pre_filter']}
  - Stage 2 (LLM classification): {filtering_summary['discarded_stage2_llm_filter']}
  - Stage 3 (cap limit): {filtering_summary['discarded_stage3_cap_limit']}

---

## Available Data Endpoints

"""

    if kept_endpoints:
        for i, ep in enumerate(kept_endpoints, 1):
            md += f"### {i}. {ep.name}\n\n"
            md += f"- **URL**: `{ep.url}`\n"
            md += f"- **Method**: {ep.method_guess}\n"
            md += f"- **Format**: {ep.format}\n"
            md += f"- **Data Type**: {ep.data_type}\n"
            if ep.notes:
                md += f"- **Notes**: {ep.notes}\n"
            if ep.evidence_urls:
                md += f"- **Evidence**: {len(ep.evidence_urls)} source(s)\n"
            md += "\n"
    else:
        md += "**No data endpoints discovered.** All discovered endpoints were filtered as non-data (auth/nav/system).\n\n"
        md += "**Recommendation**: Manual review may be needed to identify data access methods.\n\n"

    md += "---\n\n"
    md += "## Authentication Requirements\n\n"
    md += f"{auth_notes}\n\n"

    if auth_metadata.get('auth_endpoints'):
        md += "**Authentication Endpoints Discovered**:\n"
        for auth_ep in auth_metadata['auth_endpoints']:
            md += f"- `{auth_ep['name']}`: {auth_ep['url']}\n"
        md += "\n"

    md += "---\n\n"
    md += "## Recommended Collection Method\n\n"

    if kept_endpoints:
        md += f"**Scraper Type**: {type_str} collector\n\n"
        md += f"**Estimated Complexity**: {'Low' if len(kept_endpoints) <= 2 else ('Medium' if len(kept_endpoints) <= 5 else 'High')}\n\n"
        md += "**Implementation Notes**:\n"
        md += f"- {len(kept_endpoints)} endpoint(s) to implement\n"
        if auth_notes and 'required' in auth_notes.lower():
            md += "- Authentication required (obtain credentials first)\n"
        md += f"- Primary data formats: {', '.join(set(ep.format for ep in kept_endpoints))}\n"
    else:
        md += "**Status**: No data endpoints identified for automated collection.\n\n"
        md += "**Next Steps**:\n"
        md += "- Review endpoint inventory (endpoint_inventory.json) for full categorization\n"
        md += "- Consider manual data extraction if portal requires interactive navigation\n"
        md += "- Investigate alternative data access methods (bulk exports, APIs)\n"

    md += "\n---\n\n"
    md += "## Audit Trail\n\n"
    md += f"Full filtering details available in: `{output_dir / 'endpoint_inventory.json'}`\n\n"
    md += "This file contains:\n"
    md += "- All discovered endpoints with categories (DATA | AUTH | NAV | SYSTEM | UNKNOWN)\n"
    md += "- Confidence scores and reasoning for each classification\n"
    md += "- Stage-by-stage filtering decisions\n\n"

    md += "---\n\n"
    md += "*Generated by BA Analyst with NEW_GRAPH_v2 endpoint filtering*\n"

    # Write to file
    output_path = output_dir / 'executive_data_summary.md'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)

    logger.info(f"Wrote executive data summary: {output_path}")


def write_api_documentation_md(
    filtering_result: FilteringResult,
    state: BAAnalystState,
    output_dir: Path
) -> None:
    """Write API_DOCUMENTATION.md - technical API reference (E4).

    Generates a clean API reference document similar to the /discover-api plugin
    deliverables, derived entirely from discovered endpoints and parameters.

    Args:
        filtering_result: Result from hybrid filtering pipeline
        state: Full BA analyst state
        output_dir: Directory to write output file

    Output File: API_DOCUMENTATION.md (API reference)
    """
    seed_url = state.get('seed_url', '')
    hostname = get_hostname(seed_url)
    auth_metadata = filtering_result.auth_metadata
    kept_endpoints = filtering_result.kept_endpoints

    # Build markdown
    md = f"""# {hostname} - API Documentation

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Base URL**: {seed_url}

---

## Authentication

"""
    auth_notes = auth_metadata.get('auth_notes', 'Unknown')
    auth_method = auth_metadata.get('method', 'unknown')
    auth_required = auth_metadata.get('auth_required', False)

    if auth_required:
        md += f"**Required**: Yes\n"
        md += f"**Method**: {auth_method}\n\n"
        md += f"**Notes**: {auth_notes}\n\n"
    else:
        md += f"**Required**: No (public access)\n\n"
        md += f"**Notes**: {auth_notes}\n\n"

    md += "---\n\n"
    md += "## Endpoints\n\n"

    if not kept_endpoints:
        md += "*No data endpoints discovered. See endpoint_inventory.json for full audit.*\n\n"
    else:
        for i, ep in enumerate(kept_endpoints, 1):
            md += f"### {i}. {ep.name}\n\n"
            md += f"**URL**: `{ep.url}`\n\n"
            md += f"**Method**: `{ep.method_guess.upper()}`\n\n"
            md += f"**Response Format**: `{ep.format}`\n\n"

            # Parameters (from E3 - now preserved in EndpointFinding.parameters)
            if ep.parameters:
                md += "**Parameters**:\n\n"
                md += "| Name | Type | Required | Location | Description |\n"
                md += "|------|------|----------|----------|-------------|\n"
                for param in ep.parameters:
                    name = param.get('name', 'unknown')
                    ptype = param.get('type', 'string')
                    required = '✓' if param.get('required', False) else ''
                    location = param.get('location', 'query')
                    description = param.get('description', '')[:50]  # Truncate long descriptions
                    md += f"| `{name}` | {ptype} | {required} | {location} | {description} |\n"
                md += "\n"

                # Show example values if available
                examples = [(p.get('name'), p.get('example')) for p in ep.parameters if p.get('example')]
                if examples:
                    md += "**Example Values**:\n"
                    for name, example in examples:
                        md += f"- `{name}`: `{example}`\n"
                    md += "\n"

            # Pagination info
            if ep.pagination and ep.pagination.lower() not in ('unknown', 'false'):
                md += f"**Pagination**: Yes\n\n"
            elif ep.pagination and ep.pagination.lower() == 'false':
                md += f"**Pagination**: No\n\n"

            # Data type
            if ep.data_type and ep.data_type != 'other':
                md += f"**Data Type**: {ep.data_type}\n\n"

            # Notes
            if ep.notes:
                md += f"**Notes**: {ep.notes}\n\n"

            md += "---\n\n"

    # Rate limits section (placeholder - captured in notes if discovered)
    md += "## Rate Limits\n\n"
    rate_limit_notes = [ep.notes for ep in kept_endpoints if 'rate' in ep.notes.lower()]
    if rate_limit_notes:
        for note in rate_limit_notes:
            md += f"- {note}\n"
        md += "\n"
    else:
        md += "*No rate limit information discovered.*\n\n"

    md += "---\n\n"

    # Data links section (for WEBSITE sources with direct downloads)
    discovered_data_links = state.get('discovered_data_links', [])
    if discovered_data_links:
        md += "## Direct Download Links\n\n"
        md += "The following direct download URLs were discovered:\n\n"
        for link in discovered_data_links[:20]:  # Cap at 20
            md += f"- `{link}`\n"
        if len(discovered_data_links) > 20:
            md += f"\n*...and {len(discovered_data_links) - 20} more (see endpoint_inventory.json)*\n"
        md += "\n---\n\n"

    # Footer
    md += "## Usage Notes\n\n"
    md += "- This documentation is auto-generated from BA discovery analysis\n"
    md += "- Endpoints marked with 'unknown' values require manual verification\n"
    md += "- Parameter lists may be incomplete - check API source for authoritative docs\n"
    md += "- For full audit trail, see `endpoint_inventory.json`\n\n"
    md += "---\n\n"
    md += "*Generated by BA Analyst - E4: API Documentation Output*\n"

    # Write to file
    output_path = output_dir / 'API_DOCUMENTATION.md'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)

    logger.info(f"Wrote API documentation: {output_path}")


# ============================================================================
# Main Summarizer Node
# ============================================================================

def summarizer_node(state: BAAnalystState) -> Dict:
    """Summarizer Node - Generate final report and executive summary.

    This is the final node in the LangGraph workflow. It:
    1. Creates a structured SiteReport with all findings
    2. Generates executive markdown summary using Phase 3 prompt
    3. Saves both JSON and markdown to outputs/ directory
    4. Returns both in the state update

    Args:
        state: Complete BA Analyst state with all accumulated findings

    Returns:
        Dictionary with 'report' (SiteReport) and 'markdown' (str) keys

    Example:
        >>> state = {
        ...     'seed_url': 'https://api.example.com',
        ...     'visited': {'https://api.example.com', 'https://api.example.com/docs'},
        ...     'endpoints': [endpoint1, endpoint2],
        ...     'auth_summary': 'Authentication required',
        ...     'gaps': ['Rate limit unknown'],
        ...     'stop_reason': 'Max depth reached',
        ...     'config': BAConfig()
        ... }
        >>> result = summarizer_node(state)
        >>> print(result['report'].pages_visited)
        2
        >>> print(result['markdown'][:50])
        # https://api.example.com - Data Source Analysis
    """
    logger.info("=" * 80)
    logger.info("SUMMARIZER NODE - Generating final report")
    logger.info("=" * 80)

    # Extract hostname for output directory
    seed_url = state['seed_url']
    hostname = get_hostname(seed_url)

    # Ensure output directory exists
    output_dir = ensure_output_directory(hostname)
    logger.info(f"Output directory: {output_dir}")

    # Build navigation paths from visited URLs
    visited = state.get('visited', set())
    navigation_paths = [(url, "visited") for url in sorted(visited)]

    # Extract endpoint findings
    endpoints = state.get('endpoints', [])
    logger.info(f"Found {len(endpoints)} endpoints (before filtering)")

    # ========================================================================
    # NEW_GRAPH_v2: Apply hybrid 3-stage endpoint filtering
    # ========================================================================
    config = state.get('config')
    if not config:
        logger.warning("No config found in state, filtering will use default settings")
        from agentic_scraper.business_analyst.config import BAConfig
        config = BAConfig()

    # Create LLM factory for Stage 2 classification
    factory = LLMFactory(config=config, region=config.aws_region)

    # Run hybrid filtering pipeline
    logger.info("=" * 80)
    logger.info("ENDPOINT FILTERING - Hybrid 3-stage pipeline")
    logger.info("=" * 80)

    filtering_result = run_hybrid_filter(
        endpoints=endpoints,
        state=state,
        config=config,
        llm_factory=factory
    )

    # Use filtered endpoints for report generation
    endpoints = filtering_result.kept_endpoints
    logger.info(f"Using {len(endpoints)} filtered endpoints for report (after filtering)")

    # Generate NEW_GRAPH_v2 output files
    logger.info("Generating NEW_GRAPH_v2 output files...")
    write_validated_spec(filtering_result, state, output_dir)
    write_endpoint_inventory(filtering_result, output_dir)
    write_executive_data_summary(filtering_result, state, output_dir)
    write_api_documentation_md(filtering_result, state, output_dir)

    logger.info("=" * 80)
    logger.info("ENDPOINT FILTERING COMPLETE")
    logger.info("=" * 80)

    # Extract auth summary (ensure it's never None)
    auth_summary = state.get('auth_summary') or 'Unknown'

    # Extract gaps
    gaps = state.get('gaps', [])

    # Calculate metrics
    pages_visited = len(visited)
    screenshots_captured = count_screenshots(state)
    total_tokens = sum_tokens(state)

    logger.info(f"Pages visited: {pages_visited}")
    logger.info(f"Screenshots: {screenshots_captured}")
    logger.info(f"Total tokens: {total_tokens}")

    # Generate next actions
    next_actions = extract_next_actions(state)
    logger.info(f"Generated {len(next_actions)} next actions")

    # Get stop reason
    stop_reason = state.get('stop_reason')

    # Create structured SiteReport
    report = SiteReport(
        site=seed_url,
        endpoints=endpoints,
        auth_summary=auth_summary,
        navigation_paths=navigation_paths,
        gaps=gaps,
        next_actions=next_actions,
        stop_reason=stop_reason,
        pages_visited=pages_visited,
        screenshots_captured=screenshots_captured,
        total_tokens=total_tokens
    )

    logger.info("Created SiteReport")

    # Save JSON report
    json_path = save_json_report(report, output_dir)

    # Generate executive markdown
    logger.info("Generating executive markdown summary...")
    markdown = generate_executive_markdown(state, report)

    # Save markdown report
    md_path = save_markdown_report(markdown, output_dir)

    logger.info("=" * 80)
    logger.info("SUMMARIZER COMPLETE")
    logger.info(f"JSON Report: {json_path}")
    logger.info(f"Markdown Report: {md_path}")
    logger.info(f"Screenshots: {output_dir / 'screenshots'}/")
    logger.info("=" * 80)

    # Return both outputs
    return {
        'report': report,
        'markdown': markdown
    }


# Export public API
__all__ = [
    'summarizer_node',
    'extract_next_actions',
    'count_screenshots',
    'sum_tokens',
    'generate_executive_markdown',
]
