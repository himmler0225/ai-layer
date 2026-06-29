import pytest

from app.utilities.url_shortener import _call_provider


@pytest.mark.asyncio
async def test_call_provider_logs_exception(monkeypatch):
    class _BrokenResponse:
        def raise_for_status(self):
            raise RuntimeError("network down")

    class _BrokenClient:
        async def get(self, *_args, **_kwargs):
            return _BrokenResponse()

    monkeypatch.setattr(
        "app.utilities.url_shortener._get_http",
        lambda: _BrokenClient(),
    )
    result = await _call_provider("https://example.com", "https://x", {}, "tinyurl")
    assert "error" in result
    assert "network down" in result["error"]
