"""Performance profiling utilities for measuring execution time.

This module provides decorators and utilities for measuring and logging
execution time of synchronous and asynchronous functions.

Example:
    >>> from claude_scraper.utils.profiling import profile_time
    >>>
    >>> @profile_time("Database query")
    >>> async def fetch_data(id: int):
    ...     # ... query logic ...
    ...     return result
    >>>
    >>> # Logs: [PERF] Database query - START
    >>> # Logs: [PERF] Database query - DONE in 1.23s
"""

import time
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


def profile_time(operation_name: str) -> Callable:
    """Decorator to measure and log execution time.

    Automatically handles both sync and async functions. Logs start time,
    end time, and duration to the logger at INFO level (success) or
    ERROR level (failure).

    Args:
        operation_name: Descriptive name for the operation being measured

    Returns:
        Decorator function that wraps the target function

    Example:
        >>> @profile_time("Phase 0: Detection")
        >>> async def analyze_phase0(self, url: str):
        ...     # ... analysis logic ...
        ...     return result

        >>> # Log output:
        >>> # [PERF] Phase 0: Detection - START
        >>> # [PERF] Phase 0: Detection - DONE in 12.34s
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper for async functions."""
            start = time.time()
            logger.info(f"[PERF] {operation_name} - START")
            try:
                result = await func(*args, **kwargs)
                elapsed = time.time() - start
                logger.info(f"[PERF] {operation_name} - DONE in {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(f"[PERF] {operation_name} - FAILED after {elapsed:.2f}s: {e}")
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Wrapper for synchronous functions."""
            start = time.time()
            logger.info(f"[PERF] {operation_name} - START")
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start
                logger.info(f"[PERF] {operation_name} - DONE in {elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start
                logger.error(f"[PERF] {operation_name} - FAILED after {elapsed:.2f}s: {e}")
                raise

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
