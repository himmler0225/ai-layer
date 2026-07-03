class AiLayerError(Exception):
    """Base exception for ai-layer."""

    http_status: int = 500

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.cause = cause


class AiLayerConfigError(AiLayerError):
    """Missing or invalid configuration."""

    http_status = 500


class AiLayerAuthError(AiLayerError):
    """Authentication or authorization failure."""

    http_status = 401


class AiLayerForbiddenError(AiLayerError):
    """Authorization failure — authenticated but not permitted."""

    http_status = 403


class AiLayerNotFoundError(AiLayerError):
    """Requested resource was not found."""

    http_status = 404


class AiLayerValidationError(AiLayerError):
    """Invalid input or request parameters."""

    http_status = 400


class AiLayerUpstreamError(AiLayerError):
    """Upstream service failure (data-miner, external APIs, etc.)."""

    http_status = 502


class AiLayerTimeoutError(AiLayerError):
    """Operation timed out or exceeded iteration limits."""

    http_status = 504


class AiLayerLLMError(AiLayerUpstreamError):
    """LLM provider failure."""


class AiLayerAgentError(AiLayerError):
    """Agent execution failure."""

    http_status = 502


class AiLayerServiceUnavailableError(AiLayerError):
    """Service temporarily unavailable."""

    http_status = 503
