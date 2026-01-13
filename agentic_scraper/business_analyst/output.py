"""Output writers for BA Analyst.

This module handles saving analysis results to disk in various formats.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

from agentic_scraper.business_analyst.state import BAAnalystState, SiteReport

logger = logging.getLogger(__name__)


def save_results(state: BAAnalystState, output_dir: str):
    """Save analysis results to output directory.

    Creates:
    - site_report.json - Structured JSON report
    - site_report.md - Executive markdown summary
    - state.json - Complete final state (for debugging)

    Args:
        state: Final BAAnalystState from graph execution
        output_dir: Output directory path

    Raises:
        OSError: If output directory cannot be created
        Exception: If results cannot be saved
    """
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Saving results to: {output_path}")
    except OSError as e:
        logger.error(f"Failed to create output directory '{output_dir}': {e}")
        raise

    # 1. Save structured report (if available)
    try:
        if "report" in state and state["report"]:
            report = state["report"]
            report_path = output_path / "site_report.json"

            # Convert SiteReport to dict
            if hasattr(report, "model_dump"):
                report_dict = report.model_dump()
            elif hasattr(report, "dict"):
                report_dict = report.dict()
            else:
                report_dict = dict(report)

            with open(report_path, "w") as f:
                json.dump(report_dict, f, indent=2, default=str)

            logger.info(f"Saved JSON report: {report_path}")
    except Exception as e:
        logger.error(f"Failed to save JSON report: {e}")
        raise

    # 2. Save markdown summary (if available)
    try:
        if "markdown" in state and state["markdown"]:
            markdown_path = output_path / "site_report.md"
            with open(markdown_path, "w") as f:
                f.write(state["markdown"])

            logger.info(f"Saved markdown report: {markdown_path}")
    except Exception as e:
        logger.error(f"Failed to save markdown report: {e}")
        raise

    # 3. Save complete state (for debugging)
    try:
        state_path = output_path / "state.json"

        # Convert state to JSON-serializable format
        state_dict = {}
        for key, value in state.items():
            if key == "visited":
                state_dict[key] = list(value)  # set -> list
            elif key == "config":
                # Skip config object (too large)
                state_dict[key] = "<config object>"
            elif key == "artifacts":
                # Summarize artifacts (don't save full HTML)
                state_dict[key] = {
                    url: {
                        "url": url,
                        "status_code": artifact.status_code,
                        "screenshot_path": artifact.screenshot_path,
                        "links_count": len(artifact.links) if artifact.links else 0
                    }
                    for url, artifact in value.items()
                }
            elif key == "endpoints":
                # Convert Pydantic models to dicts
                state_dict[key] = [
                    endpoint.model_dump() if hasattr(endpoint, "model_dump") else dict(endpoint)
                    for endpoint in value
                ]
            else:
                state_dict[key] = value

        with open(state_path, "w") as f:
            json.dump(state_dict, f, indent=2, default=str)

        logger.info(f"Saved state: {state_path}")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")
        raise

    # 4. Copy NEW_GRAPH_v2 output files (validated spec, inventory, executive summary)
    #    These are written by summarizer to outputs/{hostname}/, but orchestrator expects them
    #    at the specified output_dir (e.g., datasource_analysis/)
    try:
        from urllib.parse import urlparse
        import shutil

        seed_url = state.get('seed_url', '')
        if seed_url:
            parsed = urlparse(seed_url)
            hostname = parsed.netloc or 'unknown_host'
            summarizer_output_dir = Path(f'outputs/{hostname}')

            # Files to copy
            new_graph_files = [
                'validated_datasource_spec.json',
                'endpoint_inventory.json',
                'executive_data_summary.md'
            ]

            for filename in new_graph_files:
                source_file = summarizer_output_dir / filename
                if source_file.exists():
                    dest_file = output_path / filename
                    shutil.copy2(source_file, dest_file)
                    logger.info(f"Copied NEW_GRAPH_v2 file: {filename}")
                else:
                    logger.warning(f"NEW_GRAPH_v2 file not found (skipping): {source_file}")

    except Exception as e:
        logger.warning(f"Failed to copy NEW_GRAPH_v2 files: {e}")
        # Don't fail the entire save operation if NEW_GRAPH_v2 files can't be copied

    # 5. List screenshot files (if any)
    screenshot_dir = output_path / "screenshots"
    if screenshot_dir.exists():
        screenshots = list(screenshot_dir.glob("*.png"))
        logger.info(f"Screenshots: {len(screenshots)} files in {screenshot_dir}")


def load_state(state_path: str) -> Dict[str, Any]:
    """Load saved state from JSON file.

    Args:
        state_path: Path to state.json file

    Returns:
        State dictionary

    Raises:
        FileNotFoundError: If state file doesn't exist
        json.JSONDecodeError: If state file is not valid JSON

    Example:
        >>> state = load_state("outputs/example/state.json")
    """
    try:
        with open(state_path, "r") as f:
            state_dict = json.load(f)

        # Convert lists back to sets where needed
        if "visited" in state_dict and isinstance(state_dict["visited"], list):
            state_dict["visited"] = set(state_dict["visited"])

        logger.info(f"Loaded state from: {state_path}")
        return state_dict
    except FileNotFoundError as e:
        logger.error(f"State file not found: {state_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from {state_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load state from {state_path}: {e}")
        raise


# Export
__all__ = ["save_results", "load_state"]
