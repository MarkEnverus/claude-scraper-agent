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
    "--mode",
    type=click.Choice(["analyze", "generate"]),
    required=True,
    help="Mode to run: analyze data source or generate scraper",
)
@click.option("--url", help="Data source URL to analyze")
@click.option(
    "--provider",
    type=click.Choice(["bedrock", "anthropic"]),
    default="bedrock",
    help="LLM provider to use (default: bedrock)",
)
@click.option("--debug", is_flag=True, help="Enable debug mode")
def run(mode: str, url: str | None, provider: str, debug: bool) -> None:
    """[DEPRECATED] Run data source analysis or scraper generation.

    This command is deprecated. Use 'analyze' or 'generate' commands instead:
    - claude-scraper analyze --url <url>
    - claude-scraper generate (coming soon)
    """
    console.print(
        "[yellow]Warning: 'run' command is deprecated. "
        "Use 'analyze' or 'generate' commands instead.[/yellow]\n"
    )

    if mode == "analyze":
        # Redirect to analyze command
        from click.testing import CliRunner
        runner = CliRunner()
        args = ["analyze", "--url", url or "", "--provider", provider]
        if debug:
            args.append("--debug")
        result = runner.invoke(cli, args, catch_exceptions=False)
        sys.exit(result.exit_code)
    else:
        console.print("[red]Error: 'generate' mode not yet implemented[/red]")
        raise click.Abort()


if __name__ == "__main__":
    cli()
