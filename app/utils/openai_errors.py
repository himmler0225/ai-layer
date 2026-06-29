"""Deprecated alias — use app.utils.llm_errors."""

from app.utils.llm_errors import (  # noqa: F401
    is_upstream_gateway_error,
    log_error,
    request_id,
    should_retry,
    user_message,
)
