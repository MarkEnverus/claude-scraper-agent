"""Main CLI entry point for Claude Scraper.

This module provides the command-line interface for the Claude Scraper tool,
enabling data source analysis and scraper generation using LangGraph and BAML.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from claude_scraper.cli.config import Config
from claude_scraper.orchestration import AnalysisState, pipeline
from claude_scraper.types.errors import (
    CollationError,
    QATestingError,
    Run1AnalysisError,
    Run2AnalysisError,
)

__version__ = "2.0.0"

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="claude-scraper")
def cli() -> None:
    """Claude Scraper CLI - Type-safe scraper generation with LangGraph + BAML"""
    pass


@cli.command()
@click.option("--url", required=True, help="Data source URL to analyze")
@click.option(
    "--provider",
    type=click.Choice(["bedrock", "anthropic"]),
    default="bedrock",
    help="LLM provider to use (default: bedrock)",
)
@click.option(
    "--output-dir",
    default="datasource_analysis",
    help="Output directory for analysis files (default: datasource_analysis)",
)
@click.option("--debug", is_flag=True, help="Enable debug logging")
def analyze(url: str, provider: str, output_dir: str, debug: bool) -> None:
    """Analyze a data source and generate validated specification.

    This command runs the full BA analysis pipeline:
    - Run 1: 4-phase analysis (detection, documentation, testing, validation)
    - Decision: Check confidence score
    - Run 2: Focused re-analysis (if confidence < 0.8)
    - Collation: Merge Run 1 + Run 2 results
    - QA: Test all endpoints

    Example:
        claude-scraper analyze --url https://api.example.com
        claude-scraper analyze --url https://api.example.com --provider anthropic --debug
    """
    try:
        # Validate URL format
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            console.print(f"[bold red]✗ Invalid URL format:[/bold red] {url}")
            console.print(f"[yellow]Expected format:[/yellow] https://example.com/path")
            raise click.Abort()

        # Validate scheme
        if parsed.scheme not in ('http', 'https', 'ftp', 'ftps'):
            console.print(f"[bold red]✗ Unsupported URL scheme:[/bold red] {parsed.scheme}")
            console.print(f"[yellow]Supported schemes:[/yellow] http, https, ftp, ftps")
            raise click.Abort()

        # Setup logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.StreamHandler(sys.stderr),  # Logs go to stderr
            ],
        )

        # Load configuration
        config = Config.from_env(provider)  # type: ignore[arg-type]  # click validates choices

        if debug:
            console.print(f"[dim]Provider: {config.provider} ({config.model_id})[/dim]")
            console.print(f"[dim]Region: {config.region}[/dim]")
            console.print(f"[dim]Output directory: {output_dir}[/dim]")

        console.print(f"\n[bold cyan]Starting analysis:[/bold cyan] {url}\n")

        # Create output directory if it doesn't exist
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Run analysis with progress tracking
        asyncio.run(run_analysis(url, output_dir, debug))

    except ValueError as e:
        console.print(f"\n[bold red]Configuration Error:[/bold red] {e}")
        raise click.Abort()
    except (Run1AnalysisError, Run2AnalysisError, CollationError, QATestingError) as e:
        console.print(f"\n[bold red]Analysis Failed:[/bold red] {e}")
        if debug:
            console.print_exception()
        raise click.Abort()
    except Exception as e:
        console.print(f"\n[bold red]Unexpected Error:[/bold red] {e}")
        if debug:
            console.print_exception()
        raise click.Abort()


async def run_analysis(url: str, output_dir: str, debug: bool) -> None:
    """Execute the analysis pipeline with progress tracking.

    Args:
        url: Data source URL to analyze
        output_dir: Output directory for analysis files
        debug: Enable debug output
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=False,  # Keep progress bars visible after completion
    ) as progress:

        # Create tasks for each major phase
        task_overall = progress.add_task(
            "[bold cyan]Overall Progress", total=5
        )
        task_run1 = progress.add_task(
            "[cyan]Run 1: Initial Analysis", total=100
        )
        task_decision = progress.add_task(
            "[yellow]Evaluating Confidence", total=100, visible=False
        )
        task_run2 = progress.add_task(
            "[cyan]Run 2: Focused Analysis", total=100, visible=False
        )
        task_collation = progress.add_task(
            "[green]Collating Results", total=100, visible=False
        )
        task_qa = progress.add_task(
            "[blue]QA Testing Endpoints", total=100, visible=False
        )

        try:
            # Execute pipeline
            state: AnalysisState = {
                "url": url,
                "output_dir": output_dir
            }

            # Stream pipeline execution
            # Note: For Iteration 1, we'll use ainvoke() without streaming
            # In future iterations, we can use astream() for real-time progress updates

            # Phase 1: Run 1
            progress.update(
                task_run1,
                description="[cyan]Run 1: Phase 0 (Detection)",
                completed=0
            )

            # For now, we'll execute the full pipeline and simulate progress
            # In a future iteration, we can integrate LangGraph streaming
            import time

            # Start pipeline execution in background
            # Generate a thread_id for checkpointing
            import uuid
            thread_id = f"analysis-{uuid.uuid4().hex[:8]}"
            config = {"configurable": {"thread_id": thread_id}}

            async def execute_pipeline():
                return await pipeline.ainvoke(state, config=config)

            # Simulate progress while pipeline runs
            # (In production, this would hook into LangGraph events)
            pipeline_task = asyncio.create_task(execute_pipeline())

            # Phase-by-phase simulation (simplified for Iteration 1)
            phases = [
                (task_run1, "Run 1: Phase 0 (Detection)", 25),
                (task_run1, "Run 1: Phase 1 (Documentation)", 50),
                (task_run1, "Run 1: Phase 2 (Testing)", 75),
                (task_run1, "Run 1: Phase 3 (Validation)", 100),
            ]

            phase_idx = 0
            while not pipeline_task.done() and phase_idx < len(phases):
                await asyncio.sleep(2)  # Check every 2 seconds
                if phase_idx < len(phases):
                    task_id, desc, completed = phases[phase_idx]
                    progress.update(task_id, description=f"[cyan]{desc}", completed=completed)
                    phase_idx += 1

            # Wait for pipeline to complete
            result = await pipeline_task

            # Mark Run 1 complete
            progress.update(
                task_run1,
                description="[green]Run 1: Complete ✓",
                completed=100,
            )
            progress.update(task_overall, advance=1)

            # Phase 2: Decision
            progress.update(task_decision, visible=True, completed=0)
            await asyncio.sleep(0.5)  # Brief pause for visibility
            progress.update(
                task_decision,
                description=f"[yellow]Confidence Check: {result['confidence_score']:.2f} ✓",
                completed=100,
            )
            progress.update(task_overall, advance=1)

            # Phase 3: Run 2 (conditional)
            if result.get("run2_required", False):
                progress.update(task_run2, visible=True, completed=50)
                progress.update(
                    task_run2,
                    description="[green]Run 2: Complete ✓",
                    completed=100,
                )
                progress.update(task_overall, advance=1)
            else:
                progress.update(
                    task_run2,
                    description="[dim]Run 2: Skipped (confidence ≥ 0.8)",
                    visible=True,
                    completed=100,
                )
                progress.update(task_overall, advance=1)

            # Phase 4: Collation
            progress.update(task_collation, visible=True, completed=50)
            await asyncio.sleep(0.5)
            progress.update(
                task_collation,
                description="[green]Collation: Complete ✓",
                completed=100,
            )
            progress.update(task_overall, advance=1)

            # Phase 5: QA
            progress.update(task_qa, visible=True, completed=50)
            await asyncio.sleep(0.5)
            progress.update(
                task_qa,
                description="[green]QA Testing: Complete ✓",
                completed=100,
            )
            progress.update(task_overall, advance=1)

            # Display results summary
            console.print("\n[bold green]✓ Analysis Complete![/bold green]\n")

            # Summary statistics
            final_spec = result.get("final_spec")
            qa_results = result.get("qa_results")

            if final_spec:
                console.print(f"[bold]Data Source Type:[/bold] {final_spec.source_type}")
                console.print(
                    f"[bold]Confidence Score:[/bold] {result['confidence_score']:.2f}"
                )
                console.print(
                    f"[bold]Total Endpoints:[/bold] {len(final_spec.endpoints)}"
                )

            if qa_results:
                console.print(
                    f"[bold]QA Results:[/bold] "
                    f"{qa_results['keep']} kept, "
                    f"{qa_results['remove']} removed, "
                    f"{qa_results['flag']} flagged"
                )

            # Output files
            console.print(f"\n[bold]Output files in {output_dir}/:[/bold]")

            # Check which files were created
            output_path = Path(output_dir)
            output_files = [
                "phase0_detection.json",
                "phase1_documentation.json",
                "phase2_tests.json",
                "validated_datasource_spec.json",  # CHANGED from phase3_validated_spec.json
                "ba_validation_report.json",  # ADDED (saved by validator)
                "final_validated_spec.json",
                "endpoint_qa_results.json",  # CHANGED from qa_results.json
            ]

            for filename in output_files:
                filepath = output_path / filename
                if filepath.exists():
                    size = filepath.stat().st_size
                    console.print(f"  [green]✓[/green] {filename} ({size:,} bytes)")
                else:
                    console.print(f"  [dim]- {filename} (not created)[/dim]")

            # Success message
            console.print(
                f"\n[bold green]Run 'claude-scraper generate' to create a scraper from this analysis.[/bold green]"
            )

        except Exception as e:
            # Mark all tasks as failed
            progress.update(
                task_run1,
                description="[red]Run 1: Failed ✗",
                completed=100
            )
            raise


@cli.command()
@click.option(
    "--ba-spec-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to validated BA spec JSON (datasource_analysis/validated_datasource_spec.json)",
)
@click.option(
    "--url",
    help="Source URL to analyze (triggers BA Analyzer)",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    help="Output directory for generated scraper (default: ./generated_scrapers/{source_snake}/)",
)
@click.option("--debug", is_flag=True, help="Enable debug logging")
def generate(
    ba_spec_file: Path | None,
    url: str | None,
    output_dir: Path | None,
    debug: bool,
) -> None:
    """Generate scraper from BA spec or URL.

    Two input modes:
    1. BA spec file: claude-scraper generate --ba-spec-file path/to/spec.json
    2. Source URL: claude-scraper generate --url https://api.example.com

    Examples:
        # Use existing BA spec
        claude-scraper generate --ba-spec-file datasource_analysis/validated_datasource_spec.json

        # Analyze URL first, then generate
        claude-scraper generate --url https://api.example.com --output-dir my_scraper
    """
    try:
        # Validate input
        if not ba_spec_file and not url:
            console.print("[bold red]Error:[/bold red] Must provide either --ba-spec-file or --url")
            raise click.Abort()

        if ba_spec_file and url:
            console.print("[bold red]Error:[/bold red] Cannot provide both --ba-spec-file and --url")
            raise click.Abort()

        # Setup logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stderr)],
        )

        # Initialize orchestrator
        from claude_scraper.generators.orchestrator import (
            ScraperOrchestrator,
            BAAnalysisError,
            GenerationError,
        )

        orchestrator = ScraperOrchestrator()

        # Execute based on input mode
        if ba_spec_file:
            # Mode 1: Use existing BA spec
            console.print(f"\n[bold cyan]Loading BA spec:[/bold cyan] {ba_spec_file}\n")

            result = asyncio.run(
                orchestrator.generate_from_spec(
                    ba_spec_file=ba_spec_file,
                    output_dir=output_dir,
                )
            )

        else:  # url
            # Mode 2: Analyze URL first
            console.print(f"\n[bold cyan]Analyzing URL:[/bold cyan] {url}\n")
            console.print("[yellow]Running BA Analyzer (this may take 5-10 minutes)...[/yellow]\n")

            result = asyncio.run(
                orchestrator.generate_from_url(
                    url=url,
                    output_dir=output_dir,
                )
            )

            console.print(f"\n[bold green]BA Analysis complete:[/bold green]")
            console.print(f"  Source type: {result.source_type}")
            console.print(f"  Confidence: {result.confidence_score:.2f}")
            console.print(f"  BA spec saved: {result.ba_spec_path}\n")

        # Display results
        console.print(f"\n[bold green]✓ Scraper generation complete![/bold green]\n")
        console.print(f"[bold]Generated files:[/bold]")
        console.print(f"  Scraper: {result.generated_files.scraper_path}")
        console.print(f"  Tests: {result.generated_files.test_path}")
        console.print(f"  README: {result.generated_files.readme_path}")

        console.print(f"\n[bold]Metadata:[/bold]")
        console.print(f"  Source: {result.generated_files.metadata['source']}")
        console.print(f"  Data type: {result.generated_files.metadata['data_type']}")
        console.print(f"  Collection method: {result.generated_files.metadata['collection_method']}")
        console.print(f"  AI generated: {result.generated_files.metadata['ai_generated']}")

        console.print(f"\n[bold green]Next steps:[/bold green]")
        console.print(f"1. Review generated scraper: {result.generated_files.scraper_path}")
        console.print(f"2. Run tests: pytest {result.generated_files.test_path}")
        console.print(f"3. Configure credentials if needed (see README)")

    except (BAAnalysisError, GenerationError) as e:
        console.print(f"\n[bold red]Generation failed:[/bold red] {e}")
        if debug:
            console.print_exception()
        raise click.Abort()
    except ValueError as e:
        console.print(f"\n[bold red]Validation Error:[/bold red] {e}")
        if debug:
            console.print_exception()
        raise click.Abort()
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}")
        if debug:
            console.print_exception()
        raise click.Abort()


@cli.command()
@click.option(
    "--scraper-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default="sourcing/scraping",
    help="Root directory containing scrapers (default: sourcing/scraping)",
)
@click.option(
    "--scraper",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Specific scraper file to fix (if not provided, will prompt for selection)",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Run QA validation after applying fix (default: enabled)",
)
@click.option("--debug", is_flag=True, help="Enable debug logging")
def fix(
    scraper_root: Path,
    scraper: Path | None,
    validate: bool,
    debug: bool,
) -> None:
    """Fix issues in an existing scraper.

    This command:
    1. Scans for scrapers (or uses --scraper path)
    2. Prompts for issue description
    3. Applies fixes with string replacement operations
    4. Updates timestamps
    5. Runs QA validation (optional)

    Examples:
        # Interactive mode - select scraper from list
        claude-scraper fix

        # Fix specific scraper
        claude-scraper fix --scraper sourcing/scraping/scraper_miso_http.py

        # Skip validation
        claude-scraper fix --scraper scraper_miso.py --no-validate
    """
    try:
        # Setup logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stderr)],
        )

        from claude_scraper.fixers.fixer import ScraperFixer

        fixer = ScraperFixer(scraper_root=str(scraper_root))

        console.print("\n[bold cyan]Scraper Fixer[/bold cyan]\n")

        # Step 1: Get scraper to fix
        if not scraper:
            # Scan and prompt for selection
            console.print("[cyan]Scanning for scrapers...[/cyan]")
            scrapers = fixer.scan_scrapers()

            if not scrapers:
                console.print(f"[bold red]No scrapers found in {scraper_root}[/bold red]")
                raise click.Abort()

            console.print(f"\n[green]Found {len(scrapers)} scrapers:[/green]")
            for i, s in enumerate(scrapers, 1):
                console.print(f"  {i}. {s.name}")

            selection = click.prompt("\nSelect scraper number", type=int)
            if selection < 1 or selection > len(scrapers):
                console.print("[bold red]Invalid selection[/bold red]")
                raise click.Abort()

            scraper = scrapers[selection - 1]

        console.print(f"\n[bold]Selected scraper:[/bold] {scraper.name}")

        # Step 2: Get problem description
        problem = click.prompt("\nDescribe the problem", type=str)

        # Step 3: Get fix operations
        console.print("\n[yellow]Enter fix operations (one per line).[/yellow]")
        console.print("[dim]Format: OLD_STRING -> NEW_STRING[/dim]")
        console.print("[dim]Press Enter twice when done.[/dim]\n")

        fix_operations = []
        while True:
            line = click.prompt("", default="", show_default=False)
            if not line:
                break

            if "->" not in line:
                console.print("[red]Invalid format. Use: OLD_STRING -> NEW_STRING[/red]")
                continue

            old, new = line.split("->", 1)
            fix_operations.append({
                "file": str(scraper),
                "old": old.strip(),
                "new": new.strip(),
            })

        if not fix_operations:
            console.print("[yellow]No fix operations provided. Aborting.[/yellow]")
            raise click.Abort()

        # Step 4: Apply fixes
        console.print(f"\n[cyan]Applying {len(fix_operations)} fix operations...[/cyan]")

        result = asyncio.run(
            fixer.fix_scraper(
                scraper_path=scraper,
                problem=problem,
                fix_operations=fix_operations,
                validate=validate,
            )
        )

        # Display results
        console.print(f"\n[bold green]✓ Fix applied successfully![/bold green]\n")
        console.print(f"[bold]Problem:[/bold] {result.problem_description}")
        console.print(f"[bold]Fix:[/bold] {result.fix_description}")
        console.print(f"[bold]Files modified:[/bold] {len(result.files_modified)}")
        for file in result.files_modified:
            console.print(f"  - {file}")

        if validate:
            if result.validation_passed:
                console.print(f"\n[bold green]✓ QA Validation: PASSED[/bold green]")
                if result.validation_fixes_applied > 0:
                    console.print(f"  Auto-fixes applied: {result.validation_fixes_applied}")
            else:
                console.print(f"\n[bold yellow]⚠ QA Validation: INCOMPLETE[/bold yellow]")
                console.print("  Manual review required")

    except ValueError as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        if debug:
            console.print_exception()
        raise click.Abort()
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}")
        if debug:
            console.print_exception()
        raise click.Abort()


@cli.command()
@click.option(
    "--mode",
    type=click.Choice(["scan", "auto"]),
    default="scan",
    help="Mode: scan (report only) or auto (update scrapers)",
)
@click.option(
    "--scraper-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default="sourcing/scraping",
    help="Root directory containing scrapers (default: sourcing/scraping)",
)
@click.option(
    "--validate/--no-validate",
    default=True,
    help="Run QA validation after updates (default: enabled)",
)
@click.option(
    "--non-interactive",
    is_flag=True,
    help="Non-interactive mode: update all without prompts",
)
@click.option("--debug", is_flag=True, help="Enable debug logging")
def update(
    mode: str,
    scraper_root: Path,
    validate: bool,
    non_interactive: bool,
    debug: bool,
) -> None:
    """Update scrapers to current infrastructure version.

    This command:
    1. Scans scrapers and detects versions
    2. Identifies outdated scrapers (< v1.6.0)
    3. Detects generator agent for each scraper
    4. Regenerates scrapers with current infrastructure
    5. Runs QA validation

    Two modes:
    - scan: Generate report, don't update
    - auto: Interactively update scrapers (or all if --non-interactive)

    Examples:
        # Scan and report only
        claude-scraper update --mode scan

        # Interactive update (select which scrapers)
        claude-scraper update --mode auto

        # Non-interactive update (all outdated)
        claude-scraper update --mode auto --non-interactive

        # Skip validation
        claude-scraper update --mode auto --no-validate
    """
    try:
        # Setup logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stderr)],
        )

        from claude_scraper.fixers.updater import ScraperUpdater, CURRENT_INFRASTRUCTURE_VERSION

        updater = ScraperUpdater(scraper_root=str(scraper_root))

        console.print("\n[bold cyan]Scraper Updater[/bold cyan]\n")
        console.print(f"[dim]Current infrastructure version: {CURRENT_INFRASTRUCTURE_VERSION}[/dim]\n")

        # Step 0: Copy infrastructure (gold standard) - only in auto mode
        if mode == "auto":
            console.print("[cyan]Updating infrastructure to v1.6.0 (gold standard)...[/cyan]")
            if not updater.copy_infrastructure():
                console.print("[bold red]✗ Failed to copy infrastructure[/bold red]")
                console.print("[dim]Cannot proceed without infrastructure[/dim]")
                raise click.Abort()
            console.print("[green]✓ Infrastructure updated[/green]\n")

        # Step 1: Scan scrapers
        console.print("[cyan]Scanning scrapers...[/cyan]")
        scrapers = updater.scan_scrapers()

        if not scrapers:
            console.print(f"[bold red]No scrapers found in {scraper_root}[/bold red]")
            raise click.Abort()

        # Filter outdated
        outdated = [s for s in scrapers if s.needs_update]

        if mode == "scan":
            # Scan mode: Generate report
            report = updater.generate_scan_report(scrapers)
            console.print(report)
            return

        # Auto mode: Update scrapers
        if not outdated:
            console.print("[green]All scrapers are up-to-date![/green]")
            return

        console.print(f"[yellow]Found {len(outdated)} outdated scrapers[/yellow]\n")

        # Select scrapers to update
        if non_interactive:
            # Update all
            to_update = outdated
            console.print("[dim]Non-interactive mode: updating all outdated scrapers[/dim]\n")
        else:
            # Interactive selection
            console.print("[bold]Outdated scrapers:[/bold]")
            for i, scraper in enumerate(outdated, 1):
                version = scraper.current_version or "UNKNOWN"
                console.print(f"  {i}. {scraper.path.name} (v{version})")

            console.print("\n[dim]Enter numbers separated by commas (e.g., 1,3,4) or 'all'[/dim]")
            selection = click.prompt("Select scrapers to update", type=str, default="all")

            if selection.lower() == "all":
                to_update = outdated
            else:
                indices = [int(x.strip()) - 1 for x in selection.split(",")]
                to_update = [outdated[i] for i in indices if 0 <= i < len(outdated)]

        if not to_update:
            console.print("[yellow]No scrapers selected[/yellow]")
            return

        # Update each scraper
        console.print(f"\n[cyan]Updating {len(to_update)} scrapers...[/cyan]\n")
        results = []

        for scraper_info in to_update:
            console.print(f"[bold]Updating:[/bold] {scraper_info.path.name}")

            result = asyncio.run(
                updater.update_scraper(scraper_info, validate=validate)
            )
            results.append(result)

            if result.error:
                console.print(f"  [red]✗ Failed: {result.error}[/red]")
            elif result.validation_passed:
                console.print(f"  [green]✓ Updated and validated[/green]")
            else:
                console.print(f"  [yellow]⚠ Updated but needs review[/yellow]")

        # Generate report
        console.print()
        report = updater.generate_update_report(
            results,
            mode="non-interactive" if non_interactive else "interactive",
        )
        console.print(report)

    except ValueError as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        if debug:
            console.print_exception()
        raise click.Abort()
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error:[/bold red] {e}")
        if debug:
            console.print_exception()
        raise click.Abort()


if __name__ == "__main__":
    cli()
