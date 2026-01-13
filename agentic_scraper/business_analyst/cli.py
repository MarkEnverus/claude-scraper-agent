"""CLI for BA Analyst.

Command-line interface for running the Business Analyst system.

Usage:
    ba-analyze <url> [options]

Example:
    ba-analyze https://api.example.com/docs --max-depth 2 --output-dir ./results
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from agentic_scraper.business_analyst.config import BAConfig
from agentic_scraper.business_analyst.graph import create_ba_graph
from agentic_scraper.business_analyst.state import BAAnalystState


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_primary_api_name(seed_url: str) -> Optional[str]:
    """Extract primary API name from URL fragment.

    Parses URL fragments like #api=pricing-api to extract the API name.
    This helps the agent stay focused on a specific API when multiple APIs
    are available on the same portal.

    Examples:
        https://data-exchange.misoenergy.org/api-details#api=pricing-api
          → "pricing-api"
        https://portal.spp.org/groups/integrated-marketplace
          → None (no fragment)

    Args:
        seed_url: The seed URL to parse

    Returns:
        API name if found in fragment, None otherwise
    """
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(seed_url)
    if parsed.fragment:
        # Parse fragment like "api=pricing-api"
        frag_params = parse_qs(parsed.fragment)
        if 'api' in frag_params:
            api_name = frag_params['api'][0]
            logger.info(f"Extracted primary_api_name from URL fragment: {api_name}")
            return api_name
    return None


def create_initial_state(
    seed_url: str,
    max_depth: int = 3,
    allowed_domains: Optional[list[str]] = None,
    config: Optional[BAConfig] = None
) -> BAAnalystState:
    """Create initial state for BA Analyst graph.

    Args:
        seed_url: Starting URL to analyze
        max_depth: Maximum navigation depth
        allowed_domains: List of allowed domains (defaults to seed domain)
        config: Optional BAConfig instance

    Returns:
        Initial BAAnalystState for graph execution
    """
    if config is None:
        config = BAConfig()

    if allowed_domains is None:
        # Extract domain from seed_url
        from urllib.parse import urlparse
        parsed = urlparse(seed_url)
        allowed_domains = [parsed.netloc]

    # Extract primary API name from URL fragment (e.g., #api=pricing-api)
    primary_api_name = extract_primary_api_name(seed_url)

    return {
        "seed_url": seed_url,
        "primary_api_name": primary_api_name,
        "max_depth": max_depth,
        "allowed_domains": allowed_domains,
        "visited": set(),
        "analyzed_urls": set(),  # URLs that completed analyst AI analysis
        "queue": [],
        "current_depth": 0,
        "current_url": None,
        "last_analyzed_url": None,  # P1/P2 Bug #2 fix
        "artifacts": {},
        "screenshots": {},
        "candidate_api_calls": [],  # Network API calls discovered
        "endpoints": [],
        "auth_summary": None,
        "gaps": [],
        "next_action": None,
        "stop_reason": None,
        "consecutive_failures": 0,  # Track consecutive failures
        "planner_agent": None,  # ReAct agent instance
        "config": config,
        # P1/P2 fields (Phase 1+ for WEBSITE/API specialized handling)
        "detected_source_type": None,
        "detection_confidence": 0.0,
        "website_hierarchy_level": None,
        "discovered_data_links": [],
        "folder_paths_visited": set(),
        "needs_p1_handling": False,
        "p1_complete": False,
        "p2_complete": False
    }


def run_analysis(
    seed_url: str,
    max_depth: int = 3,
    allowed_domains: Optional[list[str]] = None,
    output_dir: Optional[str] = None,
    config: Optional[BAConfig] = None
) -> dict:
    """Run BA Analyst analysis on a URL.

    Args:
        seed_url: Starting URL to analyze
        max_depth: Maximum navigation depth
        allowed_domains: List of allowed domains
        output_dir: Output directory for results (default: ./outputs)
        config: Optional BAConfig instance

    Returns:
        Final state dictionary with analysis results
    """
    logger.info(f"Starting BA Analyst: {seed_url}")
    logger.info(f"Max depth: {max_depth}, Allowed domains: {allowed_domains}")

    # Create graph
    graph = create_ba_graph()

    # Create initial state
    initial_state = create_initial_state(
        seed_url=seed_url,
        max_depth=max_depth,
        allowed_domains=allowed_domains,
        config=config
    )

    # Configure LangGraph execution
    graph_config = {
        "configurable": {
            "thread_id": f"ba-analyst-{seed_url}"
        },
        "recursion_limit": 150  # Support deep portal exploration (50 pages × ~3 cycles/page)
    }

    # Run graph
    logger.info("Executing BA Analyst graph...")
    try:
        final_state = graph.invoke(initial_state, config=graph_config)
        logger.info("Analysis complete!")

        # Save results
        if output_dir:
            from agentic_scraper.business_analyst.output import save_results
            save_results(final_state, output_dir)
            logger.info(f"Results saved to: {output_dir}")

        return final_state

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise


def run_analyze_command(args):
    """Handle 'analyze' subcommand."""
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    # Create config
    config = BAConfig(
        render_mode=args.render_mode
    )

    # Determine output directory
    if args.output_dir is None:
        from urllib.parse import urlparse
        parsed = urlparse(args.url)
        hostname = parsed.netloc.replace(":", "_")
        args.output_dir = f"./outputs/{hostname}"

    # Ensure output directory exists
    try:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error(f"Failed to create output directory '{args.output_dir}': {e}")
        sys.exit(1)

    # Run analysis
    try:
        final_state = run_analysis(
            seed_url=args.url,
            max_depth=args.max_depth,
            allowed_domains=args.allowed_domains,
            output_dir=args.output_dir,
            config=config
        )

        # Print summary
        print("\n" + "="*80)
        print("BA ANALYST SUMMARY")
        print("="*80)
        print(f"Site: {args.url}")
        print(f"Pages visited: {len(final_state['visited'])}")
        print(f"Endpoints found: {len(final_state['endpoints'])}")
        print(f"Stop reason: {final_state.get('stop_reason', 'unknown')}")
        print(f"Results: {args.output_dir}/site_report.md")
        print("="*80)

        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("Analysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)


async def run_generate_command_async(args):
    """Handle 'generate' subcommand (async)."""
    from agentic_scraper.generators.orchestrator import ScraperOrchestrator

    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    orchestrator = ScraperOrchestrator()

    # Check if source is URL or file path
    source_path = Path(args.source)

    try:
        if source_path.exists():
            # Generate from existing BA spec
            logger.info(f"Generating scraper from BA spec: {args.source}")
            result = await orchestrator.generate_from_spec(
                ba_spec_file=args.source,
                output_dir=args.output_dir
            )
        else:
            # Assume it's a URL - analyze first, then generate
            logger.info(f"Analyzing URL first: {args.source}")
            result = await orchestrator.generate_from_url(
                url=args.source,
                output_dir=args.output_dir
            )

        # Print summary
        print("\n" + "="*80)
        print("SCRAPER GENERATION SUMMARY")
        print("="*80)
        print(f"Source: {args.source}")
        print(f"Source type: {result.source_type}")
        print(f"Scrapers generated: {len(result.generated_files)}")
        for gf in result.generated_files:
            print(f"  - {gf.scraper_path}")
        print(f"BA spec: {result.ba_spec_path}")
        print("="*80)

        sys.exit(0)

    except KeyboardInterrupt:
        logger.warning("Generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        sys.exit(1)


def run_generate_command(args):
    """Sync wrapper for generate command."""
    import asyncio
    return asyncio.run(run_generate_command_async(args))


def main():
    """CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(
        description="Agentic Scraper - AI-powered data source analysis and scraper generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  analyze   Run BA Analyzer to understand data sources
  generate  Generate scrapers from BA spec or URL

Examples:
  # Analyze a data source
  agentic-scraper analyze https://api.example.com/docs --max-depth 2
  agentic-scraper analyze https://portal.example.com --output-dir ./results

  # Generate scraper from existing BA spec
  agentic-scraper generate ./datasource_analysis/validated_datasource_spec.json

  # Generate scraper by analyzing URL first
  agentic-scraper generate https://api.example.com/docs --output-dir ./scrapers
        """
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to run")

    # Subcommand: analyze
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze a data source URL",
        description="Run BA Analyzer to understand APIs, websites, or data portals",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    analyze_parser.add_argument(
        "url",
        help="Starting URL to analyze"
    )
    analyze_parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="Maximum navigation depth (default: 3)"
    )
    analyze_parser.add_argument(
        "--allow-domain",
        action="append",
        dest="allowed_domains",
        help="Allowed domain (can be specified multiple times)"
    )
    analyze_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for results (default: ./outputs/<hostname>)"
    )
    analyze_parser.add_argument(
        "--render-mode",
        choices=["always", "auto", "never"],
        default="auto",
        help="Screenshot rendering mode (default: auto)"
    )
    analyze_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    analyze_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    # Subcommand: generate
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate scraper from BA spec or URL",
        description="Generate production-ready scraper from BA spec file or by analyzing URL first",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    generate_parser.add_argument(
        "source",
        help="Path to BA spec JSON file OR URL to analyze first"
    )
    generate_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for generated scraper(s) (default: ./sourcing/scraping/<datasource>/<dataset>/)"
    )
    generate_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    generate_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Route to subcommand handlers
    if args.command == "analyze":
        return run_analyze_command(args)
    elif args.command == "generate":
        return run_generate_command(args)


if __name__ == "__main__":
    main()
