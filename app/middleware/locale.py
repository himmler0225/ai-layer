from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.i18n.locale import resolve_locale, set_locale


class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """Resolve and set the request locale, then continue the request.

        Args:
            request: The incoming request, used to resolve the locale (e.g.
                from headers/query params).
            call_next: The next handler in the middleware chain."""
        set_locale(resolve_locale(request))
        return await call_next(request)
