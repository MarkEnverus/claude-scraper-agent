"""CLI utilities for error handling, retry logic, and progress tracking."""

import logging
import time
from functools import wraps
from typing import TypeVar, Callable, Any, Optional
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

console = Console()
logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryableError(Exception):
    """Error that can be retried."""
    pass


class UserError(Exception):
    """Error caused by user input or configuration."""
    pass


def retry_on_error(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (RetryableError,),
) -> Callable:
    """Decorator to retry a function on specific exceptions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to retry on

    Example:
        @retry_on_error(max_attempts=3, delay=1.0)
        async def fetch_data():
            # ... code that might fail transiently
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        break

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    console.print(
                        f"[yellow]⚠ Attempt {attempt} failed. "
                        f"Retrying in {current_delay:.1f}s...[/yellow]"
                    )

                    time.sleep(current_delay)
                    current_delay *= backoff

            # All retries exhausted
            raise last_exception

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        break

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    console.print(
                        f"[yellow]⚠ Attempt {attempt} failed. "
                        f"Retrying in {current_delay:.1f}s...[/yellow]"
                    )

                    time.sleep(current_delay)
                    current_delay *= backoff

            # All retries exhausted
            raise last_exception

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def handle_cli_error(error: Exception, debug: bool = False) -> None:
    """Handle CLI errors with helpful messages and suggestions.

    Args:
        error: The exception that occurred
        debug: Whether to show full traceback
    """
    if isinstance(error, UserError):
        # User configuration or input error
        console.print(f"\n[bold red]✗ Error:[/bold red] {error}")
        console.print("\n[yellow]Suggestion:[/yellow]")
        console.print(_get_suggestion_for_error(error))

    elif isinstance(error, FileNotFoundError):
        console.print(f"\n[bold red]✗ File Not Found:[/bold red] {error}")
        console.print("\n[yellow]Suggestion:[/yellow]")
        console.print("• Check that the file path is correct")
        console.print("• Verify the file exists and you have read permissions")

    elif isinstance(error, PermissionError):
        console.print(f"\n[bold red]✗ Permission Denied:[/bold red] {error}")
        console.print("\n[yellow]Suggestion:[/yellow]")
        console.print("• Check file/directory permissions")
        console.print("• Ensure you have write access to the output directory")

    elif isinstance(error, ValueError):
        console.print(f"\n[bold red]✗ Invalid Value:[/bold red] {error}")
        console.print("\n[yellow]Suggestion:[/yellow]")
        console.print("• Check your input format matches the expected pattern")
        console.print("• Review command help with --help flag")

    else:
        # Generic error
        console.print(f"\n[bold red]✗ Unexpected Error:[/bold red] {error}")
        console.print("\n[yellow]Suggestion:[/yellow]")
        console.print("• Try running with --debug flag for more details")
        console.print("• Check the logs for error details")

    if debug:
        console.print("\n[dim]Full traceback:[/dim]")
        console.print_exception()


def _get_suggestion_for_error(error: Exception) -> str:
    """Get helpful suggestion based on error message.

    Args:
        error: The exception

    Returns:
        Suggestion text
    """
    error_msg = str(error).lower()

    if "api key" in error_msg or "authentication" in error_msg:
        return (
            "• Set the required API key environment variable\n"
            "• For Bedrock: Ensure AWS credentials are configured\n"
            "• For Anthropic: Set ANTHROPIC_API_KEY environment variable"
        )

    elif "connection" in error_msg or "network" in error_msg:
        return (
            "• Check your internet connection\n"
            "• Verify the API endpoint is accessible\n"
            "• Check if you're behind a proxy/firewall"
        )

    elif "timeout" in error_msg:
        return (
            "• The operation took too long to complete\n"
            "• Try again or increase timeout if supported\n"
            "• Check if the remote service is responding"
        )

    elif "rate limit" in error_msg:
        return (
            "• You've exceeded the API rate limit\n"
            "• Wait a few moments and try again\n"
            "• Consider using a different provider or API key"
        )

    else:
        return "• Review the error message above for specific details"


def validate_file_path(
    path: Path,
    must_exist: bool = True,
    must_be_file: bool = False,
    must_be_dir: bool = False,
) -> None:
    """Validate a file path with helpful error messages.

    Args:
        path: Path to validate
        must_exist: Whether path must exist
        must_be_file: Whether path must be a file
        must_be_dir: Whether path must be a directory

    Raises:
        UserError: If validation fails
    """
    if must_exist and not path.exists():
        raise UserError(
            f"Path does not exist: {path}\n"
            f"  Please create it or check the path is correct."
        )

    if must_be_file and path.exists() and not path.is_file():
        raise UserError(
            f"Path is not a file: {path}\n"
            f"  Expected a file, but found a directory."
        )

    if must_be_dir and path.exists() and not path.is_dir():
        raise UserError(
            f"Path is not a directory: {path}\n"
            f"  Expected a directory, but found a file."
        )


def validate_scraper_root(path: Path) -> None:
    """Validate scraper root directory with helpful suggestions.

    Args:
        path: Scraper root path

    Raises:
        UserError: If validation fails
    """
    if not path.exists():
        raise UserError(
            f"Scraper root directory does not exist: {path}\n\n"
            f"Suggestion:\n"
            f"  • Create the directory: mkdir -p {path}\n"
            f"  • Or specify a different root with --scraper-root"
        )

    if not path.is_dir():
        raise UserError(
            f"Scraper root is not a directory: {path}\n\n"
            f"Suggestion:\n"
            f"  • Provide a directory path, not a file\n"
            f"  • Use --scraper-root to specify the correct directory"
        )

    # Check if directory is readable
    if not any(path.iterdir()):
        console.print(
            f"[yellow]⚠ Warning:[/yellow] Scraper root is empty: {path}"
        )


def confirm_action(message: str, default: bool = False) -> bool:
    """Prompt user for confirmation with better formatting.

    Args:
        message: Confirmation message
        default: Default choice

    Returns:
        True if confirmed, False otherwise
    """
    return click.confirm(
        click.style(f"\n{message}", fg="yellow"),
        default=default
    )


def create_progress_bar(description: str = "Processing") -> Progress:
    """Create a Rich progress bar with consistent styling.

    Args:
        description: Description text

    Returns:
        Progress instance
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )


def print_success(message: str) -> None:
    """Print success message with consistent formatting."""
    console.print(f"\n[bold green]✓ {message}[/bold green]")


def print_warning(message: str) -> None:
    """Print warning message with consistent formatting."""
    console.print(f"\n[bold yellow]⚠ {message}[/bold yellow]")


def print_error(message: str) -> None:
    """Print error message with consistent formatting."""
    console.print(f"\n[bold red]✗ {message}[/bold red]")


def print_info(message: str) -> None:
    """Print info message with consistent formatting."""
    console.print(f"\n[cyan]ℹ {message}[/cyan]")
