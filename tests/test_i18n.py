from app.exceptions import AiLayerAuthError
from app.i18n import msg, set_locale, t
from app.i18n.locale import normalize_locale, resolve_locale
from app.i18n.responses import client_message
from app.services.agent.events.schema import error, status, tool_start
from app.utils.llm_errors import user_message
from openai import APIStatusError


class _FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = headers or {}


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.request = None
        self.headers = {}


def test_t_vi_en():
    assert t("errors.invalid_api_key", "vi") == "API key không hợp lệ"
    assert t("errors.invalid_api_key", "en") == "Invalid API key"


def test_normalize_locale():
    assert normalize_locale("vi-VN") == "vi"
    assert normalize_locale("en-US") == "en"
    assert normalize_locale(None) == "en"


def test_resolve_locale_prefers_x_lang():
    req = _FakeRequest({"x-lang": "vi", "x-locale": "en"})
    assert resolve_locale(req) == "vi"


def test_resolve_locale_header_legacy():
    req = _FakeRequest({"x-locale": "vi"})
    assert resolve_locale(req) == "vi"


def test_client_message_with_key():
    exc = AiLayerAuthError("fallback", message_key="errors.invalid_api_key")
    assert client_message(exc, "vi") == "API key không hợp lệ"
    assert client_message(exc, "en") == "Invalid API key"


def test_user_message_localized():
    exc = APIStatusError("bad", response=_FakeResponse(400), body={})
    vi = user_message(exc, "vi")
    en = user_message(exc, "en")
    assert "LLM" in vi
    assert "LLM" in en


def test_sse_events_use_single_detail():
    set_locale("vi")
    assert '"detail"' in status(msg("agent.status.analyzing")).to_sse()
    assert "detail_vi" not in status(msg("agent.status.analyzing")).to_sse()
    assert "detail_en" not in tool_start("youtube_search", "x", {}).to_sse()
    assert '"detail": "x"' in tool_start("youtube_search", "x", {}).to_sse()
    assert '"detail"' in error("boom").to_sse()
    assert "detail_vi" not in error("boom").to_sse()
