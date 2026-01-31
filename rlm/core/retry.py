"""Retry mechanism with exponential backoff for transient failures."""

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry_with_backoff(
    func: Callable[[], T],
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (
        ConnectionError,
        TimeoutError,
        OSError,
    ),
) -> T:
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry (no arguments)
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Multiplier for delay after each retry
        retryable_exceptions: Tuple of exception types to retry on

    Returns:
        Result from function call

    Raises:
        Last exception if all retries fail
    """
    last_exception: Exception | None = None
    delay = initial_delay

    for attempt in range(max_attempts):
        try:
            return func()
        except retryable_exceptions as e:
            last_exception = e
            if attempt < max_attempts - 1:
                time.sleep(min(delay, max_delay))
                delay *= backoff_factor
            else:
                raise

    # Should never reach here, but type checker needs it
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry failed without exception")
