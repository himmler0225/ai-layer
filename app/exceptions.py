class AiLayerError(Exception):
    """Base exception for ai-layer."""

    http_status: int = 500

    def __init__(
        self,
        message: str,
        *,
        message_key: str | None = None,
        message_en: str | None = None,
        message_params: dict | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize the error with a fallback message plus optional localization/context.

        Args:
            message: Fallback message, used if no localized message can be resolved.
            message_key: i18n key used to look up a localized client-facing message.
            message_en: Explicit English override for the client-facing message.
            message_params: Parameters interpolated into the localized message.
            cause: Original exception that triggered this error, if any."""
        super().__init__(message)
        self.message = message
        self.message_key = message_key
        self.message_en = message_en
        self.message_params = message_params or {}
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
