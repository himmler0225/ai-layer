"""Optional Langfuse tracing for the LangGraph agent. No-ops everywhere if
LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY aren't configured."""

import app.config.settings as settings
from app.config.logger import Logger, log_event

logger = Logger.get(__name__)

_handler = None
_handler_built = False


def is_configured() -> bool:
    """Return True if both Langfuse keys are set.

    Returns:
        Whether tracing should be enabled."""
    return bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)


def get_langfuse_handler():
    """Get or lazily create the cached Langfuse LangChain callback handler.

    Returns:
        A `langfuse.langchain.CallbackHandler` instance, or `None` if Langfuse
        isn't configured or failed to initialize (logged, not raised — tracing
        is best-effort and must never break the agent)."""
    global _handler, _handler_built
    if _handler_built:
        return _handler
    _handler_built = True
    if not is_configured():
        return None
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        _handler = CallbackHandler()
    except Exception as exc:
        logger.warning(log_event("langfuse", "handler init failed", error=exc))
        _handler = None
    return _handler


def flush() -> None:
    """Flush any buffered Langfuse events before process shutdown.

    Returns:
        None. No-op if Langfuse was never configured/initialized."""
    if _handler is None:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception as exc:
        logger.warning(log_event("langfuse", "flush failed", error=exc))
