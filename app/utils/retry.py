def retry_delay(attempt: int) -> float:
    """Exponential backoff: 1s, 2s, 4s… (attempt is 1-based)."""
    return float(2 ** (attempt - 1))
